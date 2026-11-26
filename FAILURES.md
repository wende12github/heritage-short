# FAILURES.md: what broke, what I tried, what fixed it

> Graded: **real** blockers (quota, memory, consistency, language) and how each was resolved or worked around. Log them as they
> happen, with the exact error text and the time; a failure you did not hide is worth more than a clean story. Nothing below has
> happened yet; the watch-list is where to look, not a record.

## Entry format

### F00 Short title (date, stage, shot)
- **Symptom:** exact error or what looked wrong (paste the message; remove secrets)
- **Impact:** what it blocked and for how long
- **Hypotheses and what I tried (in order):** ...
- **Fix or workaround:** ... (commit hash)
- **Evidence:** `runs.jsonl` ts / file / screenshot description
- **Lesson / what I would do first next time:** ...

## Entries

### F01 Gemini 3.8 Flash TTS spoke the English style instruction aloud (2026-11-25, narration, s01–s09)
- **Symptom:** Every narration clip began with an English voice reading `"Say this warmly, gently, and sincerely, with natural unhurried pacing"` before switching to Amharic, inflating clip durations to 10.2–13.1 s for 21–42 chars of Amharic (and using female voice `Kore` instead of a male narrator).
- **Impact:** Radio cut had an unwanted English preamble at the start of every shot and wrong voice gender.
- **Hypotheses and what I tried (in order):** Inspected `pipeline/narration.py` line 25 (`prompt = f"{cfg['style_instruction']}: {text}"`). Confirmed `gemini-3.8-flash-tts` treats `contents[].parts[].text` strictly as a verbatim transcript rather than parsing inline `"Say ...:"` directions.
- **Fix or workaround:** Updated `pipeline/narration.py` (`tts_once`) to keep `parts[0]["text"]` strictly verbatim Amharic, pass `style_instruction` via `speech_metadata` (with automatic fallback to plain `{"text": text}` if the REST endpoint rejects `speech_metadata`), and switched `config.tts.voice` in `storyboard.json` from `"Kore"` to `"Charon"` (male voice) with a clean style descriptor.
- **Evidence:** `runs.jsonl` timestamps `2026-11-25T20:04:42+0300` through `2026-11-25T20:06:15+0300` (`s03` had 21 Amharic chars yet `audio_s: 10.16`).
- **Lesson / what I would do first next time:** Listen to the very first generated shot (`--shot s01`) before generating all shots in a batch.

### F02 Click at start and loud static noise at end of every TTS clip (2026-11-25, narration / radiocut, s01–s09)
- **Symptom:** Every generated narration WAV (`s01.wav`–`s09.wav`) and `radio_cut.mp4` had a click at the start and ~0.16 s of full-scale static noise (`peak = 1.000`) at the end.
- **Impact:** Made every sentence end with a harsh burst of noise in `radio_cut.mp4`.
- **Hypotheses and what I tried (in order):** Inspected trailing 20 ms amplitude windows across all 9 WAVs; found every file started with `0.855–0.997` peak and ended with `1.000` peak. Inspected raw bytes inside `s01.wav` and discovered `gemini-3.8-flash-tts` returned a complete `RIFF....WAVE` file (with `fmt `, `data`, and a trailing 7,656-byte `C2PA` provenance chunk), which `audio.write_pcm_wav()` wrapped inside a *second* WAV header—turning the inner header and the C2PA metadata chunk into audible audio samples.
- **Fix or workaround:** Updated `pipeline/audio.py` (`write_pcm_wav`) to write `RIFF...WAVE` payloads directly to disk without double-wrapping; unwrapped the existing 9 WAVs in `outputs/narration/` locally (0 API calls, preserving C2PA metadata intact) and rebuilt `outputs/final/radio_cut.mp4`.
- **Evidence:** Before unwrapping, `s01.wav` last 200 ms peak was `1.000`; after unwrapping, `ffmpeg` decoded `5.19 s` cleanly with last 200 ms peak `0.00127` and exit code `0`.
- **Lesson / what I would do first next time:** Always check `mimeType` and magic bytes (`RIFF`) before assuming an API returns headerless PCM.

### F03 Gemini 3.8 Flash returning 503 / timeout and Gemini 2.5 Flash 404 for new keys (2026-11-26, smoke / judge)
- **Symptom:** `gemini-3.8-flash` failed with `HTTP 503` in `make smoke` and `HTTP 503` / `ReadTimeout` in `pipeline/judge.py`; `gemini-flash-latest` also returned `503` ("high demand"), and `gemini-2.5-flash` returned `HTTP 404: models/gemini-2.5-flash is no longer available to new users`.
- **Impact:** Blocked running `pipeline/judge.py` to score character consistency.
- **Hypotheses and what I tried (in order):** Listed all 65 models via `GET /v1beta/models` and probed `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-flash-latest`, and `gemini-4-hydrogen`.
- **Fix or workaround:** `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite` both returned `HTTP 200`. Set `GEMINI_TEXT_MODEL=gemini-3.5-flash-lite` in `.env` for `judge.py`.
- **Evidence:** `runs.jsonl` `2026-11-25T20:04:06+0300` (`gemini-3.8-flash` `HTTP 503`) and live model probe on `2026-11-26T02:55` (`gemini-3.5-flash-lite 200`, `gemini-3.1-flash-lite 200`).
- **Lesson / what I would do first next time:** Probe candidate Flash/Lite models with a single short call when the default model hits 503/high demand.

### F04 ACE-Step 1.5 failed on Kaggle Python 3.13 and changed Python API (2026-11-26, music, Kaggle)
- **Symptom:** Running `notebooks/acestep_kaggle.py` on Kaggle failed at `pip install -e ACE-Step-1.5` with `ERROR: Package 'ace-step' requires a different Python: 3.13.16 not in '<3.13,>=3.11'`. Also, `ACE-Step-1.5` replaced `ACEStepPipeline` with `AceStepHandler` + `GenerationParams` + `GenerationConfig` + `generate_music`.
- **Impact:** Blocked music candidate generation on Kaggle.
- **Hypotheses and what I tried (in order):** Checked the `ACE-Step-1.5` inference API and Kaggle's `uv` Python runtime provisioning.
- **Fix or workaround:** Updated `notebooks/acestep_kaggle.py` to detect Python >= 3.13, install `uv`, provision an isolated Python 3.11 `.acestep_venv`, install `ACE-Step-1.5` into it, and run `AceStepHandler(offload_to_cpu=True)` + `generate_music(..., llm_handler=None, thinking=False)` for `c1_cand1..c2_cand3`.
- **Evidence:** Kaggle traceback `ERROR: Package 'ace-step' requires a different Python: 3.13.16 not in '<3.13,>=3.11'` on `2026-11-26`.
- **Lesson / what I would do first next time:** Check `requires-python` in a cloned repo's `pyproject.toml` and provision Python 3.11 via `uv` when Kaggle runs 3.13.

## Watch-list: likely failure points for this stack (not yet observed)

- Model ids from the brief ("Gemini 3.8 Flash TTS") differ from what `GET /models` returns -> `make smoke` lists real ids.
- Gemini TTS free-tier rate limit (429) mid-run; Amharic names/words mispronounced; output voice/length varies per call.
- Cloudflare daily free allowance exhausted before all keyframes exist (`status: quota` in `runs.jsonl`, stage resumes next day).
- `seed` or image-reference fields rejected by the Workers AI endpoint for a given model (pipeline retries without seed and logs it).
- Identity drift of the grandmother across shots; hands/feet artifacts; garbled text inside images.
- Kaggle: phone verification, GPU queue, session timeout, out-of-memory at 704p, bf16 slow/NaN on T4, internet-off datasets.
- ACE-Step 1.5 Python API differs from the notebook adapter; a caption/tempo contradiction gives odd tracks.
- FFmpeg build without libass (subtitles) or without sidechaincompress.
- Free coding agent quota exhausted mid-task; free agent data terms (do not paste private data).
