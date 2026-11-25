"""Validate storyboard.json against schema/storyboard.schema.json, then run cross-field checks.

Uses `jsonschema` when installed; otherwise falls back to a small built-in validator that
supports the subset of JSON Schema this project uses (so the pipeline never skips validation).

Cross-field rules that JSON Schema cannot express:
  * shot ids unique and sequential (s01, s02, ...)
  * every shot character exists; every music cue / shot reference exists
  * CONSENT GATE: a character with real_person=true needs a consent_ref that appears in
    ETHICS.md as a recorded consent (the brief says: no consent record -> film scores zero)
  * estimated film length is within 60-90 s (warning, not error)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import common as C


# ------------------------------------------------------------- minimal fallback validator
def _type_ok(v, t):
    return {"object": isinstance(v, dict), "array": isinstance(v, list), "string": isinstance(v, str),
            "integer": isinstance(v, int) and not isinstance(v, bool),
            "number": isinstance(v, (int, float)) and not isinstance(v, bool),
            "boolean": isinstance(v, bool)}.get(t, True)


def _mini_validate(inst, schema, path="$"):
    errs = []
    t = schema.get("type")
    if t and not _type_ok(inst, t):
        return [f"{path}: expected {t}, got {type(inst).__name__}"]
    if "enum" in schema and inst not in schema["enum"]:
        errs.append(f"{path}: {inst!r} not in {schema['enum']}")
    if isinstance(inst, str):
        if len(inst) < schema.get("minLength", 0):
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], inst):
            errs.append(f"{path}: {inst!r} does not match {schema['pattern']}")
    if isinstance(inst, (int, float)) and not isinstance(inst, bool):
        if "minimum" in schema and inst < schema["minimum"]:
            errs.append(f"{path}: {inst} < minimum {schema['minimum']}")
        if "maximum" in schema and inst > schema["maximum"]:
            errs.append(f"{path}: {inst} > maximum {schema['maximum']}")
    if isinstance(inst, list):
        if len(inst) < schema.get("minItems", 0):
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if len(inst) > schema.get("maxItems", 10**9):
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, x in enumerate(inst):
                errs += _mini_validate(x, schema["items"], f"{path}[{i}]")
    if isinstance(inst, dict):
        for r in schema.get("required", []):
            if r not in inst:
                errs.append(f"{path}: missing required property '{r}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for k in inst:
                if k not in props:
                    errs.append(f"{path}: unexpected property '{k}'")
        for k, sub in props.items():
            if k in inst:
                errs += _mini_validate(inst[k], sub, f"{path}.{k}")
    return errs


def schema_errors(sb: dict) -> list[str]:
    schema = json.loads(C.SCHEMA.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore
        v = jsonschema.Draft202012Validator(schema)
        return [f"${'.' + '.'.join(map(str, e.absolute_path)) if e.absolute_path else ''}: {e.message}"
                for e in sorted(v.iter_errors(sb), key=lambda e: list(map(str, e.absolute_path)))]
    except ImportError:
        return _mini_validate(sb, schema)


# ------------------------------------------------------------------ cross-field checks
def consent_recorded(ref: str) -> bool:
    ethics = C.ROOT / "ETHICS.md"
    if not ethics.exists():
        return False
    for line in ethics.read_text(encoding="utf-8").splitlines():
        if ref in line and "RECORDED" in line.upper() and "NOT RECORDED" not in line.upper() and "TEMPLATE" not in line.upper():
            return True
    return False


def semantic_errors(sb: dict) -> tuple[list[str], list[str]]:
    errs, warns = [], []
    ids = [s["id"] for s in sb["shots"]]
    if len(set(ids)) != len(ids):
        errs.append("shot ids are not unique")
    if ids != [f"s{i:02d}" for i in range(1, len(ids) + 1)]:
        errs.append(f"shot ids must be sequential s01..s{len(ids):02d}, got {ids}")
    chars = {c["id"]: c for c in sb["characters"]}
    for s in sb["shots"]:
        for cid in s["characters"]:
            if cid not in chars:
                errs.append(f"{s['id']}: unknown character '{cid}'")
        used = set(re.findall(r"\{([a-z][a-z0-9_]*)\}", s["keyframe_prompt"]))
        if used != set(s["characters"]):
            errs.append(f"{s['id']}: keyframe_prompt placeholders {sorted(used)} must match characters {s['characters']}")
        if re.search(r"in the style of", s["keyframe_prompt"], re.I):
            warns.append(f"{s['id']}: prompt names an artist style; describe qualities instead (see ETHICS.md)")
    cue_ids = {c["id"] for c in sb["music"]["cues"]}
    for s in sb["shots"]:
        if s["music_cue"] not in cue_ids:
            errs.append(f"{s['id']}: unknown music_cue '{s['music_cue']}'")
    for c in sb["music"]["cues"]:
        for k in ("start_shot", "end_shot"):
            if c[k] not in ids:
                errs.append(f"cue {c['id']}: {k} '{c[k]}' is not a shot")
        if c["start_shot"] in ids and c["end_shot"] in ids and ids.index(c["start_shot"]) > ids.index(c["end_shot"]):
            errs.append(f"cue {c['id']}: start_shot after end_shot")
    # consent gate
    for c in sb["characters"]:
        if c["real_person"]:
            ref = c.get("consent_ref")
            if not ref:
                errs.append(f"CONSENT GATE: character '{c['id']}' is a real person but has no consent_ref")
            elif not consent_recorded(ref):
                errs.append(f"CONSENT GATE: {ref} for '{c['id']}' is not marked RECORDED in ETHICS.md")
    # length estimate (2.2 words/s is a rough default; real timing comes from the TTS files)
    est = sum(max(s["duration_s"], len(s["narration"]["text"].split()) / 2.2) for s in sb["shots"]) + sb["end_card"]["duration_s"]
    if not 60 <= est <= 90:
        warns.append(f"estimated length {est:.0f}s is outside 60-90s (shot durations + end card)")
    if sb.get("language", {}).get("needs_native_review"):
        warns.append("narration is flagged needs_native_review: have a native speaker listen before release")
    if "_note" in sb:
        warns.append(f"storyboard note: {sb['_note']}")
    return errs, warns


def validate(sb: dict | None = None, quiet: bool = False) -> bool:
    sb = sb or C.load_storyboard()
    errs = schema_errors(sb)
    warns: list[str] = []
    if not errs:
        e2, warns = semantic_errors(sb)
        errs += e2
    if not quiet:
        for w in warns:
            print(f"[validate] warning: {w}")
        for e in errs:
            print(f"[validate] ERROR: {e}")
        print("[validate] OK" if not errs else f"[validate] FAILED with {len(errs)} error(s)")
    return not errs


def main() -> None:
    sys.exit(0 if validate() else 1)


if __name__ == "__main__":
    main()
