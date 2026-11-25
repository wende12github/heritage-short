# The Heritage Short: a storyboard-driven AI film pipeline

A 60-90 s short film about a person and place that matter to my family, narrated in my own language,
with English subtitles, an original score ducked under the voice, an "Made with AI" end card, and
exports in **9:16** and **16:9**. The film is the output; **the pipeline is the product**: a stranger can clone
this repo, run one command, and regenerate the film from `storyboard.json`.

> **Status of this repo's story:** `storyboard.json` ships with a clearly marked **placeholder** story
> (a grandmother's walk to the Dessie market). Replace the story, characters, narration and audience with your own
> before generating anything real. See `docs/SUBMISSION_CHECKLIST.md`.

## Run it

```bash
git clone <this repo> && cd heritage-short
pip install -r requirements.txt          # + FFmpeg with libass on PATH
cp .env.example .env                     # add GEMINI_API_KEY, CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID

make film          # THE one command: validate -> narration -> keyframes -> shots -> music -> assemble
make demo          # same pipeline, no keys: placeholder frames + synthetic voice, real FFmpeg assembly
make test          # offline tests: schema, consent gate, caching, "only the edited shot regenerates"
```

Final files: `outputs/final/film_vertical_9x16.mp4`, `film_horizontal_16x9.mp4`, `film.srt`, `radio_cut.mp4`.

### What `make film` does, and what it does not do on your laptop

| Stage | Command | Where it runs | Output |
|---|---|---|---|
| validate | `python -m pipeline.validate` | local | schema + cross-field + **consent gate** |
| script (optional) | `python -m pipeline.script story.md` | Gemini API | `storyboard.draft.json` |
| narration | `python -m pipeline.narration` | Gemini TTS | `outputs/narration/sNN.wav` |
| reference (once) | `make reference` | Cloudflare FLUX | `outputs/reference/*.jpg` -> choose a golden reference |
| keyframes | `python -m pipeline.keyframes` | Cloudflare FLUX | `outputs/keyframes/sNN.jpg` |
| shots | `python -m pipeline.shots plan / ingest` | **Kaggle GPU** (Wan 2.2) | `outputs/clips/sNN.mp4` |
| music | `python -m pipeline.music plan / register / choose` | **Kaggle GPU** (ACE-Step 1.5) | `outputs/music/chosen/<cue>.wav` |
| assemble | `python -m pipeline.assemble` | local FFmpeg | the two MP4s |

The two GPU stages cannot be a single local command because the GPU is borrowed. They are a **plan -> notebook -> ingest**
loop, and the pipeline degrades gracefully while you wait: a shot without a fresh Wan clip uses a Ken Burns pan/zoom of its
keyframe, and a cue without a chosen score uses a clearly-reported temp track. `make film` therefore always finishes, and every
fallback is printed. After the GPU stages: run the notebook, `python -m pipeline.shots ingest <dir>`, `make film` again.

### Regenerate one shot (what the walkthrough shows)

Edit one `keyframe_prompt` (or one `narration.text`) in `storyboard.json`, then:

```bash
make film        # prints "keyframes: 1 generated, 9 cached"; runs.jsonl gains exactly one new line
```

Caching is by input hash (`outputs/manifest.json`), so only that shot's keyframe, its Wan job and its segment re-render.

## Cost

Everything used is free-tier or open-weight; measured numbers are in [COSTS.md](COSTS.md) (`make costs` builds the tables
from `runs.jsonl`). The binding constraint is GPU time and queueing, not money.

## Repository map

```
storyboard.json     the contract: shots, durations, prompts, seeds, narration, music cues, config
schema/             JSON Schema, validated before every run
pipeline/           one script per stage + common.py (hashing, cache, retries, run log)
notebooks/          Kaggle scripts for Wan 2.2 (video) and ACE-Step 1.5 (music)
runs.jsonl          one line per model call: model, params, seed, latency, GPU-minutes, list-price equivalent
outputs/            generated images, audio, clips and final cuts (kept so a run can be inspected)
tests/              offline tests (run with `make test`)
DESIGN.md           audience, intent, the two user tests and what changed because of them
ARCHITECTURE.md     stages, contracts, caching, failure handling
EXPERIMENTS.md      hypothesis -> change -> result
FAILURES.md         what broke, what I tried, what fixed it
COSTS.md            measured latency/GPU minutes per stage, list-price equivalents
ETHICS.md           consent record, licences, labelling plan
docs/               report template, post template, walkthrough script, interview prep, checklist
```

## Secrets

Keys live only in `.env` (git-ignored) or the environment. Requests send them in headers; they are never logged.
`runs.jsonl` records prompts only as hashes plus lengths.

## Known limits

- Square master frames are centre-cropped for both formats, so verticals are upscaled from ~576 px wide (see EXPERIMENTS.md).
- The Wan 2.2 and ACE-Step 1.5 notebooks, the Gemini TTS/text model ids and the FLUX.2 klein multipart call are written
  from documentation, not verified against the live services by the author of the scaffold; `make smoke` and the first real run
  are where reality is recorded (FAILURES.md).
