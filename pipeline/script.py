"""Script stage: draft storyboard.json from your own story with Gemini, validated against the schema.

  python -m pipeline.script story.md          -> storyboard.draft.json (never overwrites storyboard.json)

Write story.md yourself, in your own words, after talking to the person whose story it is (3-5 sentences
per beat is plenty). The model proposes shots, prompts, narration and music cues; YOU review it, edit it,
and copy it over storyboard.json. Every draft is re-validated; schema errors are fed back for up to 3 tries.
Avoid sending private family details: free-tier endpoints may train on what you send.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from . import common as C, validate

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

BRIEF = """You are drafting a storyboard JSON for a 60-90 second AI-generated family short film.
Rules:
- Output ONLY one JSON object, no markdown fences, valid against the JSON Schema below.
- 8 to 12 shots, ids s01.. sequential. Total of shot durations plus end card should be 60-90 seconds.
- Square (1:1) keyframes with the subject centred; one idea and one gentle movement per shot; vary shot sizes.
- keyframe_prompt must include {character_id} placeholders exactly for the characters in the shot (and no others);
  never name a living artist; no text inside images.
- motion_prompt describes only motion and camera (the image already contains the subject).
- narration.text is in the narration language, short sentences written for the ear; translation_en is faithful English.
- Every shot needs a one-sentence `reason` that a viewer-focused director could defend.
- Keep character count low. Set real_person true only if the story's person's likeness will be depicted.
- music: one cue per story section, with caption (style, mood, instruments, texture), bpm, key, instrumental true.
- Copy the config block from the TEMPLATE unchanged except where the story needs it.
"""


def call(prompt: str, model: str) -> str:
    key = C.need_env("GEMINI_API_KEY")
    r = C.post(API.format(model=model), headers={"x-goog-api-key": key, "Content-Type": "application/json"},
               json_body={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7}})
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]


def draft(story: str, narration_language: str, tries: int = 3) -> dict:
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
    schema = C.SCHEMA.read_text(encoding="utf-8")
    template = C.STORYBOARD.read_text(encoding="utf-8") if C.STORYBOARD.exists() else "{}"
    feedback = ""
    for i in range(1, tries + 1):
        prompt = (f"{BRIEF}\nNarration language: {narration_language}\n\nSCHEMA:\n{schema}\n\n"
                  f"TEMPLATE (an example storyboard; follow its structure and config):\n{template}\n\n"
                  f"STORY (from the filmmaker):\n{story}\n{feedback}")
        t0 = time.time()
        text = call(prompt, model)
        C.log_call("script", model, latency_s=time.time() - t0, attempts=i, params={"story_chars": len(story)},
                   cost_usd=C.price_of("gemini_text", 1))
        text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
        try:
            sb = json.loads(text)
        except json.JSONDecodeError as e:
            feedback = f"\nYour last output was not valid JSON ({e}). Return only the JSON object."
            continue
        errs = validate.schema_errors(sb)
        if not errs:
            e2, _ = validate.semantic_errors(sb)
            errs = e2
        if not errs:
            return sb
        feedback = "\nYour last output failed validation. Fix these and return the full JSON again:\n- " + "\n- ".join(errs[:15])
    raise C.PermanentError("could not produce a valid storyboard in 3 tries; edit by hand using the last errors")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("story_file")
    ap.add_argument("--language", default=None, help="narration language name (default: from storyboard.json)")
    a = ap.parse_args()
    lang = a.language or (C.load_storyboard()["language"]["narration_name"] if C.STORYBOARD.exists() else "English")
    sb = draft(Path(a.story_file).read_text(encoding="utf-8"), lang)
    out = C.ROOT / "storyboard.draft.json"
    out.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[script] wrote {out.name}. Review every shot, then copy it over storyboard.json.")


if __name__ == "__main__":
    main()
