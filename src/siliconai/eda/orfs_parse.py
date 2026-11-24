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
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

MAX_LOG_BYTES = 64 * 1024 * 1024  # refuse to slurp pathological logs
MAX_JSON_BYTES = 8 * 1024 * 1024

ELAPSED_RE = re.compile(
    r"Elapsed time: (?:(?P<h>\d+):)?(?P<m>\d+):(?P<s>\d+(?:\.\d+)?)\[h:\]min:sec\. "
    r"CPU time: user (?P<user>\d+(?:\.\d+)?) sys (?P<sys>\d+(?:\.\d+)?) \(\d+%\)\. "
    r"Peak memory: (?P<peak>\d+)KB\."
)
# ORFS writes some steps (e.g. detailed route) to "<step>.tmp.log" and renames the file when the
# step finishes; a run killed mid-step leaves the .tmp file behind. It is recorded as that step,
# unfinished (no timing line).
IN_PROGRESS_SUFFIX = ".tmp"
STEP_NAME_RE = re.compile(r"[A-Za-z0-9_]{1,64}")  # same rule as StepRecord.step
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


def _line_values(m: re.Match) -> tuple[float, float, float, int]:
    hours = int(m.group("h") or 0)
    wall = hours * 3600 + int(m.group("m")) * 60 + float(m.group("s"))
    return wall, float(m.group("user")), float(m.group("sys")), int(m.group("peak"))


def elapsed_lines(text: str) -> list[str]:
    """The exact text of every timing line in a log, in order."""
    return [m.group(0) for m in ELAPSED_RE.finditer(text)]


def parse_elapsed_lines(text: str, nested: frozenset[str] = frozenset()) -> StepTiming | None:
    """Aggregate the timed commands of one step log.

    Commands of a step run one after another, so wall and CPU times add up and peak memory is
    the maximum. Lines listed in ``nested`` belong to *another* step that ran inside one of this
    step's commands: ORFS echoes the sub-step's output, timing line included, into the parent's
    log (e.g. the ``4_rsz_lec`` equivalence check inside ``4_1_cts``). The enclosing command's
    line already includes that time, so it is subtracted. The sub-step keeps its own
    measurement, and the steps of a run then add up without double counting.
    """
    own: list[tuple[float, float, float, int]] = []
    inner = [0.0, 0.0, 0.0]
    for m in ELAPSED_RE.finditer(text):
        values = _line_values(m)
        if m.group(0) in nested:
            inner = [a + b for a, b in zip(inner, values[:3], strict=True)]
        else:
            own.append(values)
    if not own:
        return None
    wall, user, sys_ = (sum(v[i] for v in own) for i in range(3))
    if wall - inner[0] < 0 or user - inner[1] < 0 or sys_ - inner[2] < 0:
        # Not actually enclosed: fall back to treating every line as a sequential command.
        log.warning("nested timing exceeds its enclosing command; summing all lines instead")
        wall, user, sys_ = wall + inner[0], user + inner[1], sys_ + inner[2]
    else:
        wall, user, sys_ = wall - inner[0], user - inner[1], sys_ - inner[2]
    return StepTiming(wall, user, sys_, max(v[3] for v in own) / 1024.0, len(own))


def parse_step_log(path: Path, nested: frozenset[str] = frozenset()) -> StepTiming | None:
    return parse_elapsed_lines(_read_text(path, MAX_LOG_BYTES), nested)


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
    # A step whose own timing line also appears in another step's log ran nested inside it.
    lines = {
        name: elapsed_lines(_read_text(log_dir / f"{name}.log", MAX_LOG_BYTES))
        for name in names
        if (log_dir / f"{name}.log").is_file()
    }
    # Candidate sub-steps: valid step names whose log holds exactly one timed command.
    substep_line = {
        name: found[0]
        for name, found in lines.items()
        if len(found) == 1 and STEP_NAME_RE.fullmatch(name.removesuffix(IN_PROGRESS_SUFFIX))
    }
    for name in names:
        step = name.removesuffix(IN_PROGRESS_SUFFIX)
        if step != name and step in names:
            continue  # the finished step's files win over a leftover in-progress log
        if not STEP_NAME_RE.fullmatch(step):
            continue  # not an ORFS step file; untrusted names never reach the registry
        log_path = log_dir / f"{name}.log"
        json_path = log_dir / f"{name}.json"
        mine = lines.get(name, [])
        nested = frozenset(
            line for other, line in substep_line.items() if other != name and line in mine
        )
        if len(nested) >= len(mine):  # a parent must have a command of its own
            nested = frozenset()
        timing = parse_step_log(log_path, nested) if log_path.is_file() else None
        metrics = parse_step_metrics(json_path) if json_path.is_file() else {}
        steps[step] = StepOutput(
            step=step,
            stage=stage_of(step),
            timing=timing,
            metrics=metrics,
            log_path=log_path if log_path.is_file() else None,
        )
    return [steps[k] for k in sorted(steps, key=step_sort_key)]
