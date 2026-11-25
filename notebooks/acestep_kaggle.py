# %% [markdown]
# # ACE-Step 1.5 score candidates on Kaggle/Colab
#
# 1. On your machine: `python -m pipeline.music plan`, upload `outputs/kaggle/music_jobs.json` to the notebook.
# 2. Run this file; it writes <cue>_candN.wav + .json to ./candidates/.
# 3. Download, then `python -m pipeline.music register candidates/*.wav`, listen to them quietly UNDER the
#    narration, and `python -m pipeline.music choose c1 candidates/c1_cand2.wav --why "..."`.
#
# UNVERIFIED: the Python call in `generate()` is written against ACE-Step's documented pipeline interface
# (ACEStepPipeline: prompt, lyrics, audio_duration, infer_step, guidance_scale, manual_seeds). Version 1.5 may
# have changed names/arguments. Read https://github.com/ACE-Step/ACE-Step-1.5 and adapt ONLY that function.
# If it fights you, use the repo's own Gradio UI/CLI with the same captions from music_jobs.json, name the WAVs
# <cue>_candN.wav and carry on from step 3. Record what happened in FAILURES.md either way.
# Tempo and key go in their own fields, not in the caption. Keep instrumental=True for a score.
# %%
import json, subprocess, sys, time
from pathlib import Path

JOBS = Path("music_jobs.json")
OUT = Path("candidates"); OUT.mkdir(exist_ok=True)
STEPS = 8   # 1.5 is distilled; adjust to the repo's recommended steps


def setup():
    if not Path("ACE-Step-1.5").exists():
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5"], check=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-e", "ACE-Step-1.5"], check=True)


def generate(pipe, job, out_path):
    """ADAPT THIS FUNCTION to the real ACE-Step 1.5 API."""
    prompt = job["caption"]          # tempo/key: pass job["bpm"], job["key"] via the API's own fields if 1.5 has them
    lyrics = "[instrumental]" if job["instrumental"] else ""
    pipe(prompt=prompt, lyrics=lyrics, audio_duration=job["duration_s"], infer_step=STEPS,
         guidance_scale=15.0, manual_seeds=[job["seed"]], save_path=str(out_path))


if __name__ == "__main__":
    setup()
    import torch
    from acestep.pipeline_ace_step import ACEStepPipeline      # name may differ in 1.5
    pipe = ACEStepPipeline(dtype="bfloat16", torch_compile=False, cpu_offload=True)
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    for job in json.loads(JOBS.read_text())["jobs"]:
        wav = OUT / f"{job['candidate']}.wav"
        if wav.exists():
            continue
        t0 = time.time()
        generate(pipe, job, wav)
        dt = time.time() - t0
        wav.with_suffix(".json").write_text(json.dumps({
            "model": "ACE-Step-1.5", "caption": job["caption"], "bpm": job["bpm"], "key": job["key"], "seed": job["seed"],
            "steps": STEPS, "gpu": gpu, "latency_s": round(dt, 1), "gpu_minutes": round(dt / 60, 2)}, indent=2))
        print(job["candidate"], f"{dt:.0f}s")
