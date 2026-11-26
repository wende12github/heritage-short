"""Local web showcase & family story studio:  python -m pipeline.web  (or `make web`)

Serves the static UI in web/ alongside read-only views of storyboard.json, runs.jsonl, and outputs/.
Blocks sensitive paths (.env, .git, .venv, *.key) and supports HTTP byte-range requests for MP4 seeking.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from . import assemble, common as C, music, script as script_stage

WEB_ROOT = C.CODE_ROOT / "web"
ALLOWED_OUTPUT_DIRS = ("final", "keyframes", "reference", "narration", "music", "clips")


def _safe_file(url_path: str) -> Path | None:
    rel = unquote(urlparse(url_path).path).lstrip("/")
    if not rel:
        rel = "index.html"
    # Serve web/ assets at root, or allow explicit read-only access to outputs/
    if rel.startswith("outputs/"):
        parts = Path(rel).parts
        if len(parts) < 3 or parts[1] not in ALLOWED_OUTPUT_DIRS:
            return None
        target = (C.ROOT / rel).resolve()
        base = C.OUT.resolve()
    else:
        target = (WEB_ROOT / rel).resolve()
        base = WEB_ROOT.resolve()
    if not target.is_relative_to(base) or not target.is_file():
        return None
    if target.name.startswith(".") or target.suffix == ".key":
        return None
    return target


def _collect_state() -> dict:
    sb = C.load_storyboard() if C.STORYBOARD.exists() else None
    runs = C.read_runs()
    final = C.OUT / "final"
    refs = sorted((C.OUT / "reference").glob("*.jpg")) if (C.OUT / "reference").exists() else []
    clips = [p.stem for p in sorted((C.OUT / "clips").glob("*.mp4"))] if (C.OUT / "clips").exists() else []
    cands = []
    cand_root = C.OUT / "music" / "candidates"
    if cand_root.exists():
        for wav in sorted(cand_root.rglob("*.wav")):
            cands.append({
                "cue": wav.parent.name,
                "name": wav.name,
                "relPath": str(wav.relative_to(C.ROOT)),
                "url": "/" + str(wav.relative_to(C.ROOT)),
            })
    chosen = {}
    choices_log = C.OUT / "music" / "choices.jsonl"
    if choices_log.exists():
        for line in choices_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                chosen[rec["cue"]] = rec["file"]

    return {
        "storyboard": sb,
        "runs": runs,
        "files": {
            "vertical": "/outputs/final/film_vertical_9x16.mp4" if (final / "film_vertical_9x16.mp4").exists() else None,
            "horizontal": "/outputs/final/film_horizontal_16x9.mp4" if (final / "film_horizontal_16x9.mp4").exists() else None,
            "radio": "/outputs/final/radio_cut.mp4" if (final / "radio_cut.mp4").exists() else None,
            "srt": "/outputs/final/film.srt" if (final / "film.srt").exists() else None,
            "references": ["/" + str(p.relative_to(C.ROOT)) for p in refs],
            "clips": clips,
            "musicCandidates": cands,
            "chosenMusic": chosen,
            "basePrefix": "/",
        },
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"[web] {args[0]} {args[1]}")

    def _send_json(self, obj: dict, code: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path) -> None:
        ctype, _ = mimetypes.guess_type(str(path))
        size = path.stat().st_size
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        status = HTTPStatus.OK
        if rng:
            m = re.match(r"bytes=(\d+)-(\d*)", rng)
            if m:
                start = int(m.group(1))
                end = int(m.group(2)) if m.group(2) else size - 1
                end = min(end, size - 1)
                if start <= end:
                    status = HTTPStatus.PARTIAL_CONTENT
        length = max(0, end - start + 1)
        self.send_response(status)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/api/state":
            self._send_json(_collect_state())
            return
        path = _safe_file(self.path)
        if path is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        self._send_file(path)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}") if length else {}
        route = urlparse(self.path).path
        try:
            if route == "/api/assemble":
                rep = assemble.assemble(C.load_storyboard())
                self._send_json({"ok": True, "report": rep})
            elif route == "/api/select-music":
                src = (C.ROOT / body["file"]).resolve()
                if not src.is_relative_to((C.OUT / "music").resolve()) or not src.is_file():
                    self._send_json({"error": "invalid candidate path"}, 400)
                    return
                music.choose(body["cue"], str(src), body["why"])
                self._send_json({"ok": True})
            elif route == "/api/draft-story":
                story_txt = (
                    f"Title: {body.get('title', '')}\n"
                    f"Audience: {body.get('audience', '')}\n"
                    f"Voice: {body.get('voice', 'Charon')}\n"
                    f"Real person depicted: {bool(body.get('real_person'))}\n\n"
                    f"{body.get('story', '')}"
                )
                sb = script_stage.draft(story_txt, body.get("language_name", "Amharic"))
                out = C.ROOT / "storyboard.draft.json"
                out.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")
                self._send_json({"ok": True, "path": out.name, "shots": len(sb["shots"])})
            else:
                self._send_json({"error": "unknown endpoint"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    print(f"[web] Heritage Short Studio running at http://{a.host}:{a.port} (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[web] stopped.")


if __name__ == "__main__":
    main()
