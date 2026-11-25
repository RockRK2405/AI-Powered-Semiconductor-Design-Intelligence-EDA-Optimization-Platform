"""Run the pre-registered E5 (docs/experiments.md §11) on frozen D2.

Logs are read from the archives committed in data/d2 (extracted with the tarfile "data" filter
into a scratch directory), so the result is reproducible from the repository alone.

Usage: python scripts/run_e5.py --manifest data/d2/d2_v1.manifest.json --scratch <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from siliconai.log_intelligence.e5 import extract_archives, load_d2, load_natural, run_e5


def git_sha() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.stdout.strip() + ("-dirty" if dirty.strip() else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("experiments"))
    args = ap.parse_args()
    man = json.loads(args.manifest.read_text())
    d2 = args.manifest.parent
    for name, digest in man["log_archives"].items():  # verify archives against the manifest
        if hashlib.sha256((d2 / "logs" / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"{name} does not match the manifest")
    t0 = time.time()
    root = extract_archives(sorted((d2 / "logs").glob("*.tar.gz")), args.scratch / "d2")
    runs = load_d2(d2 / man["records"], root)
    nat_root = extract_archives([d2 / "natural" / "natural_logs.tar.gz"], args.scratch / "nat")
    natural = load_natural(d2 / "natural" / "natural_labels.yaml", nat_root)
    result = run_e5(runs, natural)
    rec = {
        "experiment": "e5",
        "dataset": str(args.manifest),
        "dataset_hash": man["content_hash"],
        "git_sha": git_sha(),
        "protocol": "docs/experiments.md §11",
        "seed": 0,
        "runtime_s": round(time.time() - t0, 1),
        "finished_at": datetime.now(UTC).isoformat(),
        "result": result,
    }
    path = args.out_dir / f"e5_{man['content_hash']}.json"
    path.write_text(json.dumps(rec, indent=2, sort_keys=True, default=str) + "\n")
    print(f"e5: wrote {path} ({rec['runtime_s']} s)")


if __name__ == "__main__":
    main()
