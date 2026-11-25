"""Assembly stage (FFmpeg only, deterministic): cut, subtitles, ducked score, loudness, end card, 2 aspect ratios.

Per shot it uses a Wan clip when fresh, else a Ken Burns pan/zoom of the keyframe, else a labelled
placeholder. Segments are cached by input hash, so changing one shot re-renders one segment per format.
Both formats are centre crops of the same square material, scaled to 1080x1920 and 1920x1080.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import audio, common as C, shots as shots_stage, timeline
from .keyframes import placeholder

FORMATS = {"vertical_9x16": (1080, 1920), "horizontal_16x9": (1920, 1080)}
FONT_CANDIDATES = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
                   "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"]
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p", "-an"]


def _crop(w: int, h: int) -> str:
    return f"crop='min(iw,ih*{w}/{h})':'min(ih,iw*{h}/{w})'"


def kenburns_filter(camera: str, w: int, h: int, frames: int, fps: int) -> str:
    N = max(frames, 2)
    z, x, y = "1", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if camera == "push_in":
        z = f"1+0.18*on/{N}"
    elif camera == "pull_out":
        z = f"1.18-0.18*on/{N}"
    elif camera in ("pan_left", "pan_right"):
        z = "1.15"
        x = f"(iw-iw/zoom)*{'(1-on/' + str(N) + ')' if camera == 'pan_left' else 'on/' + str(N)}"
    elif camera in ("tilt_up", "tilt_down"):
        z = "1.15"
        y = f"(ih-ih/zoom)*{'(1-on/' + str(N) + ')' if camera == 'tilt_up' else 'on/' + str(N)}"
    # upscale 2x first so zoompan does not jitter, then crop to aspect
    return f"{_crop(w, h)},scale={2 * w}:{2 * h},zoompan=z='{z}':x='{x}':y='{y}':d={N}:s={w}x{h}:fps={fps},setsar=1"


def render_segment(sb, shot, row, fmt, w, h, fps) -> Path:
    seg_dir = C.ensure("segments", fmt)
    out = seg_dir / f"{shot['id']}.mp4"
    kf = C.OUT / "keyframes" / f"{shot['id']}.jpg"
    state = shots_stage.clip_state(sb, shot)
    dur = row["dur"]
    frames = int(round(dur * fps))
    if state == "no_keyframe":
        placeholder(shot["id"], "MISSING KEYFRAME", kf)
    if state == "fresh":
        src = C.OUT / "clips" / f"{shot['id']}.mp4"
        kind = "clip"
    else:
        src, kind = kf, "kenburns"
    h_in = C.stable_hash(C.file_sha(src), kind, shot["camera"], round(dur, 3), w, h, fps)
    key = f"segment/{fmt}/{shot['id']}"
    if C.is_fresh(key, h_in, out):
        return out
    if kind == "clip":
        # hold the last frame if the clip is shorter than the shot, trim if longer
        vf = f"{_crop(w, h)},scale={w}:{h}:flags=lanczos,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={dur}"
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-t", f"{dur:.3f}", *ENC, str(out)]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", kenburns_filter(shot["camera"], w, h, frames, fps),
               "-frames:v", str(frames), *ENC, str(out)]
    C.run(cmd)
    C.mark(key, h_in, out)
    return out


def _font(size: int):
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_end_card(sb, fmt, w, h, fps) -> Path:
    ec = sb["end_card"]
    out = C.ensure("segments", fmt) / "end_card.mp4"
    h_in = C.stable_hash(ec, w, h, fps)
    key = f"segment/{fmt}/end_card"
    if C.is_fresh(key, h_in, out):
        return out
    img = Image.new("RGB", (w, h), (14, 14, 18))
    d = ImageDraw.Draw(img)
    sizes = [int(h * 0.05), int(h * 0.026), int(h * 0.026)] + [int(h * 0.022)] * 5
    y = h * 0.40
    for i, line in enumerate(ec["lines"]):
        f = _font(sizes[min(i, len(sizes) - 1)])
        tw = d.textlength(line, font=f)
        d.text(((w - tw) / 2, y), line, font=f, fill=(245, 240, 230) if i == 0 else (190, 190, 190))
        y += sizes[min(i, len(sizes) - 1)] * 1.9
    png = C.ensure("tmp") / f"end_card_{fmt}.png"
    img.save(png)
    frames = int(ec["duration_s"] * fps)
    vf = f"fade=t=in:st=0:d=0.6,fade=t=out:st={ec['duration_s'] - 0.6}:d=0.6"
    C.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png), "-vf", vf, "-frames:v", str(frames), "-r", str(fps), *ENC, str(out)])
    C.mark(key, h_in, out)
    return out


def assemble(sb: dict, formats: list[str] | None = None) -> dict:
    t_start = time.time()
    scale = sb["config"]["output"].get("dry_run_scale", 0.5) if C.dry_run() else 1.0
    fps = sb["config"]["output"]["fps"]
    tl = timeline.build(sb)
    if not 60 <= tl["total"] <= 90:
        print(f"[assemble] WARNING: film length {tl['total']:.1f}s is outside the 60-90s requirement")
    work = C.ensure("mix")
    mix_path, notes = audio.mix_all(sb, tl, work)
    for n in notes:
        print(f"[assemble] {n}")
    final = C.ensure("final")
    srt = final / "film.srt"
    srt.write_text(timeline.build_srt(sb, tl), encoding="utf-8")
    result = {"length_s": round(tl["total"], 2), "files": {}}
    for fmt, (W, H) in FORMATS.items():
        if formats and fmt not in formats:
            continue
        w, h = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
        segs = [render_segment(sb, s, r, fmt, w, h, fps) for s, r in zip(sb["shots"], tl["shots"])]
        segs.append(render_end_card(sb, fmt, w, h, fps))
        lst = C.ensure("tmp") / f"concat_{fmt}.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in segs), encoding="utf-8")
        joined = C.ensure("tmp") / f"joined_{fmt}.mp4"
        C.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
        out = final / f"film_{fmt}.mp4"
        # run from the final dir so the subtitle path needs no escaping
        ass = f"subs_{fmt}.ass"
        (final / ass).write_text(timeline.build_ass(sb, tl, w, h, fmt.startswith("vertical")), encoding="utf-8")
        vf = f"ass={ass}"
        C.run(["ffmpeg", "-y", "-v", "error", "-i", str(joined.resolve()), "-i", str(mix_path.resolve()),
               "-vf", vf, "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
               "-metadata", "comment=AI-generated film (images, motion, voice, music). See end card and ETHICS.md.",
               "-t", f"{tl['total']:.3f}", out.name], cwd=final)
        result["files"][fmt] = str(out.relative_to(C.ROOT))
        print(f"[assemble] wrote {out.relative_to(C.ROOT)} ({w}x{h})")
    C.log_call("assemble", "ffmpeg", latency_s=time.time() - t_start, params={"formats": list(result["files"]), "scale": scale,
               "length_s": result["length_s"]}, cost_usd=0.0)
    (final / "render_report.json").write_text(json.dumps({**result, "audio_notes": notes}, indent=2), encoding="utf-8")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--format", nargs="*", choices=list(FORMATS))
    a = ap.parse_args()
    assemble(C.load_storyboard(), a.format)


if __name__ == "__main__":
    main()
