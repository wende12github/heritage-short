"""Consistency judge: asks a Gemini vision model to score each keyframe against the golden reference.

  python -m pipeline.judge            scores every shot that has a character and a golden_reference
  -> appends one runs.jsonl line per judgement (stage "judge") with same_person / same_style 1-5

This turns "the character looks consistent" into evidence you can cite in EXPERIMENTS.md. It is a model's
opinion, not ground truth: spot-check it by eye and say so in the experiment entry.
"""
from __future__ import annotations

import json
import os
import re
import time

from . import common as C

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
Q = ('Image 1 is the approved reference for a character and art style. Image 2 is a new frame. '
     'Rate 1-5 (5 = clearly the same) whether the character in image 2 is the same person as in image 1 ("same_person") '
     'and whether the art style matches ("same_style"). If no character is visible in image 2 use null for same_person. '
     'Answer ONLY JSON: {"same_person": n|null, "same_style": n, "notes": "<=20 words"}')


def judge_one(ref, frame, model: str) -> dict:
    key = C.need_env("GEMINI_API_KEY")
    parts = [{"text": Q},
             {"inline_data": {"mime_type": "image/jpeg", "data": C.b64(ref.read_bytes())}},
             {"inline_data": {"mime_type": "image/jpeg", "data": C.b64(frame.read_bytes())}}]
    r = C.post(API.format(model=model), headers={"x-goog-api-key": key, "Content-Type": "application/json"},
               json_body={"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json"}})
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M))


def main() -> None:
    sb = C.load_storyboard()
    model = os.environ.get("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
    refs = {c["id"]: C.ROOT / c["golden_reference"] for c in sb["characters"] if c.get("golden_reference")}
    if not refs:
        print("[judge] no golden_reference set. Run `make reference`, pick one, set characters[].golden_reference."); return
    for shot in sb["shots"]:
        cid = next((c for c in shot["characters"] if c in refs), None)
        frame = C.OUT / "keyframes" / f"{shot['id']}.jpg"
        if not cid or not frame.exists():
            continue
        t0 = time.time()
        (res, attempts) = C.with_retries(lambda: judge_one(refs[cid], frame, model), label=f"judge {shot['id']}")
        C.log_call("judge", model, shot_id=shot["id"], latency_s=time.time() - t0, attempts=attempts,
                   params={"character": cid}, scores=res, cost_usd=C.price_of("gemini_text", 1))
        print(f"[judge] {shot['id']}: {res}")


if __name__ == "__main__":
    main()
