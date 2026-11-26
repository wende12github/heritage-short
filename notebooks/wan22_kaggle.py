# %% [markdown]
# # Wan 2.2 TI2V-5B image-to-video on Kaggle (2x T4)
#
# Run as a notebook (each `# %%` block is a cell) or `python wan22_kaggle.py`.
# 1. On your machine: `python -m pipeline.shots plan`, then upload `outputs/kaggle/` as a Kaggle dataset
#    (name it e.g. `heritage-jobs`). Notebook settings: Accelerator = GPU T4 x2, Internet = On.
# 2. Run this file. It reads jobs.json, writes shNN.mp4 + shNN.json to /kaggle/working/clips/ as it goes
#    (resume-safe: finished shots are skipped, so a timeout or quota stop loses nothing).
# 3. Download /kaggle/working/clips/ and run `python -m pipeline.shots ingest <folder>`.
#
# UNVERIFIED (written without GPU access; test with ONE shot first and log what differs in FAILURES.md):
#  * the diffusers class/args for Wan2.2-TI2V-5B image-to-video (check the model card)
#  * T4 has no native bfloat16: if bf16 is very slow or gives NaNs, set config.video.dtype to "float16"
#  * peak VRAM at 480p with CPU offload; lower width/height/num_frames if you hit out-of-memory
# Draft low (480x480, 81 frames ~ 3.4 s at 24 fps), finish only the shots you keep.
# %%
import json, os, subprocess, sys, time
from pathlib import Path

INPUT = next((p.parent for p in Path("/kaggle/input").rglob("jobs.json")), Path(".")) if Path("/kaggle/input").exists() else Path(".")
OUT = Path("/kaggle/working/clips") if Path("/kaggle/working").exists() else Path("clips")
OUT.mkdir(parents=True, exist_ok=True)
WORKERS = int(os.environ.get("WAN_WORKERS", "1"))      # 2 = one process per T4 (needs ~2x system RAM)
MAX_SHOTS = int(os.environ.get("WAN_MAX_SHOTS", "0"))  # set 1 to test one shot first, 0 for all


def install():
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers", "transformers", "accelerate",
                    "imageio", "imageio-ffmpeg", "sentencepiece", "ftfy"], check=True)


def worker(idx: int, n: int):
    import torch
    from diffusers import WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image

    all_jobs = json.loads((INPUT / "jobs.json").read_text())["jobs"]
    if MAX_SHOTS > 0:
        all_jobs = all_jobs[:MAX_SHOTS]
    jobs = all_jobs[idx::n]
    if not jobs:
        return
    v0 = jobs[0]["video"]
    dtype = torch.float16 if v0.get("dtype") == "float16" else torch.bfloat16
    pipe = WanImageToVideoPipeline.from_pretrained(v0["model"], torch_dtype=dtype)
    pipe.enable_model_cpu_offload()
    try:
        pipe.vae.enable_tiling()
    except Exception:
        pass
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    for job in jobs:
        sid, v = job["shot"], job["video"]
        mp4, side = OUT / f"{sid}.mp4", OUT / f"{sid}.json"
        if side.exists() and json.loads(side.read_text()).get("input_hash") == job["input_hash"]:
            print(f"[{sid}] already done, skipping"); continue
        image = load_image(str(INPUT / job["keyframe"])).resize((v["width"], v["height"]))
        gen = torch.Generator(device="cpu").manual_seed(job["seed"])
        torch.cuda.reset_peak_memory_stats()
        t0, attempts = time.time(), 0
        for attempts in (1, 2, 3):                      # max three attempts per shot, then move on
            try:
                frames = pipe(image=image, prompt=job["motion_prompt"], negative_prompt=v.get("negative_prompt", ""),
                              height=v["height"], width=v["width"], num_frames=v["num_frames"],
                              num_inference_steps=v["steps"], guidance_scale=v.get("guidance_scale", 5.0),
                              generator=gen).frames[0]
                break
            except torch.cuda.OutOfMemoryError:
                torch.cuda.empty_cache(); print(f"[{sid}] OOM on attempt {attempts}")
        else:
            print(f"[{sid}] FAILED after 3 attempts; the film will use the Ken Burns fallback"); continue
        export_to_video(frames, str(mp4), fps=v["fps"])
        dt = time.time() - t0
        side.write_text(json.dumps({
            "shot": sid, "model": v["model"], "seed": job["seed"], "input_hash": job["input_hash"],
            "width": v["width"], "height": v["height"], "num_frames": v["num_frames"], "steps": v["steps"],
            "dtype": str(dtype).split(".")[-1], "gpu": gpu, "latency_s": round(dt, 1),
            "gpu_minutes": round(dt / 60, 2), "attempts": attempts,
            "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2)}, indent=2))
        print(f"[{sid}] done in {dt:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--worker":
        worker(int(sys.argv[2]), int(sys.argv[3]))
    else:
        install()
        if WORKERS == 1:
            worker(0, 1)
        else:
            ps = [subprocess.Popen([sys.executable, __file__, "--worker", str(i), str(WORKERS)],
                                   env={**os.environ, "CUDA_VISIBLE_DEVICES": str(i)}) for i in range(WORKERS)]
            [p.wait() for p in ps]
        print("Done. Download", OUT, "then: python -m pipeline.shots ingest <folder>")
