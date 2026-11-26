# %% [markdown]
# # ACE-Step 1.5 score candidates on Kaggle/Colab
#
# 1. On your machine: `python -m pipeline.music plan`, upload `outputs/kaggle/` as a Kaggle dataset.
# 2. Run this file; it writes <cue>_candN.wav + .json to /kaggle/working/candidates/.
# 3. Download, then `python -m pipeline.music register candidates/*.wav`, listen to them quietly UNDER the
#    narration, and `python -m pipeline.music choose c1 candidates/c1_cand2.wav --why "..."`.
#
# Adapted for Kaggle Python 3.13 (creates a Python 3.11 venv via `uv`) and ACE-Step 1.5's
# AceStepHandler + GenerationParams + GenerationConfig + generate_music API (no LLM planner needed).
# %%
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

JOBS = next(Path("/kaggle/input").rglob("music_jobs.json"), Path("music_jobs.json")) if Path("/kaggle/input").exists() else Path("music_jobs.json")
OUT = Path("/kaggle/working/candidates") if Path("/kaggle/working").exists() else Path("candidates")
OUT.mkdir(parents=True, exist_ok=True)
REPO = Path("ACE-Step-1.5").resolve()
VENV_PY = Path(".acestep_venv/bin/python").absolute()  # keep venv symlink intact so pyvenv.cfg activates!
STEPS = 8


WORKER_CODE = r'''
import json, shutil, sys, time
from pathlib import Path
import torch
from acestep.handler import AceStepHandler
from acestep.inference import GenerationConfig, GenerationParams, generate_music

jobs_path = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
repo_dir = Path(sys.argv[3])
steps = int(sys.argv[4])

dit = AceStepHandler()
dit.initialize_service(project_root=str(repo_dir), config_path="acestep-v15-turbo", device="cuda", offload_to_cpu=True)
gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"

tmp_dir = out_dir / "_tmp"
tmp_dir.mkdir(parents=True, exist_ok=True)

for job in json.loads(jobs_path.read_text())["jobs"]:
    wav = out_dir / f"{job['candidate']}.wav"
    if wav.exists():
        print(f"[{job['candidate']}] already done, skipping")
        continue
    params = GenerationParams(
        caption=job["caption"],
        lyrics="[Instrumental]" if job.get("instrumental", True) else "",
        bpm=int(job["bpm"]),
        keyscale=job.get("key", "auto"),
        duration=int(job["duration_s"]),
        inference_steps=steps,
        seed=int(job["seed"]),
        thinking=False,
    )
    cfg = GenerationConfig(batch_size=1, audio_format="wav", use_random_seed=False, seeds=[int(job["seed"])])
    t0 = time.time()
    res = generate_music(dit_handler=dit, llm_handler=None, params=params, config=cfg, save_dir=str(tmp_dir))
    dt = time.time() - t0
    if not res.success or not res.audios:
        raise RuntimeError(f"{job['candidate']} failed: {res.error}")
    gen_path = Path(res.audios[0]["path"])
    shutil.move(str(gen_path), str(wav))
    wav.with_suffix(".json").write_text(json.dumps({
        "model": "ACE-Step-1.5",
        "caption": job["caption"],
        "bpm": job["bpm"],
        "key": job["key"],
        "seed": job["seed"],
        "steps": steps,
        "gpu": gpu,
        "latency_s": round(dt, 1),
        "gpu_minutes": round(dt / 60, 2),
    }, indent=2))
    print(f"[{job['candidate']}] done in {dt:.0f}s -> {wav}")
'''


def setup() -> Path:
    if not REPO.exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5", str(REPO)], check=True)
    if sys.version_info < (3, 13):
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", str(REPO)], check=True)
        return Path(sys.executable)
    if not VENV_PY.exists():
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "uv"], check=True)
        subprocess.run(["uv", "venv", "--python", "3.11", str(VENV_PY.parent.parent)], check=True)
        subprocess.run(["uv", "pip", "install", "--python", str(VENV_PY), "-e", str(REPO)], check=True)
    return VENV_PY


if __name__ == "__main__":
    assert JOBS.exists(), f"music_jobs.json not found (checked {JOBS})"
    py = setup()
    worker_file = Path("_acestep_worker.py")
    worker_file.write_text(WORKER_CODE, encoding="utf-8")
    env = {**os.environ, "MPLBACKEND": "Agg"}
    subprocess.run([str(py), str(worker_file), str(JOBS.resolve()), str(OUT.resolve()), str(REPO), str(STEPS)], check=True, env=env)
    print("Done. Download", OUT, "then run: python -m pipeline.music register <dir>/*.wav")
