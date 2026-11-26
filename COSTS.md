# COSTS.md: measured latency, GPU minutes, list-price equivalent

> Measured from `runs.jsonl` via `make costs` on **2026-11-26** (dry-run and smoke lines excluded).

## 1. Measured per stage (`make costs`)

| Stage | Model(s) | Calls | OK | Quota/fail | Mean latency (s) | Total latency (min) | GPU-min | List-price equiv. (USD) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| narration | gemini-3.8-flash-tts | 31 | 19 | 12 | 14.9 | 7.7 | 0.0 | 0.0238 |
| reference | @cf/black-forest-labs/flux-1-schnell | 8 | 8 | 0 | 15.9 | 2.1 | 0.0 | 0.0200 |
| keyframes | @cf/black-forest-labs/flux-1-schnell | 9 | 9 | 0 | 12.3 | 1.8 | 0.0 | 0.0225 |
| judge | gemini-3.5-flash-lite | 7 | 7 | 0 | 6.4 | 0.7 | 0.0 | 0.0035 |
| music | ACE-Step-1.5 | 6 | 6 | 0 | 11.0 | 1.1 | 1.1 | 0.0106 |
| assemble | ffmpeg | 2 | 2 | 0 | 118.0 | 3.9 | 0.0 | 0.0000 |
| shots | Wan-AI/Wan2.2-TI2V-5B-Diffusers | 9 | 9 | 0 | 449.3 | 67.4 | 67.4 | 0.6627 |
| **total** | | 72 | | | | 84.8 | 68.5 | 0.7431 |

Calls needing a retry: 3 of 72. Cache hits make no model call and are not logged.

## 2. Free-tier limits actually hit (checked 2026-11-25 – 2026-11-26)

| Service | Documented free limit | What I actually hit | Date |
|---|---|---|---|
| Gemini API (text / vision) | Rate-limited free tier | `gemini-3.8-flash` returned HTTP 503 / ReadTimeout; `gemini-2.5-flash` returned HTTP 404 for new keys; `gemini-3.5-flash-lite` succeeded (`200 OK`, ~6.4 s/call) | 2026-11-26 |
| Gemini TTS (`gemini-3.8-flash-tts`) | Rate-limited + daily free tier | Hit HTTP 429 (`status: quota` 12 times) after rapid batches (`sleep_between_s: 2.0`), requiring `21.0 s` spacing and a second project/account key to finish `s07`–`s09` | 2026-11-25 |
| Cloudflare Workers AI (`flux-1-schnell`) | 10,000 Neurons/day (~40+ 1024×1024 4-step images/day) | Completed 17 images (8 reference + 9 keyframes) + smoke test with 0 quota errors | 2026-11-26 |
| Kaggle GPU (`T4 x2`) | ~30 GPU hours/week, phone verification + Internet On required | Python 3.13 base image blocked ACE-Step (`uv` Python 3.11 workaround); `enable_model_cpu_offload()` OOM'd on 15 GB T4 (`enable_sequential_cpu_offload()` fixed it); `68.5` GPU-min used total | 2026-11-26 |
| Coding agent | Antigravity weekly quota | Completed pipeline fixes, frontend studio, and docs within session quota | 2026-11-26 |

## 3. List-price equivalent (`pipeline/pricing.json`)

| Item | Unit price used | Source URL | Date checked |
|---|---|---|---|
| Gemini Flash-Lite (judge) | `$0.0005` / call (~1k input + ~60 output tokens) | https://ai.google.dev/gemini-api/docs/pricing | 2026-11-26 |
| Gemini Flash TTS | `$0.00125` / shot (~5 s audio ≈ 125 output tokens at ~\$10/1M audio tokens) | https://ai.google.dev/gemini-api/docs/pricing | 2026-11-26 |
| Image (Cloudflare Workers AI FLUX.1 schnell) | `$0.0025` / 1024×1024 4-step image (~225 Neurons at \$0.011/1k Neurons) | https://developers.cloudflare.com/workers-ai/platform/pricing/ | 2026-11-26 |
| GPU minute for Wan 2.2 & ACE-Step 1.5 | `$0.009833` / GPU-min (Modal NVIDIA T4 \$0.59/hr ÷ 60) | https://modal.com/pricing | 2026-11-26 |

Total list-price equivalent across all 72 logged calls (including retries/re-takes): **\$0.7431 USD** (Wan 2.2 accounts for **89.2%** of that at \$0.6627). Actual cash spent: **\$0.00**.

## 4. Frontier comparison

No paid frontier video/image/music access (`Omni Flash`, `Nano Banana`, `Lyria 3.5`) was available on this cohort free tier.

## 5. Where the time went

- **Wan 2.2 T4 video generation & Kaggle debugging:** dominated wall-clock time (`67.4 GPU-min` render + setup/OOM debugging; switching `s02`–`s09` from `bfloat16/81f/30steps` to `float16/49f/20steps` cut per-shot time from `34.0 min` to `4.2 min`).
- **Gemini TTS debugging & rate-limit pacing:** ~1.5 hours resolving `F01`/`F02` (verbatim `speech_metadata` + double-wrapped `RIFF/WAVE` + `C2PA`) and waiting through 429 limits.
- **Story, User Test 1, keyframes, ACE-Step, FFmpeg assembly, and web studio:** remaining wall-clock time (`make film` local FFmpeg assembly takes ~2 minutes).
