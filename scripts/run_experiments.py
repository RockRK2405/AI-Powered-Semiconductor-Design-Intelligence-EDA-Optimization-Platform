"""Run pre-registered experiments E1-E4 on a frozen dataset and record them (ADR-006).

Usage: python scripts/run_experiments.py --data data/d1/d1_v1.parquet [--only e1,e3]

Each experiment writes experiments/<exp>_<dataset-hash>.json with params, dataset hash, git
SHA and seed. Numbers quoted anywhere in the docs must come from these files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from siliconai.data.dataset import content_hash
from siliconai.runtime_intelligence import experiments as ex


def git_sha() -> str:
    out = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False, timeout=30
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    ).stdout
    return out.stdout.strip() + ("-dirty" if dirty.strip() else "")


def to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--only", default="e1,e2,e3,e4")
    parser.add_argument("--out-dir", type=Path, default=Path("experiments"))
    args = parser.parse_args()
    df = pd.read_parquet(args.data)
    data_hash = content_hash(df)
    manifest = args.data.with_suffix(".manifest.json")
    if manifest.exists() and json.loads(manifest.read_text())["content_hash"] != data_hash:
        raise SystemExit("dataset does not match its manifest hash: refusing to run")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(args.only.split(","))
    e1_oof = None
    for name in ("e1", "e2", "e3", "e4"):
        if name not in wanted and not (name == "e1" and "e4" in wanted):
            continue
        t0 = time.monotonic()
        if name == "e1":
            result, e1_oof = ex.run_e1(df, seed=args.seed)
            if "e1" not in wanted:
                continue
        elif name == "e2":
            result = ex.run_e2(df, seed=args.seed)
        elif name == "e3":
            result = ex.run_e3(df, seed=args.seed)
        else:
            result = ex.run_e4(df, e1_oof, seed=args.seed)
        record = {
            "experiment": name,
            "protocol": "docs/experiments.md",
            "dataset": str(args.data),
            "dataset_hash": data_hash,
            "rows": len(df),
            "design_groups": int(df["meta__design_group"].nunique()),
            "git_sha": git_sha(),
            "seed": args.seed,
            "finished_at": datetime.now(UTC).isoformat(),
            "runtime_s": round(time.monotonic() - t0, 1),
            "result": result,
        }
        path = args.out_dir / f"{name}_{data_hash}.json"
        path.write_text(json.dumps(to_jsonable(record), indent=2, sort_keys=True) + "\n")
        print(f"{name}: wrote {path} ({record['runtime_s']} s)")


if __name__ == "__main__":
    main()
