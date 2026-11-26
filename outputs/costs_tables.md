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
