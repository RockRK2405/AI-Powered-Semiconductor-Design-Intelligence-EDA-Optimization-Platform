"""Host fingerprint recorded with every run.

Runtime labels are only comparable on the same hardware, so every run stores the machine
characteristics it ran on. Deliberately excludes hostname, user names and IP addresses.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _mem_total_gb() -> float:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                return round(int(line.split()[1]) / 1024 / 1024, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def host_fingerprint() -> dict[str, str | int | float]:
    return {
        "cpu_model": _cpu_model(),
        "logical_cpus": os.cpu_count() or 0,
        "mem_total_gb": _mem_total_gb(),
        "kernel": platform.release(),
        "machine": platform.machine(),
    }
