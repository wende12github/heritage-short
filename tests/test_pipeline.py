"""Offline tests (no keys, no GPU). Run: make test

They prove the claims the README makes: schema + consent gate are enforced, a re-run makes zero new
model calls, and editing one shot regenerates only that shot.
"""
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))


def load_sb():
    return json.loads((REPO / "storyboard.json").read_text(encoding="utf-8"))


class SchemaTests(unittest.TestCase):
    def setUp(self):
        from pipeline import validate
        self.v = validate

    def test_shipped_storyboard_is_valid(self):
        self.assertEqual(self.v.schema_errors(load_sb()), [])
        errs, _ = self.v.semantic_errors(load_sb())
        self.assertEqual(errs, [])

    def test_missing_field_fails(self):
        sb = load_sb()
        del sb["shots"][0]["reason"]
        self.assertTrue(any("reason" in e for e in self.v.schema_errors(sb)))

    def test_too_few_shots_fails(self):
        sb = load_sb()
        sb["shots"] = sb["shots"][:5]
        self.assertTrue(self.v.schema_errors(sb))

    def test_unknown_character_fails(self):
        sb = load_sb()
        sb["shots"][1]["characters"] = ["nobody"]
        errs, _ = self.v.semantic_errors(sb)
        self.assertTrue(any("unknown character" in e for e in errs))

    def test_consent_gate_blocks_real_person_without_record(self):
        sb = load_sb()
        sb["characters"][0]["real_person"] = True
        errs, _ = self.v.semantic_errors(sb)
        self.assertTrue(any("CONSENT GATE" in e for e in errs))
        sb["characters"][0]["consent_ref"] = "CONSENT-001"       # referenced but ETHICS.md only has the TEMPLATE row
        errs, _ = self.v.semantic_errors(sb)
        self.assertTrue(any("CONSENT GATE" in e for e in errs))


class SubtitleTests(unittest.TestCase):
    def test_wrapping_limits(self):
        from pipeline import timeline
        for text in ["short", "A fairly long sentence that definitely needs more than one line to fit on screen properly.",
                     "Word " * 40]:
            for cue in timeline.wrap_cues(text.strip(), 40):
                lines = cue.split("\n")
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(len(l) <= 40 for l in lines), cue)


class EndToEndDryRun(unittest.TestCase):
    """Copies the project to a temp dir and runs the real pipeline with DRY_RUN=1 (real FFmpeg)."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("ffmpeg") is None:
            raise unittest.SkipTest("ffmpeg not installed")
        cls.tmp = Path(tempfile.mkdtemp(prefix="heritage_"))
        shutil.copy(REPO / "storyboard.json", cls.tmp / "storyboard.json")
        shutil.copy(REPO / "ETHICS.md", cls.tmp / "ETHICS.md")
        cls.env = {**os.environ, "HERITAGE_ROOT": str(cls.tmp), "DRY_RUN": "1", "PYTHONPATH": str(REPO)}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_pipeline(self, *args):
        p = subprocess.run([sys.executable, "-m", "pipeline.run_all", "--dry-run", *args], cwd=REPO, env=self.env,
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout[-2000:] + p.stderr[-2000:])
        return p.stdout

    def runs(self):
        f = self.tmp / "runs.jsonl"
        return [json.loads(l) for l in f.read_text().splitlines()] if f.exists() else []

    def test_1_full_run_makes_both_formats_in_length(self):
        self.run_pipeline()
        report = json.loads((self.tmp / "outputs/final/render_report.json").read_text())
        self.assertTrue(60 <= report["length_s"] <= 90)
        self.assertEqual(set(report["files"]), {"vertical_9x16", "horizontal_16x9"})
        for rel in report["files"].values():
            self.assertTrue((self.tmp / rel).stat().st_size > 10_000)
        kinds = {r["stage"] for r in self.runs()}
        self.assertTrue({"narration", "keyframes", "assemble"} <= kinds)

    def test_2_rerun_makes_no_new_model_calls(self):
        n_shots = len(json.loads((self.tmp / "storyboard.json").read_text(encoding="utf-8"))["shots"])
        before = [r for r in self.runs() if r["stage"] in ("narration", "keyframes")]
        out = self.run_pipeline()
        after = [r for r in self.runs() if r["stage"] in ("narration", "keyframes")]
        self.assertEqual(len(before), len(after), out)
        self.assertIn(f"0 generated, {n_shots} cached", out)

    def test_3_editing_one_shot_regenerates_only_that_shot(self):
        sb = json.loads((self.tmp / "storyboard.json").read_text(encoding="utf-8"))
        sb["shots"][3]["keyframe_prompt"] += ", a red umbrella"
        sb["shots"][5]["narration"]["text"] += " ።"
        (self.tmp / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")
        n_before = len(self.runs())
        self.run_pipeline()
        new = self.runs()[n_before:]
        regenerated = sorted((r["stage"], r["shot"]) for r in new if r["stage"] in ("narration", "keyframes"))
        self.assertEqual(regenerated, [("keyframes", "s04"), ("narration", "s06")])

    def test_4_stale_clip_falls_back_but_film_still_renders(self):
        clips = self.tmp / "outputs/clips"
        clips.mkdir(parents=True, exist_ok=True)
        (clips / "s01.json").write_text(json.dumps({"input_hash": "stale"}))
        (clips / "s01.mp4").write_bytes(b"not a real clip")
        out = self.run_pipeline()
        self.assertIn("s01: Ken Burns fallback (stale)", out)


if __name__ == "__main__":
    unittest.main()
