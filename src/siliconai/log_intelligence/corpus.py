"""Collect the D2 fault-injected log corpus in budgeted, resumable chunks (TODO P3-03).

Plan = every (base design, fault) pair of the spec, minus each base's ``skip_faults``, in a
seed-shuffled order. A run's label (fault class and variant) is fixed by the plan before it runs;
its outcome is recorded after. Runs with a final status (success / failed / timeout) are never
repeated; ``aborted`` runs (Docker failures) are retried by the next chunk.

Records are appended to ``<SILICONAI_HOME>/d2_records.jsonl``. Logs stay in the ORFS work dir
(``console/<run_id>.log`` and ``logs/<platform>/<nickname>/<run_id>/``); ``results`` and
``objects`` are deleted after each run.
"""

from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from siliconai.eda.collect import classify_status
from siliconai.eda.host import host_fingerprint
from siliconai.eda.orfs import OrfsJob, image_digest, run_orfs
from siliconai.log_intelligence.faults import (
    FAULTS,
    BaseDesign,
    FaultedDesign,
    build_faulted,
    bundled_base,
    generated_base,
    write_faulted,
)
from siliconai.sweep.runner import RUN_SUBDIRS, docker_healthy, prune_artifacts

FINAL = frozenset({"success", "failed", "timeout"})
RTL_FRONTEND_FAULTS = (
    "syntax_error/*",
    "elaboration_error/*",
    "missing_file/include",
)
# Rough share of a clean run's wall time that each class takes before it stops, for budgeting
# only (from the dev probe); congestion can run long, so it is budgeted pessimistically.
COST_SHARE = {
    "syntax_error": 0.05,
    "elaboration_error": 0.05,
    "missing_file": 0.3,
    "sdc_error": 0.4,
    "floorplan_capacity": 0.5,
    "routing_resources": 2.0,
    "out_of_memory": 0.8,
    "timeout": 1.0,
    "none": 1.0,
}
ESTIMATE_FACTOR, ESTIMATE_OVERHEAD_S = 1.3, 20.0


@dataclass(frozen=True)
class PlannedFault:
    base: BaseDesign
    fault_class: str
    variant: str

    @property
    def run_id(self) -> str:
        return "d2_" + build_faulted(self.base, self.fault_class, self.variant).dir_name


def _skipped(skips: list[str], cls: str, var: str) -> bool:
    return any(s in (f"{cls}/{var}", f"{cls}/*") for s in skips)


def load_bases(spec: dict, reader: Callable[[str], str] | None) -> list[tuple[BaseDesign, list]]:
    out = []
    for b in spec["bases"]:
        skips = list(b.get("skip_faults", []))
        if b.get("slang"):
            skips += list(RTL_FRONTEND_FAULTS)
        if "generate" in b:
            g = b["generate"]
            base = generated_base(g["family"], g["params"], b["platform"], b["group"])
        else:
            if reader is None:
                raise ValueError("bundled bases need an image file reader")
            base = bundled_base(
                b["name"],
                b["platform"],
                b["group"],
                tuple(b["sources"]),
                b["top_file"],
                b["sdc"],
                reader,
                config=b.get("config"),
            )
        base = BaseDesign(
            **{**base.__dict__, "ref_wall_s": b["ref_wall_s"], "ref_peak_mb": b["ref_peak_mb"]}
        )
        out.append((base, skips))
    return out


def plan(bases: list[tuple[BaseDesign, list]], seed: int) -> list[PlannedFault]:
    runs = [
        PlannedFault(base, cls, var)
        for base, skips in bases
        for cls, var in FAULTS
        if not _skipped(skips, cls, var)
    ]
    random.Random(seed).shuffle(runs)  # noqa: S311 (run order, not crypto)
    return runs


def run_timeout(fd: FaultedDesign, base: BaseDesign, cap_s: int) -> int:
    """The timeout fault's own limit, else a cap scaled to the design's clean runtime."""
    if fd.timeout_s is not None:
        return fd.timeout_s
    return int(min(cap_s, max(300, 3 * (base.ref_wall_s or 100))))


def estimate_s(p: PlannedFault) -> float:
    return COST_SHARE[p.fault_class] * (p.base.ref_wall_s or 100) * ESTIMATE_FACTOR + (
        ESTIMATE_OVERHEAD_S
    )


def read_records(path: Path) -> dict[str, dict]:
    recs: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                recs[r["run_id"]] = r  # last record of a run wins (aborted, then retried)
    return recs


def collect(
    spec_path: Path,
    *,
    home: Path,
    image: str,
    budget_s: float,
    reader: Callable[[str], str] | None,
    clock: Callable[[], float] = time.monotonic,
    dry_run: bool = False,
) -> dict:
    spec = yaml.safe_load(Path(spec_path).read_text())
    bases = load_bases(spec, reader)
    planned = plan(bases, int(spec["seed"]))
    work_dir, fault_root = home / "runs", home / "faulted"
    rec_path = home / "d2_records.jsonl"
    done = {k for k, r in read_records(rec_path).items() if r["status"] in FINAL}
    report = {"planned": len(planned), "already_done": 0, "executed": {}, "deferred": 0}
    start = clock()
    digest = None if dry_run else (image_digest(image) or image)
    for p in planned:
        rid = p.run_id
        if rid in done:
            report["already_done"] += 1
            continue
        if estimate_s(p) > budget_s - (clock() - start):
            report["deferred"] += 1
            continue
        if dry_run:
            report["executed"]["dry_run"] = report["executed"].get("dry_run", 0) + 1
            continue
        if not docker_healthy():
            report["stopped"] = "docker daemon not reachable"
            break
        fd = build_faulted(p.base, p.fault_class, p.variant)
        d = write_faulted(fd, fault_root)
        job = OrfsJob(design_config=fd.design_config, variant=rid)
        prune_artifacts(work_dir, fd.platform, rid, RUN_SUBDIRS)
        started = datetime.now(UTC)
        timeout = run_timeout(fd, p.base, int(spec.get("cap_s", 1800)))
        res = run_orfs(
            job,
            work_dir=work_dir,
            image=image,
            timeout_s=timeout,
            design_dir=d,
            memory_mb=fd.memory_mb,
        )
        status = classify_status(res.exit_code, res.timed_out)
        log_dir = job.log_dir(work_dir)
        rec = {
            "run_id": rid,
            "base": p.base.name,
            "group": p.base.group,
            "platform": p.base.platform,
            "origin": p.base.origin,
            "fault_class": p.fault_class,
            "variant": p.variant,
            "memory_mb": fd.memory_mb,
            "timeout_s": timeout,
            "status": status,
            "exit_code": res.exit_code,
            "wall_s": round(res.wall_s, 2),
            "console_log": str(res.log_path.relative_to(work_dir)),
            "log_dir": str(log_dir.relative_to(work_dir)) if log_dir.is_dir() else None,
            "tool_image": digest,
            "host": host_fingerprint(),
            "started_at": started.isoformat(),
        }
        with rec_path.open("a") as f:
            f.write(json.dumps(rec, sort_keys=True) + "\n")
        report["executed"][status] = report["executed"].get(status, 0) + 1
        print(f"{rid} {p.fault_class}/{p.variant} -> {status} ({res.wall_s:.0f}s)", flush=True)
        prune_artifacts(work_dir, fd.platform, rid)  # keep logs and console, drop results
        if status == "aborted" and not docker_healthy():
            report["stopped"] = "docker daemon lost"
            break
    report["remaining"] = (
        report["planned"]
        - report["already_done"]
        - sum(v for k, v in report["executed"].items() if k in FINAL)
    )
    return report


def main() -> None:
    import argparse

    from siliconai.config import Settings
    from siliconai.log_intelligence.faults import image_file_reader

    ap = argparse.ArgumentParser(description="Collect a D2 chunk")
    ap.add_argument("spec", type=Path)
    ap.add_argument("--budget-min", type=float, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    s = Settings.from_env()
    s.home.mkdir(parents=True, exist_ok=True)
    rep = collect(
        args.spec,
        home=s.home,
        image=s.orfs_image,
        budget_s=args.budget_min * 60,
        reader=image_file_reader(s.orfs_image),
        dry_run=args.dry_run,
    )
    print("d2 " + json.dumps(rep, sort_keys=True))


if __name__ == "__main__":
    main()
