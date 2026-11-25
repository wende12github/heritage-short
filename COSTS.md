# COSTS.md: measured latency, GPU minutes, list-price equivalent

> Graded: measured latency and GPU minutes **per stage**, a **list-price** cost equivalent, and a **frontier comparison** where you
> had access. Do not estimate when you can measure: `make costs` builds the table from `runs.jsonl` (dry-run lines excluded).
> Nothing here is measured yet.

## 1. Measured per stage (paste the output of `make costs`)

TODO: run `make film` for real, then `make costs`, and paste the table here with the date.

## 2. Free-tier limits I actually found (check each at the start; note the date)

| Service | Documented free limit | What I actually hit | Date |
|---|---|---|---|
| Gemini API (text) | TODO | | |
| Gemini TTS | TODO | | |
| Cloudflare Workers AI (images/day) | TODO | | |
| Kaggle GPU hours / week, session length | TODO | | |
| Coding agent weekly quota | TODO | | |

## 3. List-price equivalent

Fill `pipeline/pricing.json` from each provider's **current** price page (put URL + date in the table), then re-run `make costs`.

| Item | Unit price used | Source URL | Date checked |
|---|---|---|---|
| Image (Workers AI FLUX) | TODO | | |
| TTS | TODO | | |
| GPU minute for Wan/ACE-Step (comparable paid GPU) | TODO | | |

Total list-price equivalent for the film: TODO. Actual cash spent: 0 (if true).

## 4. Frontier comparison (only if access was granted)

| Shot | Open model (Wan 2.2) latency / cost | Frontier model latency / cost | Blind preference (n, result) |
|---|---|---|---|
| TODO | | | |

If no frontier access: say so here in one line.

## 5. Where the time went

Wall-clock per phase (story, radio cut, keyframes, GPU queue, edit, docs): TODO. What dominated: TODO.
