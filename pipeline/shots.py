"""Moving-shots stage: Wan 2.2 TI2V-5B image-to-video, run on a free Kaggle/Colab GPU.

The GPU does not live on your machine, so this stage is a plan -> (GPU notebook) -> ingest loop:

  python -m pipeline.shots plan      list shots whose clip is missing or stale, write
                                     outputs/kaggle/jobs.json and copy their keyframes next to it
  (upload outputs/kaggle/ to Kaggle as a dataset, run notebooks/wan22_kaggle.py, download clips/)
  python -m pipeline.shots ingest DIR   copy clips + sidecars into outputs/clips/, log latency/GPU-minutes
  python -m pipeline.shots status    which shots will use a real clip, which fall back to Ken Burns

A clip is "fresh" only if its sidecar's input hash equals the hash of the CURRENT keyframe,
motion prompt, seed and video params. Change one keyframe prompt and only that shot's clip goes stale.
Stale or missing clips never block the film: assemble.py uses a Ken Burns pan/zoom of the keyframe.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from . import common as C


def expected_hash(sb: dict, shot: dict) -> str | None:
    kf = C.OUT / "keyframes" / f"{shot['id']}.jpg"
    if not kf.exists():
        return None
    v = sb["config"]["video"]
    return C.stable_hash(C.file_sha(kf), shot["motion_prompt"], C.seed_for(sb, shot), v)


def clip_state(sb: dict, shot: dict) -> str:
    """'fresh' | 'stale' | 'missing' | 'no_keyframe'"""
    exp = expected_hash(sb, shot)
    if exp is None:
        return "no_keyframe"
    clip = C.OUT / "clips" / f"{shot['id']}.mp4"
    side = C.OUT / "clips" / f"{shot['id']}.json"
    if not clip.exists() or not side.exists():
        return "missing"
    return "fresh" if json.loads(side.read_text()).get("input_hash") == exp else "stale"


def plan(sb: dict, force: bool = False) -> list[dict]:
    kdir = C.ensure("kaggle", "keyframes")
    jobs = []
    for shot in sb["shots"]:
        st = clip_state(sb, shot)
        if st == "no_keyframe" or (st == "fresh" and not force):
            continue
        shutil.copy(C.OUT / "keyframes" / f"{shot['id']}.jpg", kdir / f"{shot['id']}.jpg")
        jobs.append({"shot": shot["id"], "state": st, "keyframe": f"keyframes/{shot['id']}.jpg",
                     "motion_prompt": shot["motion_prompt"], "seed": C.seed_for(sb, shot),
                     "input_hash": expected_hash(sb, shot), "video": sb["config"]["video"]})
    (C.OUT / "kaggle" / "jobs.json").write_text(json.dumps({"jobs": jobs}, indent=2), encoding="utf-8")
    print(f"[shots] {len(jobs)} clip job(s) planned -> outputs/kaggle/jobs.json "
          f"({', '.join(j['shot'] for j in jobs) or 'nothing to do'})")
    return jobs


def ingest(src_dir: Path, sb: dict) -> None:
    dst = C.ensure("clips")
    n = 0
    for side in sorted(src_dir.glob("s*.json")):
        mp4 = side.with_suffix(".mp4")
        if not mp4.exists():
            continue
        meta = json.loads(side.read_text())
        shutil.copy(mp4, dst / mp4.name)
        shutil.copy(side, dst / side.name)
        C.log_call("shots", meta.get("model", sb["config"]["video"]["model"]), shot_id=side.stem, seed=meta.get("seed"),
                   latency_s=meta.get("latency_s", 0.0), gpu_minutes=meta.get("gpu_minutes", 0.0),
                   params={k: meta.get(k) for k in ("width", "height", "num_frames", "steps", "dtype", "gpu", "peak_vram_gb")},
                   cost_usd=C.price_of("wan22_gpu", meta.get("gpu_minutes", 0.0)), input_hash=meta.get("input_hash"),
                   attempts=meta.get("attempts", 1))
        n += 1
    print(f"[shots] ingested {n} clip(s)")


def status(sb: dict) -> dict[str, str]:
    st = {s["id"]: clip_state(sb, s) for s in sb["shots"]}
    for sid, v in st.items():
        print(f"[shots] {sid}: {'Wan clip' if v == 'fresh' else 'Ken Burns fallback (' + v + ')'}")
    return st


def run(sb: dict) -> None:
    plan(sb)
    status(sb)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "ingest", "status"], nargs="?", default="plan")
    ap.add_argument("dir", nargs="?")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    sb = C.load_storyboard()
    if a.cmd == "plan":
        plan(sb, a.force)
    elif a.cmd == "ingest":
        ingest(Path(a.dir), sb)
    else:
        status(sb)


if __name__ == "__main__":
    main()
