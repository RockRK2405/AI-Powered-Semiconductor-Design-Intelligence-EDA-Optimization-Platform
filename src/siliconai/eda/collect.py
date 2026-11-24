"""Execute an ORFS job and record the run plus per-step measurements in the registry."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord, stable_hash
from siliconai.eda.host import host_fingerprint
from siliconai.eda.orfs import TIMEOUT_EXIT_CODE, OrfsJob, image_digest, run_orfs
from siliconai.eda.orfs_parse import collect_steps

log = logging.getLogger(__name__)


def make_run_id(
    design_id: str, overrides: dict[str, str], repeat_index: int, target: str = "finish"
) -> str:
    """Deterministic run id: same design + config + target + repeat -> same id (resumable)."""
    suffix = "" if target == "finish" else f"_{target}"
    return f"{design_id}_{stable_hash(overrides)[:8]}_r{repeat_index}{suffix}"


DOCKER_DAEMON_ERROR = 125  # `docker run` itself failed (daemon gone, bad flags, ...)


def orfs_design_id(design_config: str) -> str:
    """``./designs/<platform>/<design>/config.mk`` -> ``<design>_<platform>``."""
    parts = design_config.split("/")
    if len(parts) != 5 or parts[1] != "designs":
        raise ValueError(f"not an ORFS design config path: {design_config!r}")
    return f"{parts[3]}_{parts[2]}"


def orfs_design_record(design_config: str, design_group: str | None = None) -> DesignRecord:
    """Design record for an ORFS design; the group defaults to the design directory name."""
    design_id = orfs_design_id(design_config)  # validates the path shape
    parts = design_config.split("/")
    return DesignRecord(
        design_id=design_id,
        name=parts[3],
        platform=parts[2],
        origin="orfs",
        source=f"ORFS {design_config}",
        design_group=design_group or parts[3],
        license=None,  # TODO(P0-R4): fill from flow/designs/src/<design>/LICENSE
    )


def classify_status(exit_code: int | None, timed_out: bool, budget_capped: bool = False) -> str:
    """Map a tool result to a run status.

    ``budget_capped``: the timeout was lowered below the sweep's own timeout to fit a chunk
    budget, so a timeout is our doing ("aborted"), not a property of the design.
    """
    if exit_code == DOCKER_DAEMON_ERROR:
        return "aborted"
    if timed_out or exit_code == TIMEOUT_EXIT_CODE:
        return "aborted" if budget_capped else "timeout"
    return "success" if exit_code == 0 else "failed"


def steps_from_log_dir(run_id: str, log_dir: Path) -> list[StepRecord]:
    records = []
    for out in collect_steps(log_dir):
        t = out.timing
        records.append(
            StepRecord(
                run_id=run_id,
                step=out.step,
                stage=out.stage,
                wall_s=t.wall_s if t else None,
                cpu_user_s=t.user_s if t else None,
                cpu_sys_s=t.sys_s if t else None,
                peak_rss_mb=t.peak_rss_mb if t else None,
                metrics=out.metrics,
                log_path=str(out.log_path) if out.log_path else None,
            )
        )
    return records


def execute_and_record(
    registry: Registry,
    design: DesignRecord,
    job_config: str,
    overrides: dict[str, str],
    *,
    work_dir: Path,
    image: str,
    timeout_s: int,
    repeat_index: int = 0,
    concurrency: int = 1,
    cpuset: str | None = None,
    skip_existing: bool = True,
    target: str = "finish",
    budget_capped: bool = False,
    design_dir: Path | None = None,
) -> RunRecord:
    run_id = make_run_id(design.design_id, overrides, repeat_index, target)
    if skip_existing:
        existing = [r for r in registry.runs(design.design_id) if r["run_id"] == run_id]
        if existing and existing[0]["status"] == "success":
            log.info("skip %s (already recorded as success)", run_id)
            return RunRecord(
                run_id=run_id,
                design_id=design.design_id,
                config=dict(overrides),
                status="success",
                repeat_index=repeat_index,
            )

    registry.upsert_design(design)
    job = OrfsJob(design_config=job_config, variant=run_id, overrides=overrides, target=target)
    started = datetime.now(UTC)
    log.info("run %s: %s %s", run_id, job_config, overrides or "")
    result = run_orfs(
        job,
        work_dir=work_dir,
        image=image,
        timeout_s=timeout_s,
        cpuset=cpuset,
        design_dir=design_dir,
    )
    status = classify_status(result.exit_code, result.timed_out, budget_capped)

    run = RunRecord(
        run_id=run_id,
        design_id=design.design_id,
        config=dict(overrides),
        tool_image=image_digest(image) or image,
        host=host_fingerprint(),
        concurrency=concurrency,
        repeat_index=repeat_index,
        status=status,  # type: ignore[arg-type]
        exit_code=result.exit_code,
        wall_s=result.wall_s,
        started_at=started,
    )
    try:
        steps = steps_from_log_dir(run_id, job.log_dir(work_dir))
    except ValueError:  # includes pydantic ValidationError: never lose the run itself
        log.exception("run %s: step records rejected; recording the run without steps", run_id)
        steps = []
    registry.record_run(run, steps)
    log.info("run %s: %s in %.1fs, %d steps recorded", run_id, status, result.wall_s, len(steps))
    return run


def recorded_log_dir(registry: Registry, run_id: str) -> Path | None:
    """The ORFS log directory a run's steps were parsed from (None if it is not on disk)."""
    dirs = {Path(s["log_path"]).parent for s in registry.steps(run_id) if s["log_path"]}
    if len(dirs) != 1:
        return None
    (log_dir,) = dirs
    return log_dir if log_dir.is_dir() and not log_dir.is_symlink() else None


def reparse_run(registry: Registry, run_id: str) -> tuple[float | None, float | None]:
    """Re-collect a recorded run's steps from its original logs with the current parser.

    Returns the run's summed step wall time (before, after). Run records (status, wall time,
    config) are not touched. Raises FileNotFoundError if the logs are not on disk.
    """
    log_dir = recorded_log_dir(registry, run_id)
    if log_dir is None:
        raise FileNotFoundError(f"logs of {run_id} are not available")
    before = [s["wall_s"] for s in registry.steps(run_id) if s["wall_s"] is not None]
    steps = steps_from_log_dir(run_id, log_dir)
    registry.replace_steps(run_id, steps)
    after = [s.wall_s for s in steps if s.wall_s is not None]
    return (sum(before) if before else None, sum(after) if after else None)
