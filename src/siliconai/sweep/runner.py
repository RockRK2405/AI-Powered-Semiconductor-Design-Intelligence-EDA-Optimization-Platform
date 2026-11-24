"""Execute a sweep in budgeted, resumable chunks (TODO P2-01, P2-10, P2-11, P2-12).

One call of :func:`run_sweep` is one *chunk*: it walks the deterministic plan, skips runs that
already have a final status, and starts a run only if its expected duration fits in the
remaining budget. Runs execute one at a time (concurrency 1, the noise-safe setting measured in
the Phase 1 pilot). After each run, bulky ORFS artifacts are pruned and only logs/reports kept.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord
from siliconai.eda.collect import execute_and_record, orfs_design_record
from siliconai.eda.orfs import VARIANT_RE
from siliconai.rtlgen.generators import generate
from siliconai.rtlgen.orfs_design import write_orfs_design
from siliconai.sweep.preflight import ConfigReader, fixes_floorplan, incompatible_overrides
from siliconai.sweep.spec import DesignSpec, PlannedRun, SweepSpec, plan

log = logging.getLogger(__name__)

FINAL_STATUSES = frozenset({"success", "failed", "timeout"})
# Safety factor on the expected duration, and a fixed allowance for container start/stop.
ESTIMATE_FACTOR = 1.3
ESTIMATE_OVERHEAD_S = 30.0
PRUNED_SUBDIRS = ("results", "objects")
# Everything ORFS writes for one variant. Cleared before a (re)run so make cannot reuse an
# earlier attempt's results and stale logs cannot be mistaken for this run's steps.
RUN_SUBDIRS = ("results", "objects", "logs", "reports")

Executor = Callable[..., RunRecord]


@dataclass
class ChunkReport:
    planned: int = 0
    already_done: int = 0
    executed: Counter = field(default_factory=Counter)
    deferred_budget: int = 0
    rejected_preflight: list[str] = field(default_factory=list)
    stopped_reason: str | None = None

    @property
    def remaining(self) -> int:
        return (
            self.planned
            - self.already_done
            - sum(n for s, n in self.executed.items() if s in FINAL_STATUSES)
        )

    def summary(self) -> str:
        done = ", ".join(f"{k}={v}" for k, v in sorted(self.executed.items())) or "none"
        text = (
            f"planned={self.planned} already_done={self.already_done} executed[{done}] "
            f"deferred_budget={self.deferred_budget} remaining={self.remaining}"
        )
        if self.rejected_preflight:
            text += f" rejected_preflight={len(self.rejected_preflight)}"
        if self.stopped_reason:
            text += f" stopped: {self.stopped_reason}"
        return text


def expected_duration(registry: Registry, run: PlannedRun, spec: SweepSpec) -> float:
    """Best guess of a run's wall time: slowest recorded run of the same design, else the
    spec's ``expected_s``, else the full timeout (pessimistic for unmeasured designs)."""
    walls = [
        r["wall_s"]
        for r in registry.runs(run.design.design_id)
        if r["wall_s"] is not None and r["status"] in FINAL_STATUSES
    ]
    if walls:
        return max(walls)
    return run.design.expected_s or float(spec.timeout_s)


def prune_artifacts(
    work_dir: Path, platform: str, variant: str, subdirs: tuple[str, ...] = PRUNED_SUBDIRS
) -> int:
    """Delete one variant's ORFS outputs under ``subdirs`` (default: the bulky ``results/`` and
    ``objects/``; logs and reports are kept).

    Returns the number of directories removed. Paths are built from validated names and must
    resolve inside ``work_dir``.
    """
    if not VARIANT_RE.match(variant) or not VARIANT_RE.match(platform):
        raise ValueError("invalid platform/variant")
    root = Path(work_dir).resolve()
    removed = 0
    for sub in subdirs:
        for path in (root / sub / platform).glob(f"*/{variant}"):
            resolved = path.resolve()
            if path.is_symlink() or not resolved.is_relative_to(root):
                raise ValueError(f"refusing to delete outside work dir: {path}")
            shutil.rmtree(resolved)
            removed += 1
    return removed


def materialize_generated(spec: SweepSpec, gen_root: Path) -> dict[str, Path]:
    """Write every generated design of the spec; returns config path -> design directory."""
    out = {}
    for d in spec.designs:
        if d.generate:
            design = generate(d.generate.family, d.generate.params)
            out[d.config] = write_orfs_design(design, d.generate.platform, gen_root)
    return out


def design_record(d: DesignSpec) -> DesignRecord:
    if not d.generate:
        return orfs_design_record(d.config, d.group)
    params = json.dumps(d.generate.params, sort_keys=True)
    return DesignRecord(
        design_id=d.design_id,
        name=d.config.split("/")[3],
        platform=d.platform,
        origin="generated",
        source=f"siliconai.rtlgen {d.generate.family} {params}",
        design_group=d.group,
        license="MIT",
    )


def docker_healthy(timeout_s: int = 30) -> bool:
    try:
        proc = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def run_sweep(
    spec: SweepSpec,
    registry: Registry,
    *,
    work_dir: Path,
    image: str,
    budget_s: float,
    config_reader: ConfigReader,
    executor: Executor = execute_and_record,
    clock: Callable[[], float] = time.monotonic,
    health_check: Callable[[], bool] = docker_healthy,
    prune: bool = True,
    dry_run: bool = False,
    gen_root: Path | None = None,
) -> ChunkReport:
    """Run one budgeted chunk of the sweep. Safe to call repeatedly (resumable)."""
    start = clock()
    gen_dirs = materialize_generated(spec, gen_root) if gen_root else {}
    if any(d.generate for d in spec.designs) and not gen_root:
        raise ValueError("spec has generated designs: gen_root is required")
    config_texts = {
        d.config: (gen_dirs[d.config] / "config.mk").read_text()
        if d.config in gen_dirs
        else config_reader(d.config)
        for d in spec.designs
    }
    fixed = {cfg: fixes_floorplan(text) for cfg, text in config_texts.items()}
    planned = plan(spec, fixed)
    status = {r["run_id"]: r["status"] for r in registry.runs()}
    report = ChunkReport(planned=len(planned))

    for run in planned:
        if status.get(run.run_id) in FINAL_STATUSES:
            report.already_done += 1
            continue
        bad = incompatible_overrides(config_texts[run.design.config], run.overrides)
        if bad:  # cannot happen with plan(); guards hand-edited plans and future knobs
            report.rejected_preflight.append(f"{run.run_id}: {','.join(bad)}")
            continue
        remaining = budget_s - (clock() - start)
        need = expected_duration(registry, run, spec) * ESTIMATE_FACTOR + ESTIMATE_OVERHEAD_S
        if need > remaining:
            report.deferred_budget += 1
            continue
        if dry_run:
            report.executed["dry_run"] += 1
            continue
        if not health_check():
            report.stopped_reason = "docker daemon not reachable"
            break
        timeout = int(min(spec.timeout_s, remaining - ESTIMATE_OVERHEAD_S))
        if prune_artifacts(work_dir, run.design.platform, run.run_id, RUN_SUBDIRS):
            log.info("%s: cleared outputs of an earlier attempt", run.run_id)
        record = executor(
            registry,
            design_record(run.design),
            run.design.config,
            run.overrides,
            work_dir=work_dir,
            image=image,
            timeout_s=timeout,
            repeat_index=run.repeat_index,
            concurrency=1,
            skip_existing=False,
            target=spec.target,
            budget_capped=timeout < spec.timeout_s,
            design_dir=gen_dirs.get(run.design.config),
        )
        report.executed[record.status] += 1
        log.info("%s -> %s (%.0fs)", run.run_id, record.status, record.wall_s or 0)
        if prune:
            prune_artifacts(work_dir, run.design.platform, run.run_id)
        if record.status == "aborted" and not health_check():
            report.stopped_reason = "docker daemon not reachable"
            break
    return report
