"""Radio cut: narration over placeholder music on a black screen. Prototype for user test 1.

Plays the story end to end before any picture is generated, so you can test it with 3+ people
from your audience (DESIGN.md). Needs only narration (real or DRY_RUN) and the temp track.
"""
from __future__ import annotations

from . import audio, common as C, music, timeline


def make(sb: dict):
    tl = timeline.build(sb)
    temp = C.OUT / "music" / "temp_track.wav"
    if not temp.exists():
        music.make_temp_track(max(60, tl["total"] + 5))
    work = C.ensure("radiocut")
    narr = audio.build_narration_track(sb, tl)
    audio.write_wav(work / "narration_raw.wav", narr)
    mx = sb["config"]["mix"]
    narr = audio.gain_to(narr, work / "narration_raw.wav", mx.get("narration_prelevel_lufs", -16))
    audio.write_wav(work / "narration.wav", narr)
    temp_arr = audio.gain_to(audio.read_audio(temp), temp, mx.get("music_prelevel_lufs", -24))
    temp_leveled = work / "temp_leveled.wav"
    audio.write_wav(temp_leveled, temp_arr)
    fc = ("[0:a]asplit=2[n1][n2];"
          f"[1:a][n1]sidechaincompress=threshold={mx.get('duck_threshold', 0.02)}:ratio={mx.get('duck_ratio', 6)}:"
          f"attack={mx.get('duck_attack_ms', 300)}:release={mx.get('duck_release_ms', 1500)}[d];[d][n2]amix=inputs=2:normalize=0[out]")
    out = C.ensure("final") / "radio_cut.mp4"
    C.run(["ffmpeg", "-y", "-v", "error", "-i", str(work / "narration.wav"), "-stream_loop", "-1", "-i", str(temp_leveled),
           "-f", "lavfi", "-i", f"color=c=black:s=1280x720:r=24", "-filter_complex", fc,
           "-map", "2:v", "-map", "[out]", "-t", f"{tl['total'] - tl['end_dur']:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", str(out)])
    print(f"[radiocut] {out.relative_to(C.ROOT)}  ({tl['total'] - tl['end_dur']:.1f}s). Play it to 3+ people and write the notes in DESIGN.md.")
    return out


if __name__ == "__main__":
    make(C.load_storyboard())
