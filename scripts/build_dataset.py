"""Freeze an analysis dataset from the run registry (docs/experiments.md §0).

Usage: SILICONAI_HOME=workspace/d1 python scripts/build_dataset.py --out data/d1/d1_v1.parquet

Writes the Parquet table plus ``<name>.manifest.json`` (content hash, counts, exclusions).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from siliconai.config import Settings
from siliconai.data.dataset import build_table, content_hash
from siliconai.data.registry import Registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--tool-image", default=None)
    args = parser.parse_args()
    with Registry(Settings.from_env().db_path) as reg:
        df = build_table(reg, tool_image=args.tool_image)
        status_counts: dict[str, int] = {}
        for r in reg.runs():
            status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    manifest = {
        "file": args.out.name,
        "content_hash": content_hash(df),
        "rows": len(df),
        "columns": df.shape[1],
        "design_groups": sorted(df["meta__design_group"].unique().tolist()),
        "designs": int(df["meta__design_id"].nunique()),
        "platforms": sorted(df["meta__platform"].unique().tolist()),
        "registry_status_counts": status_counts,
    }
    manifest_path = args.out.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
