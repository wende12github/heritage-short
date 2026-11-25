"""Narration stage: Gemini TTS, one WAV per shot (cheap re-takes, easy timing).

Cache key per shot = hash(text, tts model, voice, style, language). Edit one line in
storyboard.json and only that shot's narration is regenerated.

Model id comes from storyboard config.tts.model, overridable with GEMINI_TTS_MODEL.
Run `python -m pipeline.smoke_test` to list the model ids your key can actually use.
"""
from __future__ import annotations

import argparse
import base64
import re
import time

import numpy as np

from . import audio, common as C, timeline

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def tts_once(text: str, cfg: dict, lang_code: str, model: str) -> tuple[bytes, int]:
    key = C.need_env("GEMINI_API_KEY")
    # gemini-3.8-flash-tts treats parts[].text as verbatim transcript: prepending style_instruction
    # to text causes the model to speak the English instruction aloud. Pass style via speech_metadata
    # and fall back to plain verbatim text if the REST endpoint rejects speech_metadata.
    part: dict = {"text": text}
    if cfg.get("style_instruction"):
        part["speech_metadata"] = {"style": cfg["style_instruction"]}

    def _build_body(p: dict) -> dict:
        return {
            "contents": [{"parts": [p]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"languageCode": lang_code,
                                 "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice"]}}},
            },
        }

    url = API.format(model=model)
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    try:
        r = C.post(url, headers=headers, json_body=_build_body(part))
    except C.PermanentError as e:
        if "speech_metadata" in part and ("400" in str(e) or "speech_metadata" in str(e).lower()):
            r = C.post(url, headers=headers, json_body=_build_body({"text": text}))
        else:
            raise
    try:
        part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
    except (KeyError, IndexError):
        raise C.PermanentError(f"unexpected TTS response shape: {r.text[:300]}")
    m = re.search(r"rate=(\d+)", part.get("mimeType", ""))
    return base64.b64decode(part["data"]), int(m.group(1)) if m else 24000


def fake_speech(seconds: float, path) -> None:
    """DRY_RUN placeholder: amplitude-modulated hum so loudness/ducking can be tested without a key."""
    sr = 24000
    t = np.linspace(0, seconds, int(seconds * sr), endpoint=False)
    sig = 0.2 * np.sin(2 * np.pi * 180 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))
    audio.write_pcm_wav(path, (sig * 32767).astype("<i2").tobytes(), sr)


def run(sb: dict, shot_ids: list[str] | None = None, force: bool = False) -> None:
    cfg = sb["config"]["tts"]
    model = __import__("os").environ.get("GEMINI_TTS_MODEL", cfg["model"])
    lang = sb["language"]["tts_language_code"]
    out = C.ensure("narration")
    done = skipped = 0
    for shot in C.select_shots(sb, shot_ids):
        text = shot["narration"]["text"]
        h = C.stable_hash(text, model, cfg["voice"], cfg.get("style_instruction"), lang, C.dry_run())
        path = out / f"{shot['id']}.wav"
        if not force and C.is_fresh(f"narration/{shot['id']}", h, path):
            skipped += 1
            continue
        t0 = time.time()
        if C.dry_run():
            fake_speech(timeline.estimate_narr_seconds(text), path)
            attempts = 1
        else:
            try:
                (pcm, rate), attempts = C.with_retries(lambda: tts_once(text, cfg, lang, model), label=f"tts {shot['id']}")
            except C.QuotaError as e:
                C.log_call("narration", model, shot_id=shot["id"], status="quota", params={"voice": cfg["voice"]})
                print(f"[narration] QUOTA: {e}. {done} done, rest kept for next run.")
                return
            audio.write_pcm_wav(path, pcm, rate)
            time.sleep(cfg.get("sleep_between_s", 0))
        C.mark(f"narration/{shot['id']}", h, path)
        dur = C.ffprobe_duration(path)
        C.log_call("narration", model, shot_id=shot["id"], latency_s=time.time() - t0, attempts=attempts,
                   params={"voice": cfg["voice"], "lang": lang, "chars": len(text), "audio_s": round(dur, 2)},
                   cost_usd=C.price_of("gemini_tts", 1))
        done += 1
        print(f"[narration] {shot['id']}: generated {dur:.1f}s")
    print(f"[narration] {done} generated, {skipped} cached")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    run(C.load_storyboard(), a.shot, a.force)


if __name__ == "__main__":
    main()
