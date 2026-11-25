"""Freeze D2 (docs/experiments.md §11 stopping rule): records + log archives -> manifest.

Usage: python scripts/freeze_d2.py --chunks 3 [--out data/d2/d2_v1.manifest.json]
Refuses to freeze if runs are still pending and fewer than 6 chunks were collected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

MAX_CHUNKS = 6


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", type=Path, default=Path("data/d2/records.jsonl"))
    ap.add_argument("--logs", type=Path, default=Path("data/d2/logs"))
    ap.add_argument("--planned", type=int, required=True, help="runs in the plan (333)")
    ap.add_argument("--chunks", type=int, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/d2/d2_v1.manifest.json"))
    args = ap.parse_args()
    recs: dict[str, dict] = {}
    for line in args.records.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            recs[r["run_id"]] = r
    final = {k: r for k, r in recs.items() if r["status"] in ("success", "failed", "timeout")}
    if len(final) < args.planned and args.chunks < MAX_CHUNKS:
        raise SystemExit(f"{len(final)}/{args.planned} runs final after {args.chunks} chunks")
    frozen = args.records.with_name("d2_v1_records.jsonl")
    frozen.write_text("".join(json.dumps(final[k], sort_keys=True) + "\n" for k in sorted(final)))
    archives = sorted(args.logs.glob("*.tar.gz"))
    h = hashlib.sha256(frozen.read_bytes())
    for a in archives:
        h.update(sha(a).encode())
    manifest = {
        "records": frozen.name,
        "content_hash": h.hexdigest()[:16],
        "runs_final": len(final),
        "runs_planned": args.planned,
        "chunks": args.chunks,
        "status_counts": dict(Counter(r["status"] for r in final.values())),
        "class_status_counts": {
            c: dict(Counter(r["status"] for r in final.values() if r["fault_class"] == c))
            for c in sorted({r["fault_class"] for r in final.values()})
        },
        "groups": sorted({r["group"] for r in final.values()}),
        "log_archives": {a.name: sha(a) for a in archives},
    }
    args.out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: manifest[k] for k in ("content_hash", "runs_final", "status_counts")}))


if __name__ == "__main__":
    main()
