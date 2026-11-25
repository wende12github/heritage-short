"""Keyframe stage: reference sheet first, then one keyframe per shot (Cloudflare Workers AI, FLUX).

  python -m pipeline.keyframes reference     N options per character -> outputs/reference/
                                             then set characters[].golden_reference in storyboard.json
  python -m pipeline.keyframes run [--shot s04] [--force]

Prompt = style_block + shot prompt with {character_id} expanded to the character description,
so the subject is described identically in every shot (re-describing is the main cause of drift).
Frames are square (1:1) with the subject centred: 16:9 and 9:16 are both centre crops of it.

Cache key = hash(final prompt, model, steps, size, seed, golden reference file hash).
"""
from __future__ import annotations

import argparse
import base64
import io
import time
from pathlib import Path

from PIL import Image, ImageDraw

from . import common as C

API = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"


def compose_prompt(sb: dict, shot: dict) -> str:
    chars = {c["id"]: c["description"] for c in sb["characters"]}
    body = shot["keyframe_prompt"]
    for cid, desc in chars.items():
        body = body.replace("{" + cid + "}", desc)
    return f"{body}. {sb['style']['style_block']}"


def _golden_for(sb: dict, shot: dict) -> Path | None:
    for c in sb["characters"]:
        if c["id"] in shot["characters"] and c.get("golden_reference"):
            p = C.ROOT / c["golden_reference"]
            if p.exists():
                return p
    return None



def generate(prompt: str, cfg: dict, seed: int, golden: Path | None) -> tuple[bytes, dict]:
    token, acct = C.need_env("CLOUDFLARE_API_TOKEN"), C.need_env("CLOUDFLARE_ACCOUNT_ID")
    model = cfg["model"]
    url = API.format(acct=acct, model=model)
    headers = {"Authorization": f"Bearer {token}"}
    info = {"seed_sent": False, "reference_used": False}
    if "flux-2" in model:
        # FLUX.2 klein on Workers AI takes multipart form data and can condition on reference images.
        # NOTE: written from the model's documented behaviour; verify field names against the
        # current Workers AI model page and record any difference in FAILURES.md.
        files = {"prompt": (None, prompt), "width": (None, str(cfg.get("width", 1024))),
                 "height": (None, str(cfg.get("height", 1024))), "steps": (None, str(cfg["steps"]))}
        if cfg.get("send_seed", True):
            files["seed"] = (None, str(seed)); info["seed_sent"] = True
        if golden:
            files["input_image_0"] = ("ref.png", golden.read_bytes(), "image/png"); info["reference_used"] = True
        r = C.post(url, headers=headers, files=files)
    else:
        body = {"prompt": prompt[:2000], "steps": cfg["steps"]}
        if cfg.get("send_seed", True):
            body["seed"] = seed; info["seed_sent"] = True
        try:
            r = C.post(url, headers=headers, json_body=body)
        except C.PermanentError as e:
            if "seed" in str(e).lower() and "seed" in body:
                body.pop("seed"); info["seed_sent"] = False       # endpoint rejects seed: retry without it
                r = C.post(url, headers=headers, json_body=body)
            else:
                raise
    ctype = r.headers.get("content-type", "")
    if "json" in ctype:
        data = r.json()
        img = (data.get("result") or {}).get("image")
        if not img:
            raise C.PermanentError(f"no image in response: {str(data)[:300]}")
        return base64.b64decode(img), info
    return r.content, info


def placeholder(shot_id: str, prompt: str, path: Path, size: int = 1024) -> None:
    """DRY_RUN / missing-keyframe placeholder so the rest of the pipeline can run and be tested."""
    n = int(shot_id[1:])
    img = Image.new("RGB", (size, size), (40 + n * 14 % 120, 70 + n * 23 % 100, 90 + n * 31 % 100))
    d = ImageDraw.Draw(img)
    d.ellipse([size * .3, size * .3, size * .7, size * .7], outline=(240, 220, 180), width=8)
    d.text((size * .08, size * .08), f"{shot_id}  PLACEHOLDER", fill=(255, 255, 255))
    d.text((size * .08, size * .92), prompt[:90], fill=(230, 230, 230))
    img.convert("RGB").save(path, quality=90)


def run(sb: dict, shot_ids: list[str] | None = None, force: bool = False) -> None:
    cfg = sb["config"]["keyframe"]
    out = C.ensure("keyframes")
    done = skipped = 0
    for shot in C.select_shots(sb, shot_ids):
        prompt = compose_prompt(sb, shot)
        seed = C.seed_for(sb, shot)
        golden = _golden_for(sb, shot)
        h = C.stable_hash(prompt, cfg["model"], cfg["steps"], cfg.get("width"), cfg.get("height"), seed,
                          C.file_sha(golden) if golden else None, C.dry_run())
        path = out / f"{shot['id']}.jpg"
        if not force and C.is_fresh(f"keyframe/{shot['id']}", h, path):
            skipped += 1
            continue
        t0 = time.time()
        info: dict = {}
        if C.dry_run():
            placeholder(shot["id"], prompt, path); attempts = 1
        else:
            try:
                (raw, info), attempts = C.with_retries(lambda: generate(prompt, cfg, seed, golden), label=f"keyframe {shot['id']}")
            except C.QuotaError as e:
                C.log_call("keyframes", cfg["model"], shot_id=shot["id"], status="quota")
                print(f"[keyframes] QUOTA: {e}. {done} done; cached frames are kept, re-run after the daily reset.")
                return
            Image.open(io.BytesIO(raw)).convert("RGB").save(path, quality=95)
            time.sleep(cfg.get("sleep_between_s", 0))
        C.mark(f"keyframe/{shot['id']}", h, path)
        C.log_call("keyframes", cfg["model"], shot_id=shot["id"], seed=seed, latency_s=time.time() - t0, attempts=attempts,
                   params={"steps": cfg["steps"], "prompt_chars": len(prompt), **info}, cost_usd=C.price_of("cloudflare_flux", 1),
                   prompt_sha=C.stable_hash(prompt))
        done += 1
        print(f"[keyframes] {shot['id']}: generated")
    print(f"[keyframes] {done} generated, {skipped} cached")


def reference(sb: dict) -> None:
    """Generate several options per character and keep them all, so a golden reference can be chosen."""
    cfg = sb["config"]["keyframe"]
    n = cfg.get("options_per_reference", 4)
    out = C.ensure("reference")
    for ch in sb["characters"]:
        prompt = (f"character reference portrait, {ch['description']}, standing, neutral plain background, "
                  f"full body,front view, natural expression. {sb['style']['style_block']}")
        for k in range(n):
            seed = sb["config"]["seed_base"] + 9000 + k
            path = out / f"{ch['id']}_{k + 1}.jpg"
            if path.exists():
                continue
            t0 = time.time()
            if C.dry_run():
                placeholder(f"s{k + 1:02d}", prompt, path); attempts = 1
            else:
                (raw, _), attempts = C.with_retries(lambda: generate(prompt, cfg, seed, None), label=f"reference {ch['id']}")
                Image.open(io.BytesIO(raw)).convert("RGB").save(path, quality=95)
                time.sleep(cfg.get("sleep_between_s", 0))
            C.log_call("reference", cfg["model"], seed=seed, latency_s=time.time() - t0, attempts=attempts,
                       params={"character": ch["id"], "option": k + 1}, cost_usd=C.price_of("cloudflare_flux", 1))
            print(f"[reference] {path.name}")
    print("[reference] choose one per character and set characters[].golden_reference in storyboard.json")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "reference"], nargs="?", default="run")
    ap.add_argument("--shot", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sb = C.load_storyboard()
    reference(sb) if a.cmd == "reference" else run(sb, a.shot, a.force)


if __name__ == "__main__":
    main()
