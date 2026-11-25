"""One command for the whole film:  python -m pipeline.run_all   (or `make film`)

  validate -> narration -> keyframes -> shots (plan/status) -> music (temp fallback) -> assemble

  --dry-run         no keys needed: placeholder frames + synthetic voice, real FFmpeg assembly
  --only STAGE      run one stage (validate|narration|keyframes|shots|music|assemble|radiocut)
  --shot s04 ...    restrict narration/keyframes to these shots (everything else stays cached)
  --force           ignore the cache for the selected shots
Re-running after editing one shot in storyboard.json regenerates only that shot.
"""
from __future__ import annotations

import argparse
import os
import sys

from . import common as C


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["validate", "narration", "keyframes", "shots", "music", "assemble", "radiocut"])
    ap.add_argument("--shot", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        os.environ["DRY_RUN"] = "1"
    from . import assemble, keyframes, music, narration, radiocut, shots, validate

    sb = C.load_storyboard()
    if not validate.validate(sb):
        sys.exit(1)
    stages = {
        "narration": lambda: narration.run(sb, a.shot, a.force),
        "keyframes": lambda: keyframes.run(sb, a.shot, a.force),
        "shots": lambda: shots.run(sb),
        "music": lambda: (music.make_temp_track() if not any((C.OUT / "music" / "chosen").glob("*.wav")) else None),
        "radiocut": lambda: radiocut.make(sb),
        "assemble": lambda: assemble.assemble(sb),
    }
    order = ["narration", "keyframes", "shots", "music", "assemble"]
    for name in ([a.only] if a.only and a.only != "validate" else [] if a.only == "validate" else order):
        print(f"\n=== {name} ===")
        stages[name]()
    if not a.only:
        print("\nDone. Film files are in outputs/final/ (see render_report.json).")


if __name__ == "__main__":
    main()
