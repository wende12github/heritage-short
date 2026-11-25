# EXPERIMENTS.md: hypothesis -> change -> result

> Graded: at least **ten** logged experiments with hypotheses, comparisons backed by evidence in text or logs, and reasons for
> each choice. Rules that make them honest: change **one thing**, keep the seed fixed, log every call (it is automatic in
> `runs.jsonl`), and write the result even when it surprised you. Entries E01-E11 are **planned, not run**: each has a
> hypothesis and a method. Replace `TODO` with your measured result and delete any experiment you do not run.
> Evidence can be `runs.jsonl` lines (cite the `ts`), `judge` scores, timings from `make costs`, or listener counts.

Entry format: **Hypothesis** | **Change (one thing)** | **Held fixed** | **Measure** | **Result** | **Decision and why**

---

### E01 Style block on every prompt reduces style drift
- Hypothesis: attaching the same `style_block` to every keyframe prompt raises the judge's `same_style` score vs shot-specific styling.
- Change: with vs without `style.style_block` (edit `compose_prompt` flag or temporarily blank the block). Fixed: seeds, model, steps, shots s02/s05/s09.
- Measure: `python -m pipeline.judge` mean `same_style` (and your own 1-5 rating of 3 frames).
- Result: TODO. Decision: TODO

### E02 Fixed character description beats re-describing
- Hypothesis: expanding `{grandmother}` to one fixed description gives higher `same_person` than free-writing the character each shot.
- Change: placeholder expansion vs hand-written variations. Fixed: seed, steps. Measure: judge `same_person` over shots with the character.
- Result: TODO. Decision: TODO

### E03 Golden reference (image conditioning) vs text only
- Hypothesis: FLUX.2 klein conditioned on the golden reference beats FLUX.1 schnell text-only on identity.
- Change: `config.keyframe.model` schnell -> flux-2-klein + `golden_reference`. Only if klein works on your free tier; if not, record why in FAILURES.md.
- Measure: judge `same_person`; latency per image from `runs.jsonl`. Result: TODO. Decision: TODO

### E04 Fixed vs varied seed across shots
- Hypothesis: a fixed seed (same noise) for a recurring character improves similarity but hurts composition variety.
- Change: `shots[].seed` identical vs different. Measure: judge scores + your note on composition. Result: TODO

### E05 Steps 2 / 4 / 8 on the keyframe model
- Hypothesis: 4 steps is the knee; 8 adds latency without visible gain on a distilled model.
- Change: `config.keyframe.steps`. Fixed: prompt, seed, 3 shots. Measure: latency (`runs.jsonl`), blind pick of 3 pairs (n people). Result: TODO

### E06 Wan draft resolution and frames: 480 vs 704
- Hypothesis: 480x480 drafts are 2x+ faster and good enough to judge motion; finals only for kept shots.
- Change: `config.video.width/height`. Measure: `latency_s`, `peak_vram_gb` in clip sidecars/`runs.jsonl`; artifacts by eye. Result: TODO

### E07 Motion prompt: minimal vs full formula
- Hypothesis: for image-to-video, "motion + camera only" gives fewer artifacts than the full subject/environment/style formula.
- Change: `shots[].motion_prompt` style. Fixed: keyframe, seed. Measure: artifacts counted on 3 shots (flicker, morphing, face drift). Result: TODO

### E08 bfloat16 vs float16 on a T4
- Hypothesis: fp16 is faster on T4 (no native bf16) but risks NaNs/black frames.
- Change: `config.video.dtype`. Measure: seconds per clip, failures. Result: TODO. (Record real errors in FAILURES.md.)

### E09 Wan clip vs Ken Burns on the same keyframe (blind preference)
- Hypothesis: viewers prefer Wan motion for close-ups but not for wide establishing shots.
- Change: segment source. Measure: blind A/B with at least 5 people, per shot size. Result: TODO. (Also counts as ceiling work.)

### E10 ACE-Step caption detail and candidate choice
- Hypothesis: a caption with style + mood + instruments + texture gives more usable candidates than a one-line caption.
- Change: caption length; 3 candidates each. Measure: which candidates survive listening under the narration at low volume. Record why you chose one (`python -m pipeline.music choose ... --why`). Result: TODO

### E11 Ducking settings and intelligibility
- Hypothesis: defaults (0.02 / 6 / 300 ms / 1500 ms) keep the voice clear on a phone speaker; stronger ducking helps only if the music is busy.
- Change: `config.mix.duck_*` or `music_prelevel_lufs`. Measure: 3 listeners on phone speaker, "could you understand every word?"; final LUFS/true peak from `outputs/mix/loudness_report.json`. Result: TODO

### E12 Narration style instruction vs none (and language quality)
- Hypothesis: a short style instruction improves prosody more than switching voice; the model may mispronounce names.
- Change: `config.tts.style_instruction`, then a different `voice`. Measure: native-speaker notes (which words wrong). Result: TODO

---

## Practices tested (feeds the report)

| Suggested practice | Did it beat my instinct? | Evidence |
|---|---|---|
| JSON contract between stages | TODO | |
| Reference sheet before keyframes | TODO | |
| Log every call | TODO | |
| Let the agent write stage scripts while I design and review | TODO | |
