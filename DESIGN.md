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

Build: `make radio` -> `outputs/final/radio_cut.mp4`. Commit hash of storyboard tested: TODO

| # | Who (relationship to the audience) | Where / how (in person, Slack, voice note) | What they said / where they reacted (their words) | What I heard |
|---|---|---|---|---|
| 1 | TODO | | | |
| 2 | TODO | | | |
| 3 | TODO | | | |

Questions I asked (keep them neutral and the same for everyone): "What was this about?", "Where did you lose interest?",
"What did you feel at the end?", "Was any word or name unclear?", "What would you cut?"

**Insights (what repeated):** TODO

**What I changed because of it (storyboard diff):**

| Change | Shot(s) | Which comment caused it | Commit |
|---|---|---|---|
| TODO | | | |

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

Who listened: TODO. Mispronounced names/words and the fix: TODO (also record in FAILURES.md if the model got your language wrong).
