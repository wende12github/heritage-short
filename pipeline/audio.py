"""Audio helpers: narration track, score placement, mixing, ducking, loudness (all FFmpeg/numpy).

Order follows professional practice (Appendix C): dialogue first, music under it,
bring each source to a similar loudness, duck, THEN set final loudness.
"""
from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path

import numpy as np

from . import common as C

SR = 48000


# ------------------------------------------------------------------------- I/O
def read_audio(path: Path) -> np.ndarray:
    """Decode any audio file to float32 stereo at 48 kHz, shape (n, 2)."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                       capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(f"cannot decode {path}: {p.stderr.decode()[-300:]}")
    return np.frombuffer(p.stdout, dtype=np.float32).reshape(-1, 2).copy()


def write_wav(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.clip(arr, -1.0, 1.0)
    pcm = (a * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def write_pcm_wav(path: Path, pcm: bytes, rate: int) -> None:
    """Write mono 16-bit PCM bytes (what Gemini TTS returns) as a WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


# -------------------------------------------------------------------- loudness
def measure(path: Path, I: float = -14, TP: float = -1, LRA: float = 11) -> dict | None:
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af",
                        f"loudnorm=I={I}:TP={TP}:LRA={LRA}:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", p.stderr, re.S)
    if not m:
        return None
    d = json.loads(m.group(0))
    try:
        d = {k: float(v) for k, v in d.items() if k != "normalization_type"}
    except ValueError:
        return None
    return d


def gain_to(arr: np.ndarray, path_for_measure: Path, target_lufs: float) -> np.ndarray:
    """Return arr scaled so its integrated loudness is ~target_lufs (skips silence)."""
    m = measure(path_for_measure)
    if not m or m["input_i"] < -70:
        return arr
    g = 10 ** ((target_lufs - m["input_i"]) / 20)
    return arr * g


def loudnorm_two_pass(src: Path, dst: Path, I: float, TP: float, LRA: float) -> dict:
    m = measure(src, I, TP, LRA)
    if m is None:
        raise RuntimeError("loudness measurement failed")
    af = (f"loudnorm=I={I}:TP={TP}:LRA={LRA}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    C.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", af, "-ar", str(SR), "-ac", "2", str(dst)])
    after = measure(dst, I, TP, LRA) or {}
    return {"before": m, "after": after}


# ------------------------------------------------------------- track building
def build_narration_track(sb: dict, tl: dict) -> np.ndarray:
    total = int(tl["total"] * SR)
    track = np.zeros((total, 2), dtype=np.float32)
    for shot, row in zip(sb["shots"], tl["shots"]):
        p = C.OUT / "narration" / f"{shot['id']}.wav"
        if not p.exists():
            continue
        a = read_audio(p)
        i = int(row["narr_start"] * SR)
        n = min(len(a), total - i)
        if n > 0:
            track[i:i + n] += a[:n]
    return track


def _fade(a: np.ndarray, fin: float, fout: float) -> np.ndarray:
    a = a.copy()
    nin, nout = min(int(fin * SR), len(a)), min(int(fout * SR), len(a))
    if nin:
        a[:nin] *= np.linspace(0, 1, nin)[:, None]
    if nout:
        a[-nout:] *= np.linspace(1, 0, nout)[:, None]
    return a


def chosen_cue_path(cue_id: str) -> Path | None:
    p = C.OUT / "music" / "chosen" / f"{cue_id}.wav"
    return p if p.exists() else None


def build_score(sb: dict, tl: dict) -> tuple[np.ndarray, list[str]]:
    """Place each chosen cue at its shot range with crossfades. Falls back to the temp track."""
    total = int(tl["total"] * SR)
    xf = sb["music"].get("crossfade_s", 1.5)
    ids = [s["id"] for s in sb["shots"]]
    starts = {r["id"]: r["start"] for r in tl["shots"]}
    ends = {r["id"]: r["start"] + r["dur"] for r in tl["shots"]}
    buf = np.zeros((total + int(xf * SR) * 2, 2), dtype=np.float32)
    notes: list[str] = []
    temp = C.OUT / "music" / "temp_track.wav"
    cues = sb["music"]["cues"]
    for k, cue in enumerate(cues):
        last = k == len(cues) - 1
        src = chosen_cue_path(cue["id"])
        if src is None:
            if not temp.exists():
                from . import music
                music.make_temp_track(60)
            src = temp
            notes.append(f"cue {cue['id']}: no chosen score, using TEMP track (not an original score)")
        a = read_audio(src)
        t0 = starts[cue["start_shot"]]
        t1 = tl["total"] if last else ends[cue["end_shot"]] + xf     # overlap into the next cue
        n = int((t1 - t0) * SR)
        if len(a) < n:                                               # loop short cues
            a = np.tile(a, (n // len(a) + 1, 1))
        a = _fade(a[:n], 0.8 if k == 0 else xf, 2.5 if last else xf)
        i = int(t0 * SR)
        buf[i:i + n] += a[:n]
    return buf[:total], notes


# ------------------------------------------------------------------------- mix
def mix_all(sb: dict, tl: dict, workdir: Path) -> tuple[Path, list[str]]:
    """Narration + ducked score -> loudness-normalised stereo WAV. Returns (path, notes)."""
    mx = sb["config"]["mix"]
    workdir.mkdir(parents=True, exist_ok=True)
    narr = build_narration_track(sb, tl)
    write_wav(workdir / "narration_raw.wav", narr)
    narr = gain_to(narr, workdir / "narration_raw.wav", mx.get("narration_prelevel_lufs", -16))
    write_wav(workdir / "narration.wav", narr)

    score, notes = build_score(sb, tl)
    write_wav(workdir / "score_raw.wav", score)
    score = gain_to(score, workdir / "score_raw.wav", mx.get("music_prelevel_lufs", -24))
    write_wav(workdir / "score.wav", score)

    sc = (f"sidechaincompress=threshold={mx.get('duck_threshold', 0.02)}:ratio={mx.get('duck_ratio', 6)}:"
          f"attack={mx.get('duck_attack_ms', 300)}:release={mx.get('duck_release_ms', 1500)}")
    fc = f"[0:a]asplit=2[n1][n2];[1:a][n1]{sc}[duck];[duck][n2]amix=inputs=2:normalize=0[out]"
    C.run(["ffmpeg", "-y", "-v", "error", "-i", str(workdir / "narration.wav"), "-i", str(workdir / "score.wav"),
           "-filter_complex", fc, "-map", "[out]", "-ar", str(SR), "-ac", "2", str(workdir / "mix_prenorm.wav")])
    report = loudnorm_two_pass(workdir / "mix_prenorm.wav", workdir / "mix_final.wav",
                               mx["target_lufs"], mx["true_peak_db"], mx.get("lra", 11))
    (workdir / "loudness_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    after = report.get("after", {})
    if after:
        notes.append(f"final mix: {after.get('input_i', '?')} LUFS, true peak {after.get('input_tp', '?')} dBTP "
                     f"(targets {mx['target_lufs']} / {mx['true_peak_db']})")
    return workdir / "mix_final.wav", notes
