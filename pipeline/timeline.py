"""Timeline: turns narration durations + storyboard into start/duration per shot.

Narration sets the pace (professionals cut picture to the voice). A shot lasts
max(duration_s, narration + lead_in + tail). Used by radio cut, assembly and subtitles.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

from . import common as C


def narration_path(shot_id: str) -> Path:
    return C.OUT / "narration" / f"{shot_id}.wav"


def estimate_narr_seconds(text: str) -> float:
    return max(1.5, len(text.split()) / 2.2)


def build(sb: dict) -> dict:
    o = sb["config"]["output"]
    lead, tail = o.get("lead_in_s", 0.5), o.get("tail_s", 0.7)
    t, rows = 0.0, []
    for s in sb["shots"]:
        p = narration_path(s["id"])
        if p.exists():
            nd = C.ffprobe_duration(p)
        else:
            nd = estimate_narr_seconds(s["narration"]["text"])
            print(f"[timeline] {s['id']}: no narration file, estimating {nd:.1f}s")
        dur = max(float(s["duration_s"]), nd + lead + tail)
        rows.append({"id": s["id"], "start": t, "dur": dur, "narr_dur": nd, "narr_start": t + lead,
                     "has_narr": p.exists()})
        t += dur
    end_dur = float(sb["end_card"]["duration_s"])
    return {"shots": rows, "shots_total": t, "end_start": t, "end_dur": end_dur, "total": t + end_dur}


# ------------------------------------------------------------------- subtitles
def wrap_cues(text: str, max_chars: int = 40, max_lines: int = 2) -> list[str]:
    """Split text into subtitle cues of at most `max_lines` lines of `max_chars` characters."""
    lines = textwrap.wrap(text, width=max_chars) or [text]
    return ["\n".join(lines[i:i + max_lines]) for i in range(0, len(lines), max_lines)]


def _ts(x: float) -> str:
    ms = int(round(x * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cues(sb: dict, tl: dict) -> list[tuple[float, float, str]]:
    """(start, end, text) for every subtitle cue; text has at most 2 lines of <= subtitle_max_chars."""
    maxc = sb["config"]["output"].get("subtitle_max_chars", 40)
    out: list[tuple[float, float, str]] = []
    for shot, row in zip(sb["shots"], tl["shots"]):
        parts = wrap_cues(shot["narration"]["translation_en"], maxc)
        total_chars = sum(len(c.replace("\n", " ")) for c in parts) or 1
        t = row["narr_start"]
        for c in parts:
            d = row["narr_dur"] * len(c.replace("\n", " ")) / total_chars
            out.append((t, t + d, c))
            t += d
    return out


def build_srt(sb: dict, tl: dict) -> str:
    return "\n".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n" for i, (a, b, txt) in enumerate(cues(sb, tl), 1))


def _ass_ts(x: float) -> str:
    cs = int(round(x * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(sb: dict, tl: dict, w: int, h: int, vertical: bool) -> str:
    """ASS subtitles on a real w x h canvas so sizes/margins are in output pixels.
    Vertical keeps text clear of platform buttons (bottom ~20%) and inside side margins."""
    size, mv, ml = (int(h * 0.030), int(h * 0.20), int(w * 0.08)) if vertical else (int(h * 0.050), int(h * 0.07), int(w * 0.10))
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {w}\nPlayResY: {h}\nWrapStyle: 2\n\n"
            "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,DejaVu Sans,{size},&H00FFFFFF,&H00FFFFFF,&H99000000,&H00000000,0,0,0,0,100,100,0,0,1,{max(2, size // 14)},0,2,{ml},{ml},{mv},1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    lines = [f"Dialogue: 0,{_ass_ts(a)},{_ass_ts(b)},Default,,0,0,0,,{txt.replace(chr(10), chr(92) + 'N')}" for a, b, txt in cues(sb, tl)]
    return head + "\n".join(lines) + "\n"
