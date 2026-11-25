"""Probe every fault injector once on one development design (Phase 3, TODO P3-02).

The dev design (default gcd/nangate45) is excluded from E5 evaluation. Its logs are the only ones
used to write the keyword baseline and the gold evidence patterns (docs/experiments.md §11).

Usage:
  SILICONAI_HOME=workspace/d2probe SILICONAI_ORFS_IMAGE=<digest> \
    python scripts/probe_faults.py --out data/d2/probe/probe_gcd_nangate45.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

from siliconai.config import Settings
from siliconai.eda.collect import classify_status
from siliconai.eda.orfs import OrfsJob, run_orfs
from siliconai.log_intelligence.faults import (
    FAULTS,
    BaseDesign,
    build_faulted,
    bundled_base,
    image_file_reader,
    write_faulted,
)
from siliconai.sweep.runner import RUN_SUBDIRS, prune_artifacts

ERR_RE = re.compile(r"(\[ERROR|ERROR:|Error:|error:|\*\*\*|Killed|Terminated|not found)", re.I)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--only", default=None, help="comma-separated class/variant keys")
    # gcd/nangate45 clean run in this probe: 41.7 s wall, 559 MB peak step RSS
    ap.add_argument("--ref-wall", type=float, default=41.7)
    ap.add_argument("--ref-peak-mb", type=float, default=559.0)
    ap.add_argument("--slang", action="store_true", help="use the slang HDL frontend")
    args = ap.parse_args()
    s = Settings.from_env()
    reader = image_file_reader(s.orfs_image)
    base = bundled_base(
        "gcd",
        "nangate45",
        "gcd",
        ("src/gcd/gcd.v",),
        "src/gcd/gcd.v",
        "nangate45/gcd/constraint.sdc",
        reader,
    )
    base = BaseDesign(
        **{**base.__dict__, "ref_wall_s": args.ref_wall, "ref_peak_mb": args.ref_peak_mb}
    )
    if args.slang:  # dev probe of the slang frontend's messages (picorv32, uart use it)
        cfg = base.config_text + "export SYNTH_HDL_FRONTEND = slang\n"
        base = BaseDesign(**{**base.__dict__, "config_text": cfg, "group": "gcd_slang"})
    keys = list(FAULTS)
    if args.only:
        want = set(args.only.split(","))
        keys = [k for k in keys if "/".join(k) in want]
    gen_root = s.home / "faulted"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for cls, var in keys:
        fd = build_faulted(base, cls, var)
        d = write_faulted(fd, gen_root)
        variant = f"probe_{fd.dir_name}"
        job = OrfsJob(design_config=fd.design_config, variant=variant)
        prune_artifacts(s.runs_dir, fd.platform, variant, RUN_SUBDIRS)  # no stale results
        t0 = time.time()
        res = run_orfs(
            job,
            work_dir=s.runs_dir,
            image=s.orfs_image,
            timeout_s=fd.timeout_s or args.timeout,
            design_dir=d,
            memory_mb=fd.memory_mb,
        )
        console = res.log_path.read_text(errors="replace").splitlines()
        errs = [ln.strip()[:240] for ln in console if ERR_RE.search(ln)][:12]
        rec = {
            "fault_class": cls,
            "variant": var,
            "dir": fd.dir_name,
            "status": classify_status(res.exit_code, res.timed_out),
            "exit_code": res.exit_code,
            "wall_s": round(res.wall_s, 1),
            "console_lines": len(console),
            "error_lines": errs,
            "last_lines": [ln[:240] for ln in console[-4:]],
            "started": t0,
        }
        with args.out.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"{cls}/{var}: {rec['status']} exit={res.exit_code} {rec['wall_s']}s", flush=True)


if __name__ == "__main__":
    main()
