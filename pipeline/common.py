"""Shared helpers: paths, env, hashing, cache manifest, retries, HTTP, run logging.

Design rules (see ARCHITECTURE.md):
  * storyboard.json is the only input a stage needs besides secrets in .env
  * every stage is idempotent: it hashes its inputs and skips work whose output
    already exists with the same hash (outputs/manifest.json)
  * every model call appends exactly one line to runs.jsonl
  * secrets only come from the environment / .env and are never logged
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

import requests

CODE_ROOT = Path(__file__).resolve().parent.parent
# HERITAGE_ROOT lets tests run the pipeline against a scratch copy of the project.
ROOT = Path(os.environ.get("HERITAGE_ROOT", CODE_ROOT)).resolve()
OUT = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = CODE_ROOT / "schema" / "storyboard.schema.json"
MANIFEST = OUT / "manifest.json"


# --------------------------------------------------------------------------- env
def load_env() -> None:
    """Tiny .env loader (no dependency). Existing environment variables win."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env()


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "0") == "1"


def need_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"[config] {name} is not set. Copy .env.example to .env and fill it in "
                 f"(or run with DRY_RUN=1 to test without keys).")
    return v


# ----------------------------------------------------------------------- storyboard
def load_storyboard(path: Path | None = None) -> dict:
    return json.loads((path or STORYBOARD).read_text(encoding="utf-8"))


def seed_for(sb: dict, shot: dict, salt: int = 0) -> int:
    return int(shot.get("seed", sb["config"]["seed_base"] + salt))


# ------------------------------------------------------------------------ hashing
def stable_hash(*objs: Any) -> str:
    blob = json.dumps(objs, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- cache manifest
def _manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def is_fresh(key: str, h: str, path: Path) -> bool:
    """True when `path` exists and was produced from inputs with hash `h`."""
    m = _manifest().get(key)
    return bool(m and m.get("hash") == h and path.exists())


def mark(key: str, h: str, path: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    m = _manifest()
    m[key] = {"hash": h, "path": str(path.relative_to(ROOT)), "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
    MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


# ------------------------------------------------------------------- run logging
def log_call(stage: str, model: str, *, params: dict | None = None, seed: int | None = None,
             latency_s: float = 0.0, cost_usd: float = 0.0, gpu_minutes: float = 0.0,
             shot_id: str | None = None, status: str = "ok", attempts: int = 1, **extra: Any) -> None:
    """Append one line to runs.jsonl. `cost_usd` is the list-price equivalent, not what we paid."""
    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "stage": stage, "shot": shot_id, "model": model, "params": params or {},
        "seed": seed, "latency_s": round(latency_s, 3), "gpu_minutes": round(gpu_minutes, 3),
        "list_price_usd": round(cost_usd, 6), "status": status, "attempts": attempts,
        "dry_run": dry_run(),
    }
    rec.update(extra)
    with open(RUNS, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_runs() -> list[dict]:
    if not RUNS.exists():
        return []
    return [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]


# --------------------------------------------------------------------- failures
class TransientError(Exception):
    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after


class PermanentError(Exception):
    pass


class QuotaError(Exception):
    """Provider quota exhausted. Stages stop cleanly; cached work is kept; re-run later."""


def with_retries(fn: Callable[[], Any], *, attempts: int = 3, base_delay: float = 3.0,
                 label: str = "call") -> tuple[Any, int]:
    """Run fn with exponential backoff on TransientError. Returns (result, attempts_used)."""
    last: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return fn(), i
        except TransientError as e:
            last = e
            if i == attempts:
                break
            delay = e.retry_after if e.retry_after else base_delay * (2 ** (i - 1))
            print(f"[retry] {label}: {e} -> waiting {delay:.0f}s (attempt {i}/{attempts})")
            time.sleep(delay)
    if isinstance(last, TransientError) and "429" in str(last):
        raise QuotaError(f"{label}: rate/quota limit after {attempts} attempts") from last
    raise PermanentError(f"{label}: failed after {attempts} attempts: {last}")


def post(url: str, *, headers: dict, json_body: dict | None = None, files: dict | None = None,
         data: dict | None = None, timeout: int = 180) -> requests.Response:
    """POST that maps HTTP failures onto TransientError / PermanentError. Never prints headers."""
    try:
        r = requests.post(url, headers=headers, json=json_body, files=files, data=data, timeout=timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise TransientError(f"network: {type(e).__name__}")
    if r.status_code == 429 or r.status_code >= 500:
        ra = r.headers.get("Retry-After")
        raise TransientError(f"HTTP {r.status_code}", float(ra) if ra and ra.isdigit() else None)
    if r.status_code >= 400:
        raise PermanentError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r


def get(url: str, *, headers: dict, timeout: int = 60) -> requests.Response:
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except (requests.ConnectionError, requests.Timeout) as e:
        raise TransientError(f"network: {type(e).__name__}")
    if r.status_code == 429 or r.status_code >= 500:
        raise TransientError(f"HTTP {r.status_code}")
    if r.status_code >= 400:
        raise PermanentError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r


# --------------------------------------------------------------------------- misc
def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def run(cmd: list[str], *, cwd: Path | None = None, capture: bool = True) -> subprocess.CompletedProcess:
    p = subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True)
    if p.returncode != 0:
        tail = (p.stderr or "")[-1500:]
        raise RuntimeError(f"command failed ({p.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return p


def ffprobe_duration(path: Path) -> float:
    p = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    return float(p.stdout.strip())


def ensure(*parts: str) -> Path:
    p = OUT.joinpath(*parts)
    p.mkdir(parents=True, exist_ok=True)
    return p


def select_shots(sb: dict, ids: list[str] | None) -> list[dict]:
    return [s for s in sb["shots"] if not ids or s["id"] in ids]


def pricing() -> dict:
    p = CODE_ROOT / "pipeline" / "pricing.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def price_of(model_key: str, units: float) -> float:
    """List-price equivalent for `units` of a model. 0.0 when the price is not filled in yet."""
    per = pricing().get(model_key, {}).get("usd_per_unit")
    return float(per) * units if isinstance(per, (int, float)) else 0.0
