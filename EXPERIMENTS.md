# EXPERIMENTS.md: hypothesis -> change -> result

> Ten measured experiments backed by `runs.jsonl`, `outputs/clips/*.json`, `outputs/mix/loudness_report.json`, and `judge.py` scores.

Entry format: **Hypothesis** | **Change (one thing)** | **Held fixed** | **Measure** | **Result** | **Decision and why**

---

### E01 Style block pivot: 2D gouache illustration vs. 35mm live-action photography
- **Hypothesis:** Replacing `"hand-painted gouache illustration"` + `"character reference sheet, full body"` with `"cinematic 35mm live-action film still"` + `"character reference portrait, waist up"` removes flat cartoon rendering and watermarks (`Mea.H` on v1 `yonas_1.jpg`).
- **Change:** `style.style_block`, `characters[0].description`, and `keyframes.py` reference prompt template. **Fixed:** Cloudflare `@cf/black-forest-labs/flux-1-schnell`, `steps: 4`, `1024x1024`, seeds `11000–11003`.
- **Measure:** Visual inspection of `outputs/reference/yonas_1..4.jpg` (`2026-11-26T00:10` vs `00:33–00:34`) and `judge.py` `same_style`.
- **Result:** All 4 v2 portraits rendered clean photographic skin/hoodie textures with zero signatures; `judge.py` scored `same_style = 5/5` on all 7 character shots.
- **Decision and why:** Adopted 35mm live-action style and `yonas_1.jpg` as `golden_reference`.

### E02 Fixed `{yonas}` character expansion vs. free-form re-description
- **Hypothesis:** Expanding `{yonas}` identically across all character shots maintains high identity consistency (`>= 4/5`) even on a text-only image backend.
- **Change:** Identical `{yonas}` template string (skin tone, tapered curly Afro, thin mustache/stubble, charcoal hoodie over white tee) in `s01, s03, s04, s06, s07, s08, s09`. **Fixed:** `flux-1-schnell`, `steps: 4`, `style_block`.
- **Measure:** `python -m pipeline.judge` (`gemini-3.5-flash-lite`, `2026-11-26T04:06`) against `yonas_1.jpg` + eye spot-check.
- **Result:** Mean **`same_person = 4.71 / 5.0`** (`5/5` on `s03, s04, s06, s08, s09`; `4/5` on `s01, s07`) and **`same_style = 5.00 / 5.0`**.
- **Decision and why:** Kept text-anchored `{yonas}` expansion; no LoRA needed for a single-character 9-shot short.

### E03 Cloudflare `flux-1-schnell` `seed` parameter handling
- **Hypothesis:** Workers AI `flux-1-schnell` may reject `seed`; automatic fallback without `seed` prevents stage failure at the cost of non-seeded variance.
- **Change:** `keyframes.py` catches `seed` rejection and retries without `seed`, logging `seed_sent`. **Fixed:** `model`, `steps: 4`, `1024x1024`.
- **Measure:** `runs.jsonl` `params.seed_sent` and `params.reference_used` across `s01`–`s09` (`2026-11-26T00:41:47`–`00:43:25`).
- **Result:** `9/9` keyframes succeeded (`mean latency 12.3 s`), all with `seed_sent: false` and `reference_used: false`.
- **Decision and why:** Kept `flux-1-schnell` with automatic `seed`-strip fallback and noted the reproducibility caveat in `ARCHITECTURE.md` / `FAILURES.md`.

### E04 Gemini 3.8 Flash TTS: inline style prefix vs. `speech_metadata` + male voice (`Charon`)
- **Hypothesis:** `gemini-3.8-flash-tts` reads `parts[].text` verbatim; moving `style_instruction` to `speech_metadata` and switching `Kore` -> `Charon` eliminates the English preamble and halves clip durations.
- **Change:** `pipeline/narration.py` (`speech_metadata` + verbatim Amharic `text`) and `voice: "Charon"`. **Fixed:** `gemini-3.8-flash-tts`, `am-ET`, same 9 Amharic lines.
- **Measure:** `audio_s` in `runs.jsonl` (`20:04–20:06` `Kore` vs `20:15–22:32` `Charon`) and `radio_cut.mp4` duration.
- **Result:** `Kore` with inline prompt ran `10.16–13.07 s/shot` (`radio_cut.mp4` = `95.0 s`); `Charon` with `speech_metadata` ran `3.39–6.57 s/shot` (`radio_cut.mp4` = `67.0 s`) with pure Amharic speech.
- **Decision and why:** Kept `speech_metadata` + `Charon` (`F01`).

### E05 Unwrapping Gemini TTS `RIFF/WAVE` + `C2PA` vs. double-wrapped PCM
- **Hypothesis:** Writing Gemini's `RIFF....WAVE` payload directly removes the start click and trailing `C2PA` static burst while preserving provenance.
- **Change:** `pipeline/audio.py` (`write_pcm_wav` detects `RIFF`/`WAVE` header and writes raw bytes directly). **Fixed:** Existing 9 WAVs in `outputs/narration/` (`0` new API calls).
- **Measure:** First-40 ms and last-200 ms peak amplitude decoded via FFmpeg before vs. after unwrapping.
- **Result:** Last-200 ms peak dropped from `1.000` (all 9 files) to `0.0008–0.0738`; `s01.wav` start-40 ms peak dropped `0.855 -> 0.102`; `7,656 B` `C2PA` chunk stayed intact (`F02`).
- **Decision and why:** Merged into `pipeline/audio.py` permanently.

### E06 Gemini TTS free-tier pacing (`sleep_between_s: 2.0` vs `21.0`)
- **Hypothesis:** Spacing TTS calls by `21.0 s` keeps requests under a 3-RPM free limit, though daily caps still require resuming across keys/windows.
- **Change:** `config.tts.sleep_between_s` from `2.0` to `21.0` in `storyboard.json`. **Fixed:** `gemini-3.8-flash-tts`, `Charon`.
- **Measure:** `status` counts and timestamps in `runs.jsonl`.
- **Result:** Total narration log shows `19 OK` vs `12 quota`; spacing alone did not bypass the daily cap on the first key, so switching to a second account key finished `s07–s09` at `22:31:25–22:32:20` (`25.7–35.3 s` latency).
- **Decision and why:** Kept `sleep_between_s: 21.0` plus `manifest.json` per-shot caching so interrupted runs resume with zero wasted calls.

### E07 Wan 2.2 TI2V-5B offload & precision on Kaggle T4: `model_cpu_offload` vs `sequential_cpu_offload` + `float16`
- **Hypothesis:** `enable_sequential_cpu_offload()` fits Wan 2.2 into 15 GB T4 VRAM without OOM, and switching `bfloat16 / 81f / 30 steps` (`s01`) to `float16 / 49f / 20 steps` (`s02–s09`) cuts runtime >4× without black frames.
- **Change:** First `enable_model_cpu_offload()` -> `enable_sequential_cpu_offload()` + `vae.enable_slicing()`; then `bfloat16/81f/30` (`s01`) -> `float16/49f/20` (`s02–s09`). **Fixed:** `480x480`, `Tesla T4`, `guidance_scale: 5.0`.
- **Measure:** `outputs/clips/s01..s09.json` (`latency_s`, `peak_vram_gb`) and FFmpeg first-frame mean RGB brightness (`0` = black).
- **Result:** `enable_model_cpu_offload()` OOM'd on all 9 shots (`F05`). With `sequential_cpu_offload`: `s01` (`bf16/81f/30`) took `2040.8 s` (`34.01 GPU-min`, `5.81 GB` VRAM); `s02–s09` (`fp16/49f/20`) took **`248.7–256.0 s` (`4.14–4.27 GPU-min`, `2.12–2.13 GB` VRAM)** — an **8.1× speedup** with zero NaNs (`first_frame_mean = 34.2–106.5`).
- **Decision and why:** Used `float16 / 49f / 20 steps` for `s02–s09` to finish all 9 clips well before the deadline.

### E08 ACE-Step 1.5 candidate auditioning (`thinking=False` on T4)
- **Hypothesis:** Running `AceStepHandler` (`acestep-v15-turbo`, `offload_to_cpu=True`, `llm_handler=None`) generates 40 s instrumental cues fast on T4, and measured LUFS/LRA predicts which candidate sits cleanest under narration.
- **Change:** Generated 3 seeds per cue (`c1_cand1..3`, `c2_cand1..3`, 8 steps). **Fixed:** `caption`, `bpm`, `keyscale`, `duration_s: 40`.
- **Measure:** `runs.jsonl` `latency_s` (`10.3–14.0 s`), FFmpeg `loudnorm` measurement + RMS, and listening under `narration.wav`.
- **Result:** `c1_cand1` (`-19.14 LUFS`, `RMS 0.083`, `LRA 5.3`) was quieter and steadier than `c1_cand2` (`-15.78 LUFS`, `LRA 7.0`) and `c1_cand3` (`-15.09 LUFS`, `LRA 12.9`); `c2_cand1` (`-14.56 LUFS`, `LRA 12.4`) provided a warmer F-major dawn lift (`choices.jsonl`).
- **Decision and why:** Selected `c1_cand1.wav` and `c2_cand1.wav`.

### E09 Music pre-level & ducking: hardcoded `volume=0.35` (`-31.1 LUFS`) vs `music_prelevel_lufs: -20`
- **Hypothesis:** Removing `radiocut.py`'s hardcoded `volume=0.35` (which dropped `-22.04 LUFS` temp track to `-31.1 LUFS`) and unifying on `config.mix.music_prelevel_lufs = -20` makes the score audible between sentences while sidechain ducking keeps narration clear.
- **Change:** `pipeline/radiocut.py` uses `audio.gain_to(..., music_prelevel_lufs)` and `storyboard.json` `music_prelevel_lufs: -24 -> -20`. **Fixed:** `narration_prelevel_lufs: -16`, `duck_threshold: 0.02`, `duck_ratio: 6`.
- **Measure:** Listening test on `radio_cut.mp4` + `outputs/mix/loudness_report.json` on final assembly.
- **Result:** User listening confirmed music became clearly audible without masking voice; final two-pass `loudnorm` measured **`-14.47 LUFS` integrated** and **`-0.99 dBTP` true peak** (`LRA 6.5 LU`).
- **Decision and why:** Kept `-20 LUFS` prelevel across both `radiocut.py` and `audio.mix_all`.

### E10 Input-hash caching & single-shot regeneration (`s01` User Test 1 fix + `make test`)
- **Hypothesis:** `outputs/manifest.json` input hashing allows editing one narration line in `storyboard.json` and regenerating only that single shot.
- **Change:** Edited `s01.narration.text` (`"ችግሮችን"` -> `"ችግሮች"`) after User Test 1 and re-ran `narration --shot s01`. **Fixed:** `s02–s09` narration, all 9 keyframes, all 9 Wan clips.
- **Measure:** `runs.jsonl` entry count on `2026-11-26T00:02:43+0300` + `tests/test_pipeline.py` (`test_2_rerun_makes_no_new_model_calls`, `test_3_editing_one_shot_regenerates_only_that_shot`).
- **Result:** Exactly 1 new TTS call (`s01`, `chars: 30`, `audio_s: 4.55`) was logged (`s02–s09` stayed cached); all 10 offline unit tests passed (`156.976 s`).
- **Decision and why:** Confirmed stage-boundary caching works for the live walkthrough demo.

---

## Practices tested (feeds the report)

| Suggested practice | Did it beat my instinct? | Evidence |
|---|---|---|
| JSON contract between stages (`storyboard.json`) | **Yes** | Allowed switching style (`E01`), fixing 1 Amharic word (`E10`), and swapping audio levels (`E09`) in data without rewriting assembly code. |
| Reference sheet before keyframes (`make reference`) | **Yes** | Caught the unintended 2D cartoon look on the first batch (`00:10`) before spending quota on 9 keyframes; v2 `yonas_1.jpg` anchored `4.71/5` identity (`E01`, `E02`). |
| Log every call (`runs.jsonl`) | **Yes** | Immediately exposed the English TTS preamble bug (`audio_s: 12.0` for 31 chars in `F01`), `seed_sent: false` (`E03`), and the 8.1× `fp16` speedup (`E07`). |
| Relying on `bfloat16` / `enable_model_cpu_offload` defaults on T4 | **Did not work as assumed** | Default `model_cpu_offload` OOM'd at step 0 (`F05`) and `bfloat16/81f` took `34.0 min` for one shot (`s01`), forcing a switch to `sequential_cpu_offload` + `float16/49f/20` (`E07`). |
