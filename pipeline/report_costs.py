"""Aggregate runs.jsonl into the measurement tables for COSTS.md.

  python -m pipeline.report_costs            print Markdown
  python -m pipeline.report_costs --write    also save to outputs/costs_tables.md

Dry-run records are excluded. List-price equivalents use pipeline/pricing.json (fill it from current price
pages, otherwise they show as 0). Free-tier quota you actually hit goes in COSTS.md by hand.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from . import common as C


def table() -> str:
    rows = [r for r in C.read_runs() if not r.get("dry_run") and r["stage"] != "smoke"]
    if not rows:
        return "_No real (non-dry-run) calls in runs.jsonl yet._\n"
    g = defaultdict(list)
    for r in rows:
        g[r["stage"]].append(r)
    out = ["| Stage | Model(s) | Calls | OK | Quota/fail | Mean latency (s) | Total latency (min) | GPU-min | List-price equiv. (USD) |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    tot_lat = tot_gpu = tot_usd = 0.0
    for stage, rs in g.items():
        ok = [r for r in rs if r["status"] == "ok"]
        lat = sum(r["latency_s"] for r in rs)
        gpu = sum(r.get("gpu_minutes", 0) for r in rs)
        usd = sum(r.get("list_price_usd", 0) for r in rs)
        mean = lat / len(rs) if rs else 0
        out.append(f"| {stage} | {', '.join(sorted({r['model'] for r in rs}))} | {len(rs)} | {len(ok)} | {len(rs) - len(ok)} | "
                   f"{mean:.1f} | {lat / 60:.1f} | {gpu:.1f} | {usd:.4f} |")
        tot_lat += lat; tot_gpu += gpu; tot_usd += usd
    out.append(f"| **total** | | {len(rows)} | | | | {tot_lat / 60:.1f} | {tot_gpu:.1f} | {tot_usd:.4f} |")
    retried = sum(1 for r in rows if r.get("attempts", 1) > 1)
    out.append(f"\nCalls needing a retry: {retried} of {len(rows)}. Cache hits make no model call and are not logged.")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    t = table()
    print(t)
    if a.write:
        (C.ensure() / "costs_tables.md").write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main()
