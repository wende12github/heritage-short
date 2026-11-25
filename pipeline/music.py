"""Music stage (ACE-Step 1.5 runs on Kaggle/Colab; this file plans jobs and registers results).

  python -m pipeline.music plan                 write outputs/kaggle/music_jobs.json (captions, bpm, key, seeds)
  python -m pipeline.music register FILES...    copy generated WAVs into outputs/music/candidates/<cue>/
  python -m pipeline.music choose CUE FILE --why "..."   pick the score for a cue (reason is logged)
  python -m pipeline.music temp                 offline synthetic temp track (used by the radio cut)

Spotting note -> caption is in storyboard.json (music.cues). Tempo and key live in their own
fields, NOT in the caption, because contradictions between them are a common failure.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from . import audio, common as C


def make_temp_track(seconds: float = 60, out: Path | None = None) -> Path:
    """Soft synthetic pad (A minor, slow LFO). A TEMP TRACK only: not the film's original score."""
    out = out or C.OUT / "music" / "temp_track.wav"
    sr = audio.SR
    t = np.linspace(0, seconds, int(seconds * sr), endpoint=False)
    freqs = [110.0, 164.81, 220.0, 261.63, 329.63]           # A2 E3 A3 C4 E4
    sig = np.zeros_like(t)
    for i, f in enumerate(freqs):
        lfo = 0.6 + 0.4 * np.sin(2 * np.pi * (0.05 + 0.013 * i) * t + i)
        sig += lfo * np.sin(2 * np.pi * f * t) / (i + 1.5)
    sig *= 0.25 / np.max(np.abs(sig))
    out.parent.mkdir(parents=True, exist_ok=True)
    audio.write_wav(out, np.stack([sig, sig], axis=1).astype(np.float32))
    return out


def plan(sb: dict) -> Path:
    n = sb["music"].get("candidates_per_cue", 3)
    jobs = []
    for cue in sb["music"]["cues"]:
        for k in range(n):
            jobs.append({
                "cue": cue["id"], "candidate": f"{cue['id']}_cand{k + 1}", "caption": cue["caption"],
                "bpm": cue["bpm"], "key": cue["key"], "instrumental": cue["instrumental"],
                "duration_s": cue.get("duration_s", 40),
                "seed": sb["config"]["seed_base"] + 5000 + 10 * sb["music"]["cues"].index(cue) + k,
            })
    out = C.ensure("kaggle") / "music_jobs.json"
    out.write_text(json.dumps({"hash": C.stable_hash(jobs), "jobs": jobs}, indent=2), encoding="utf-8")
    print(f"[music] wrote {len(jobs)} candidate jobs to {out.relative_to(C.ROOT)}; run notebooks/acestep_kaggle.py")
    return out


def register(files: list[str], sidecar_dir: str | None = None) -> None:
    for f in files:
        p = Path(f)
        cue = p.stem.split("_cand")[0]
        dest = C.ensure("music", "candidates", cue) / p.name
        shutil.copy(p, dest)
        side = p.with_suffix(".json")
        meta = json.loads(side.read_text()) if side.exists() else {}
        C.log_call("music", meta.get("model", "ACE-Step-1.5"), params={k: meta.get(k) for k in ("caption", "bpm", "key", "steps")},
                   seed=meta.get("seed"), latency_s=meta.get("latency_s", 0.0),
                   gpu_minutes=meta.get("gpu_minutes", 0.0), shot_id=None, cue=cue, candidate=p.stem,
                   price_key="acestep_gpu")
        print(f"[music] registered {p.name} -> {dest.relative_to(C.ROOT)}")


def choose(cue: str, file: str, why: str) -> None:
    src = Path(file)
    dest = C.ensure("music", "chosen") / f"{cue}.wav"
    audio.write_wav(dest, audio.read_audio(src))
    rec = {"cue": cue, "file": src.name, "why": why}
    log = C.ensure("music") / "choices.jsonl"
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[music] chose {src.name} for {cue}. Now write the reason in EXPERIMENTS.md: {why}")


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    sub.add_parser("temp")
    r = sub.add_parser("register"); r.add_argument("files", nargs="+")
    c = sub.add_parser("choose"); c.add_argument("cue"); c.add_argument("file"); c.add_argument("--why", required=True)
    a = ap.parse_args()
    if a.cmd == "plan":
        plan(C.load_storyboard())
    elif a.cmd == "temp":
        print(f"[music] temp track at {make_temp_track()}")
    elif a.cmd == "register":
        register(a.files)
    else:
        choose(a.cue, a.file, a.why)


if __name__ == "__main__":
    main()
