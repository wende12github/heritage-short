# DESIGN.md: audience, intent, user tests

> Graded: audience and intent stated **before generating**; **two** user tests (radio cut, near-final cut), each with
> **at least three people from the audience**; the storyboard visibly changed by what they said; every shot has a stated reason.
> Everything below marked `TODO` must be filled with what actually happened. Do not backfill invented quotes.

## 1. Audience and intent (write before generating)

- **Story / person:** A fictionalised story (*ተስፋ አለመቁረጥ* / Never Give Up) written by me, inspired by the real encouragement friends and family give when repeated failures make someone want to quit. Single fictional character (Yonas, `real_person: false`).
- **Who will watch:** Young Ethiopians in their teens and twenties who feel discouraged when hard work or studies/projects do not succeed right away.
- **Where they watch:** On a phone, vertical 9:16, in Telegram/WhatsApp groups, TikTok, or YouTube Shorts (plus horizontal 16:9 for desktop viewing).
- **How might we...:** How might we remind discouraged young Ethiopians, in 70 seconds of warm Amharic storytelling, that falling is part of learning rather than the end of the road?
- **Feeling or understanding at the end:** Quiet relief and renewed courage to pick up the pen and try one more time tomorrow.
- **What I will not do:** No real people's faces, cloned voices, or private family details; no preachy lecture tone—keep the dialogue gentle and personal.
- **Logline:** see `storyboard.json -> logline`

## 2. Shot reasons

Every shot's reason is in `storyboard.json -> shots[].reason` (schema requires it). After the user tests, update them.
Print them with: `python3 -c "import json;[print(s['id'],s['shot_size'],'|',s['reason']) for s in json.load(open('storyboard.json'))['shots']]"`

## 3. User test 1: the radio cut (narration + temp music on black)

Build: `make radio` -> `outputs/final/radio_cut.mp4`. Commit hash of storyboard tested: `3eb6789`

| # | Who (relationship to the audience) | Where / how (in person, Slack, voice note) | What they said / where they reacted (their words) | What I heard |
|---|---|---|---|---|
| 1 | Roble (friend, target audience) | Telegram | "It is good." | Pacing and overall story landed without confusion. |
| 2 | Tesfa (friend, target audience) | Telegram | "Also it is very good, keep it up." | Tone and encouragement message resonated positively. |
| 3 | Yaread (friend, native Amharic speaker) | Telegram | "It is good, but fix the word issue: instead of 'ችግሮችን' it would be better to say 'ችግሮች'." | Grammatical phrasing in the opening line sounded unnatural with the accusative suffix `-ን` before `ያጋጠመው`. |

Questions I asked (keep them neutral and the same for everyone): "What was this about?", "Where did you lose interest?",
"What did you feel at the end?", "Was any word or name unclear?", "What would you cut?"

**Insights (what repeated):** All three listeners understood the story and responded warmly to the pacing and tone, while a native-speaker listen caught an unnatural Amharic suffix in the opening sentence (`s01`) that only stood out when heard aloud.

**What I changed because of it (storyboard diff):**

| Change | Shot(s) | Which comment caused it | Commit |
|---|---|---|---|
| Changed narration text from `"አንድ ወቅት ብዙ ችግሮችን ያጋጠመው ወጣት ነበር።"` to `"አንድ ወቅት ብዙ ችግሮች ያጋጠመው ወጣት ነበር።"` | `s01` | Yaread's comment on `"ችግሮችን"` vs `"ችግሮች"` | pending commit after `s01` regeneration |

## 4. User test 2: the near-final cut (both formats, score, subtitles)

Build: `make film` -> `outputs/final/`. Commit hash tested: TODO

| # | Who | Where / how | What they said (their words) | What I heard |
|---|---|---|---|---|
| 1 | TODO | | | |
| 2 | TODO | | | |
| 3 | TODO | | | |

Also ask: can you read the subtitles on your phone, can you hear the voice over the music, does she/he look like the same
person every time, did you notice the AI end card?

**Insights:** TODO

**What I changed because of it:**

| Change | Shot(s) | Which comment caused it | Commit |
|---|---|---|---|
| TODO | | | |

## 5. Native-speaker check of the narration

Who listened: Myself (native Amharic speaker) and Yaread (friend, Telegram). Mispronounced names/words and the fix: Earlier `F01`/`F02` pipeline issues (English style prompt spoken aloud and trailing C2PA bytes played as noise) were fixed before testing; in User Test 1, Yaread caught `"ችግሮችን"` sounding unnatural before `"ያጋጠመው"` in `s01`, fixed to `"ችግሮች"` in `storyboard.json`.
