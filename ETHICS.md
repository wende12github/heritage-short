# ETHICS.md: consent, licences, labelling

> The film scores **zero** if a real person appears or is voiced without a consent record here.
> `pipeline/validate.py` enforces this: a character with `real_person: true` needs a `consent_ref`
> whose row below says `RECORDED` (and is not a TEMPLATE row). Fill this in **before** generating anything of a real person.

## 1. Do real people appear or speak?

Decide per person. Tick what applies, then fill section 2.

- [ ] A real person's face or likeness appears (photo used as a reference, or the character is described to look like them)
- [ ] A real person's voice is used or cloned
- [ ] Words are put in a real person's mouth
- [x] None of the above: characters are invented or fictionalised (say how in one sentence): Yonas is a completely fictional young Ethiopian man (`real_person: false`) created for this original parable, and Gemini TTS uses a stock voice (`Kore`).

Rule of thumb used in this project: if I would say "that is grandma" when I see the character, it is a likeness, so
`real_person` is `true` and I need consent. Gemini TTS uses a stock voice (`config.tts.voice`), not a clone of anyone.

## 2. Consent record

One row per real person. A row only counts when it contains the word `RECORDED` in the Status column
(the example row is a TEMPLATE and is ignored by the validator).

| Ref | Person (relationship) | What they agreed to (face / voice / words / story) | How it was given (date, who asked, in person/voice note/message, language) | Evidence kept | Status |
|---|---|---|---|---|---|
| CONSENT-000 | EXAMPLE: Aster (grandmother) | face likeness, the proverb in her words, the market story | 24 Nov, I explained in Amharic by phone, she agreed, voice note saved | voice-note file name (not committed, private) | TEMPLATE, delete this row |
| CONSENT-001 | N/A (fictional character Yonas; `real_person: false`) | n/a | n/a | n/a | NOT NEEDED (fictional) |

Words the person agreed to be in their mouth (quote them exactly): ______

## 3. Licences of every model and output

Checked on: **2026-11-26**. Statuses below verified against the model/provider terms used in this pipeline.

| Component | Used for | Licence / terms | Commercial use of outputs? | Source checked |
|---|---|---|---|---|
| Gemini 3.5 Flash-Lite (API, free tier) | consistency judge | Google API terms (`ai.google.dev/gemini-api/terms`). **Free tier may improve Google products; no private family data sent.** | per Google API terms | https://ai.google.dev/gemini-api/terms |
| Gemini 3.8 Flash TTS | narration | Google API terms, outputs carry SynthID + C2PA | per Google API terms | https://ai.google.dev/gemini-api/terms |
| FLUX.1 schnell on Cloudflare Workers AI | reference & keyframes | Apache 2.0 model weights + Cloudflare Workers AI terms | yes (Apache 2.0) | https://huggingface.co/black-forest-labs/FLUX.1-schnell |
| Wan 2.2 TI2V-5B | moving shots | Apache 2.0 | yes | https://huggingface.co/Wan-AI/Wan2.2-TI2V-5B |
| ACE-Step 1.5 | score | MIT; outputs usable commercially | yes | https://github.com/ACE-Step/ACE-Step-1.5 |
| FFmpeg | assembly | LGPL/GPL depending on build | n/a | https://ffmpeg.org/legal.html |
| DejaVu Sans / other fonts | subtitles, end card | Free font licence (Bitstream Vera / Arev) | yes | https://dejavu-fonts.github.io/License.html |
| Coding agent (Antigravity) | code | Agent terms; no secrets or private family photos pasted | n/a | workspace policy |

## 4. Private data

- What family details are in prompts sent to free endpoints? None—the story, character name (`Yonas`), and setting are fictionalised.
- What I kept out of them (full names, addresses, photos of relatives): All real names, personal stories of identifiable relatives, addresses, and personal photos.

## 5. Labelling plan

- [x] End card says it was made with AI (rendered by `pipeline/assemble.py`, text in `storyboard.json -> end_card`)
- [ ] Platform AI/"altered or synthetic content" label switched **on** when posting (platform: ______, screenshot saved: ______)
- [x] Provenance (SynthID/C2PA) not stripped: `audio.write_pcm_wav()` preserves Gemini's RIFF `C2PA` chunks intact (`F02`); final encode keeps MP4 provenance/AI end card
- [x] Style prompts describe qualities, never a living artist's name (validator warns on "in the style of")
