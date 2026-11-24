"""Hardened subprocess execution for EDA tools.

Every external tool invocation in SiliconAI goes through :func:`run_tool`. It enforces the
security rules from ARCHITECTURE.md section 7:

* argv is a list -- never a shell string (no shell injection);
* the child gets an allowlisted environment (no API keys or tokens leak into tools);
* a wall-clock timeout kills the whole process group, not just the direct child;
* an optional address-space limit (used later for out-of-memory fault injection);
* stdout+stderr go to a log file, never into memory unbounded.

When GNU time is available, the command is wrapped with it so we record *per-command*
user/system CPU time and peak resident memory (``%M``, in KiB). These are the
measurements the runtime-intelligence models are trained on.
"""

from __future__ import annotations

import contextlib
import logging
import os
import resource
import shutil
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

GNU_TIME = "/usr/bin/time"
# elapsed wall seconds, user CPU seconds, system CPU seconds, max RSS KiB
_TIME_FORMAT = "SILICONAI_TIME %e %U %S %M"
_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "TERM", "TZ")
_KILL_GRACE_S = 10.0


@dataclass(frozen=True)
class ToolResult:
    argv: tuple[str, ...]
    exit_code: int | None  # None if the process never started
    wall_s: float  # measured by us (monotonic clock), always present
    timed_out: bool
    log_path: Path
    user_s: float | None = None  # from GNU time, if available
    sys_s: float | None = None
    peak_rss_kb: int | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def gnu_time_available() -> bool:
    if not os.path.exists(GNU_TIME):
        return False
    try:
        proc = subprocess.run(
            [GNU_TIME, "--version"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return "GNU" in (proc.stdout + proc.stderr)


def build_env(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Allowlisted environment for child processes."""
    env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
    for key, value in (extra or {}).items():
        if not key or "=" in key or "\0" in key or "\0" in value:
            raise ValueError(f"invalid environment entry: {key!r}")
        env[key] = value
    return env


def _validate_argv(argv: Sequence[str]) -> tuple[str, ...]:
    if isinstance(argv, str | bytes):
        raise TypeError("argv must be a sequence of arguments, not a shell string")
    out = tuple(argv)
    if not out:
        raise ValueError("argv must not be empty")
    for arg in out:
        if not isinstance(arg, str):
            raise TypeError(f"argv entries must be str, got {type(arg).__name__}")
        if "\0" in arg:
            raise ValueError("argv entries must not contain NUL bytes")
    return out


def parse_time_stats(text: str) -> tuple[float, float, float, int] | None:
    """Parse the SILICONAI_TIME line written by GNU time. Returns None if absent."""
    for line in reversed(text.splitlines()):
        if line.startswith("SILICONAI_TIME "):
            parts = line.split()
            if len(parts) != 5:
                return None
            try:
                return float(parts[1]), float(parts[2]), float(parts[3]), int(parts[4])
            except ValueError:
                return None
    return None


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=_KILL_GRACE_S)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()


def run_tool(
    argv: Sequence[str],
    *,
    cwd: Path,
    log_path: Path,
    timeout_s: float,
    env: Mapping[str, str] | None = None,
    measure: bool = True,
    address_space_limit_mb: int | None = None,
) -> ToolResult:
    """Run one tool command safely and return timing/memory measurements."""
    cmd = _validate_argv(argv)
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    cwd = Path(cwd)
    if not cwd.is_dir():
        raise FileNotFoundError(f"working directory does not exist: {cwd}")
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    stats_path = log_path.with_suffix(log_path.suffix + ".time")
    use_time = measure and gnu_time_available()
    full_cmd = (GNU_TIME, "-f", _TIME_FORMAT, "-o", str(stats_path), *cmd) if use_time else cmd
    if measure and not use_time:
        log.warning("GNU time not found at %s; peak memory will not be recorded", GNU_TIME)

    def _limits() -> None:  # runs in the child between fork and exec
        if address_space_limit_mb is not None:
            limit = address_space_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (limit, limit))

    log.debug("run_tool: %s (cwd=%s, timeout=%ss)", cmd, cwd, timeout_s)
    start = time.monotonic()
    timed_out = False
    with open(log_path, "wb") as log_file:
        try:
            proc = subprocess.Popen(
                full_cmd,
                cwd=cwd,
                env=build_env(env),
                stdin=subprocess.DEVNULL,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # own process group -> killpg on timeout
                preexec_fn=_limits if address_space_limit_mb is not None else None,  # noqa: PLW1509
            )
        except FileNotFoundError:
            log_file.write(f"siliconai: executable not found: {cmd[0]}\n".encode())
            return ToolResult(cmd, None, 0.0, False, log_path)
        try:
            exit_code: int | None = proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_group(proc)
            exit_code = proc.returncode
    wall_s = time.monotonic() - start

    user_s = sys_s = None
    peak_kb = None
    if use_time and stats_path.exists():
        parsed = parse_time_stats(stats_path.read_text(errors="replace"))
        if parsed is not None:
            _, user_s, sys_s, peak_kb = parsed
        stats_path.unlink(missing_ok=True)

    return ToolResult(cmd, exit_code, wall_s, timed_out, log_path, user_s, sys_s, peak_kb)


def which(tool: str) -> str | None:
    return shutil.which(tool)
