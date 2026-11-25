"""Load a run's logs as an ordered list of lines, safely (Phase 3).

A run's diagnosis input is its ORFS step logs in flow order, followed by its console log (the
make output a user sees). Step logs are needed because some frontends write their only error
line there, not to the console.

Logs are untrusted input: each file is read up to ``MAX_FILE_BYTES``, decoded with replacement,
lines are cut to ``MAX_LINE_CHARS`` and the run to its last ``MAX_LINES`` lines (failures are
reported at the end). Only ``*.log`` files directly inside the run's log directory are read, and
symlinks are skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from siliconai.eda.orfs_parse import step_sort_key

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_LINE_CHARS = 1000
MAX_LINES = 60_000


@dataclass(frozen=True)
class Line:
    source: str  # "console" or the step log name, e.g. "5_1_grt"
    no: int  # 1-based line number within its source
    text: str


def _read(path: Path) -> list[str]:
    if path.is_symlink() or not path.is_file():
        return []
    with path.open("rb") as f:
        data = f.read(MAX_FILE_BYTES)
    return [ln[:MAX_LINE_CHARS] for ln in data.decode("utf-8", "replace").splitlines()]


def load_run_lines(console: Path | None, log_dir: Path | None) -> list[Line]:
    lines: list[Line] = []
    if log_dir is not None and Path(log_dir).is_dir() and not Path(log_dir).is_symlink():
        steps = sorted(
            (p for p in Path(log_dir).iterdir() if p.suffix == ".log"),
            key=lambda p: step_sort_key(p.stem),
        )
        for p in steps:
            lines += [Line(p.stem, i + 1, t) for i, t in enumerate(_read(p))]
    if console is not None:
        lines += [Line("console", i + 1, t) for i, t in enumerate(_read(Path(console)))]
    return lines[-MAX_LINES:]
