"""Parsers for OpenROAD-flow-scripts (ORFS) run outputs.

ORFS writes, per flow *step* (e.g. ``3_3_place_gp``):

* ``<step>.log`` -- tool output; each command ends with a line such as
  ``Elapsed time: 0:04.26[h:]min:sec. CPU time: user 4.08 sys 0.17 (99%). Peak memory: 671508KB.``
  (emitted by ORFS's ``scripts/run_command.py``; measured inside the container).
* ``<step>.json`` -- METRICS2.1-style flat key/value metrics (``stage__category__metric``).

These parsers treat every file as untrusted text: they never evaluate content, they bound
what they read, and they skip malformed values instead of raising.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

MAX_LOG_BYTES = 64 * 1024 * 1024  # refuse to slurp pathological logs
MAX_JSON_BYTES = 8 * 1024 * 1024

ELAPSED_RE = re.compile(
    r"Elapsed time: (?:(?P<h>\d+):)?(?P<m>\d+):(?P<s>\d+(?:\.\d+)?)\[h:\]min:sec\. "
    r"CPU time: user (?P<user>\d+(?:\.\d+)?) sys (?P<sys>\d+(?:\.\d+)?) \(\d+%\)\. "
    r"Peak memory: (?P<peak>\d+)KB\."
)
STEP_RE = re.compile(r"^(?P<stage>[1-6])_(?P<rest>[A-Za-z0-9_]+)$")

STAGE_NAMES = {
    "1": "synth",
    "2": "floorplan",
    "3": "place",
    "4": "cts",
    "5": "route",
    "6": "finish",
}
# Canonical flow order, used for "knowledge horizon" features later.
STAGE_ORDER = ("synth", "floorplan", "place", "cts", "route", "finish")


@dataclass(frozen=True)
class StepTiming:
    wall_s: float
    user_s: float
    sys_s: float
    peak_rss_mb: float
    n_commands: int  # number of timed commands found in the log


def stage_of(step: str) -> str:
    """Map an ORFS step name (``3_3_place_gp``) to its flow stage (``place``)."""
    match = STEP_RE.match(step)
    if match is None:
        return "other"
    return STAGE_NAMES[match.group("stage")]


def step_sort_key(step: str) -> tuple[int, str]:
    stage = stage_of(step)
    idx = STAGE_ORDER.index(stage) if stage in STAGE_ORDER else len(STAGE_ORDER)
    return idx, step


def _read_text(path: Path, limit: int) -> str:
    with open(path, "rb") as fh:
        data = fh.read(limit + 1)
    if len(data) > limit:
        data = data[-limit:]  # keep the tail: timing lines are written last
    return data.decode("utf-8", errors="replace")


def parse_elapsed_lines(text: str) -> StepTiming | None:
    """Aggregate all timed commands in one step log.

    A step may run several timed commands; wall and CPU times add up, peak memory is the
    maximum (commands run sequentially within a step).
    """
    wall = user = sys_ = 0.0
    peak_kb = 0
    n = 0
    for m in ELAPSED_RE.finditer(text):
        hours = int(m.group("h") or 0)
        wall += hours * 3600 + int(m.group("m")) * 60 + float(m.group("s"))
        user += float(m.group("user"))
        sys_ += float(m.group("sys"))
        peak_kb = max(peak_kb, int(m.group("peak")))
        n += 1
    if n == 0:
        return None
    return StepTiming(wall, user, sys_, peak_kb / 1024.0, n)


def parse_step_log(path: Path) -> StepTiming | None:
    return parse_elapsed_lines(_read_text(path, MAX_LOG_BYTES))


def parse_step_metrics(path: Path) -> dict[str, float | str]:
    """Load a METRICS2.1 step JSON as a flat dict of finite numbers / short strings."""
    try:
        raw = json.loads(_read_text(path, MAX_JSON_BYTES))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float | str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or len(key) > 200:
            continue
        if isinstance(value, bool):
            out[key] = float(value)
        elif isinstance(value, int | float):
            if math.isfinite(value):
                out[key] = float(value)
        elif isinstance(value, str) and len(value) <= 200:
            out[key] = value
    return out


@dataclass(frozen=True)
class StepOutput:
    step: str
    stage: str
    timing: StepTiming | None
    metrics: dict[str, float | str]
    log_path: Path | None


def collect_steps(log_dir: Path) -> list[StepOutput]:
    """Collect timing + metrics for every step found in an ORFS log directory."""
    log_dir = Path(log_dir)
    if not log_dir.is_dir():
        return []
    steps: dict[str, StepOutput] = {}
    names = {p.stem for p in log_dir.glob("*.log")} | {p.stem for p in log_dir.glob("*.json")}
    for name in names:
        log_path = log_dir / f"{name}.log"
        json_path = log_dir / f"{name}.json"
        timing = parse_step_log(log_path) if log_path.is_file() else None
        metrics = parse_step_metrics(json_path) if json_path.is_file() else {}
        steps[name] = StepOutput(
            step=name,
            stage=stage_of(name),
            timing=timing,
            metrics=metrics,
            log_path=log_path if log_path.is_file() else None,
        )
    return [steps[k] for k in sorted(steps, key=step_sort_key)]
