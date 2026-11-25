"""Call each provider once, log latency to runs.jsonl, and tell you early what works.

  python -m pipeline.smoke_test

Checks: Gemini (lists model ids so you can set GEMINI_TTS_MODEL / text model correctly, then one tiny
text call), Cloudflare Workers AI (one small image), Kaggle (credentials present). Never prints secrets.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

from . import common as C

GEM = "https://generativelanguage.googleapis.com/v1beta"


def gemini() -> None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("[smoke] GEMINI_API_KEY missing"); return
    h = {"x-goog-api-key": key}
    t0 = time.time()
    try:
        r = C.get(f"{GEM}/models?pageSize=200", headers=h)
    except Exception as e:
        print(f"[smoke] gemini list FAILED: {e}"); C.log_call("smoke", "gemini-list", status="fail", note=str(e)[:200]); return
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])]
    C.log_call("smoke", "gemini-list", latency_s=time.time() - t0, params={"n_models": len(names)})
    print("[smoke] gemini OK. Candidate model ids (set GEMINI_TEXT_MODEL / GEMINI_TTS_MODEL):")
    for n in names:
        if any(k in n for k in ("flash", "tts")):
            print("   ", n)
    model = os.environ.get("GEMINI_TEXT_MODEL", "")
    if model:
        t0 = time.time()
        try:
            C.post(f"{GEM}/models/{model}:generateContent", headers={**h, "Content-Type": "application/json"},
                   json_body={"contents": [{"parts": [{"text": "Reply with the single word: ok"}]}]})
            C.log_call("smoke", model, latency_s=time.time() - t0, params={"kind": "text"})
            print(f"[smoke] text model {model} OK ({time.time() - t0:.1f}s)")
        except Exception as e:
            C.log_call("smoke", model, status="fail", note=str(e)[:200]); print(f"[smoke] text model FAILED: {e}")


def cloudflare() -> None:
    tok, acct = os.environ.get("CLOUDFLARE_API_TOKEN"), os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    if not (tok and acct):
        print("[smoke] CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID missing"); return
    model = "@cf/black-forest-labs/flux-1-schnell"
    t0 = time.time()
    try:
        r = C.post(f"https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}",
                   headers={"Authorization": f"Bearer {tok}"}, json_body={"prompt": "a red clay cup on a table", "steps": 4})
        ok = "image" in (r.json().get("result") or {})
        C.log_call("smoke", model, latency_s=time.time() - t0, params={"steps": 4}, status="ok" if ok else "fail")
        print(f"[smoke] cloudflare {'OK' if ok else 'returned no image'} ({time.time() - t0:.1f}s)")
    except Exception as e:
        C.log_call("smoke", model, status="fail", note=str(e)[:200]); print(f"[smoke] cloudflare FAILED: {e}")


def kaggle() -> None:
    cfg = Path.home() / ".kaggle" / "kaggle.json"
    ok = cfg.exists() or (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    print(f"[smoke] kaggle credentials: {'found' if ok else 'missing (needed only for the optional CLI automation)'}")
    C.log_call("smoke", "kaggle-credentials", status="ok" if ok else "missing")


def main() -> None:
    if C.dry_run():
        print("[smoke] DRY_RUN=1: nothing to call"); return
    gemini(); cloudflare(); kaggle()
    print("[smoke] latencies are in runs.jsonl. Note the real free-tier limits you hit in COSTS.md.")


if __name__ == "__main__":
    main()
