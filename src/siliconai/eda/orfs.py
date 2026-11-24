"""Run OpenROAD-flow-scripts designs inside the official Docker image.

Why Docker: the image pins every tool (OpenROAD, OpenSTA, Yosys, KLayout) to one
reproducible build, identified by its digest (ADR-010). Each SiliconAI run gets its own
``FLOW_VARIANT`` so outputs of different runs never overwrite each other.

Security: design configs and flow-variable overrides are validated against allowlists
before they reach ``make``. Nothing user-supplied is interpolated into a shell string.
"""

from __future__ import annotations

import logging
import re
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from siliconai.eda.runner import ToolResult, run_tool

log = logging.getLogger(__name__)

ORFS_ROOT = "/OpenROAD-flow-scripts"
ORFS_FLOW = f"{ORFS_ROOT}/flow"
CONTAINER_WORK = "/work"
# Equivalent of sourcing ORFS env.sh, so we can exec `make` directly (no `bash -c`).
ORFS_PATH = ":".join(
    [
        f"{ORFS_ROOT}/.venv/bin",
        f"{ORFS_ROOT}/tools/install/kepler-formal/bin",
        f"{ORFS_ROOT}/tools/install/yosys/bin",
        f"{ORFS_ROOT}/tools/install/OpenROAD/bin",
        "/opt/orfs-python/bin",
        "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    ]
)

DESIGN_CONFIG_RE = re.compile(r"^\./designs/[A-Za-z0-9_]+/[A-Za-z0-9_]+/config\.mk$")
VARIANT_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
VALUE_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")

# Flow variables we allow sweeps to override. Extend deliberately, one at a time.
ALLOWED_OVERRIDES = frozenset(
    {
        "CORE_UTILIZATION",
        "CORE_ASPECT_RATIO",
        "PLACE_DENSITY",
        "PLACE_DENSITY_LB_ADDON",
        "ABC_AREA",
        "SYNTH_HIERARCHICAL",
        "NUM_CORES",
        "TNS_END_PERCENT",
        "GPL_TIMING_DRIVEN",
        "GPL_ROUTABILITY_DRIVEN",
        "SKIP_INCREMENTAL_REPAIR",
    }
)

TIMEOUT_EXIT_CODE = 124  # coreutils `timeout`


@dataclass(frozen=True)
class OrfsJob:
    design_config: str  # e.g. "./designs/nangate45/gcd/config.mk" (relative to flow/)
    variant: str  # unique per run -> FLOW_VARIANT
    overrides: Mapping[str, str] = field(default_factory=dict)
    target: str = "finish"

    def __post_init__(self) -> None:
        if not DESIGN_CONFIG_RE.match(self.design_config):
            raise ValueError(f"design_config not allowed: {self.design_config!r}")
        if not VARIANT_RE.match(self.variant):
            raise ValueError(f"variant not allowed: {self.variant!r}")
        if self.target not in {"synth", "floorplan", "place", "cts", "route", "finish"}:
            raise ValueError(f"target not allowed: {self.target!r}")
        for key, value in self.overrides.items():
            if key not in ALLOWED_OVERRIDES:
                raise ValueError(f"override not allowed: {key!r}")
            if not VALUE_RE.match(str(value)):
                raise ValueError(f"override value not allowed: {key}={value!r}")

    @property
    def platform(self) -> str:
        return self.design_config.split("/")[2]

    @property
    def design(self) -> str:
        return self.design_config.split("/")[3]

    def log_dir(self, work_dir: Path) -> Path:
        return Path(work_dir) / "logs" / self.platform / self.design / self.variant


def build_docker_argv(
    job: OrfsJob,
    *,
    work_dir: Path,
    image: str,
    inner_timeout_s: int,
    cpuset: str | None = None,
) -> list[str]:
    """Build the `docker run` argument list for one ORFS job."""
    if inner_timeout_s <= 0:
        raise ValueError("inner_timeout_s must be positive")
    if cpuset is not None and not re.fullmatch(r"[0-9,\-]{1,32}", cpuset):
        raise ValueError(f"invalid cpuset: {cpuset!r}")
    argv = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--name",
        container_name(job),
        "--network",
        "none",  # the flow needs no network; reduces blast radius
        "-v",
        f"{Path(work_dir).resolve()}:{CONTAINER_WORK}",
        "-w",
        ORFS_FLOW,
        "-e",
        f"PATH={ORFS_PATH}",
        "-e",
        f"FLOW_HOME={ORFS_FLOW}",
    ]
    if cpuset:
        argv += ["--cpuset-cpus", cpuset]
    argv += [
        image,
        "timeout",
        "--signal=TERM",
        "--kill-after=30",
        str(inner_timeout_s),
        "make",
        f"DESIGN_CONFIG={job.design_config}",
        f"WORK_HOME={CONTAINER_WORK}",
        f"FLOW_VARIANT={job.variant}",
    ]
    argv += [f"{k}={v}" for k, v in sorted(job.overrides.items())]
    argv.append(job.target)
    return argv


def container_name(job: OrfsJob) -> str:
    return f"siliconai_{job.variant}"


def run_orfs(
    job: OrfsJob,
    *,
    work_dir: Path,
    image: str,
    timeout_s: int,
    cpuset: str | None = None,
) -> ToolResult:
    """Execute one ORFS job. Timing per step is parsed separately from ORFS logs."""
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    argv = build_docker_argv(
        job, work_dir=work_dir, image=image, inner_timeout_s=timeout_s, cpuset=cpuset
    )
    console_log = work_dir / "console" / f"{job.variant}.log"
    # Outer timeout is a backstop for the inner coreutils timeout.
    result = run_tool(
        argv,
        cwd=work_dir,
        log_path=console_log,
        timeout_s=timeout_s + 120,
        measure=False,  # GNU time would measure the docker CLI, not the tools
    )
    if result.timed_out:
        # Killing the docker CLI does not stop the container; stop it explicitly.
        subprocess.run(
            ["docker", "kill", container_name(job)], capture_output=True, timeout=60, check=False
        )
    return result


def image_digest(image: str) -> str | None:
    """Return the repo digest of a local image (e.g. 'openroad/orfs@sha256:...')."""
    try:
        proc = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{index .RepoDigests 0}}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = proc.stdout.strip()
    return out or None
