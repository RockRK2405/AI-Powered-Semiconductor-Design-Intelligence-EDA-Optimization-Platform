"""Runtime configuration, read from environment variables (see .env.example).

Configuration is deliberately small and explicit: every setting has a default that works
for a local checkout, and every path is derived from a single root (SILICONAI_HOME).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


@dataclass(frozen=True)
class Settings:
    home: Path
    orfs_image: str
    tool_timeout_s: int
    log_level: str

    @property
    def db_path(self) -> Path:
        return self.home / "registry.sqlite"

    @property
    def runs_dir(self) -> Path:
        return self.home / "runs"

    @classmethod
    def from_env(cls) -> Settings:
        home = Path(os.environ.get("SILICONAI_HOME", "./workspace")).expanduser().resolve()
        level = os.environ.get("SILICONAI_LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError(f"SILICONAI_LOG_LEVEL invalid: {level!r}")
        return cls(
            home=home,
            orfs_image=os.environ.get("SILICONAI_ORFS_IMAGE", "openroad/orfs:latest"),
            tool_timeout_s=_env_int("SILICONAI_TOOL_TIMEOUT_S", 7200),
            log_level=level,
        )

    def ensure_dirs(self) -> None:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
