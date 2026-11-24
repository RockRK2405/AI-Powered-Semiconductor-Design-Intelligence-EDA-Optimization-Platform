"""Validated record types stored in the run registry.

Every record that enters the database passes through one of these pydantic models, so
malformed or hostile input (from logs, uploads or configs) is rejected at the boundary.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ID_PATTERN = r"^[A-Za-z0-9_\-]{1,64}$"

DesignOrigin = Literal["orfs", "generated", "external"]
RunStatus = Literal["pending", "running", "success", "failed", "timeout"]
Scalar = float | int | str


def stable_hash(obj: object) -> str:
    """Deterministic short hash of a JSON-serialisable object (sorted keys)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DesignRecord(_Strict):
    design_id: str = Field(pattern=_ID_PATTERN)
    name: str = Field(min_length=1, max_length=128)
    platform: str = Field(pattern=_ID_PATTERN)
    origin: DesignOrigin
    source: str = Field(max_length=512, description="Where the RTL/config comes from")
    design_group: str = Field(
        pattern=_ID_PATTERN,
        description="Designs sharing RTL lineage share a group; used for leakage-safe splits",
    )
    license: str | None = Field(default=None, max_length=128)


class RunRecord(_Strict):
    run_id: str = Field(pattern=_ID_PATTERN)
    design_id: str = Field(pattern=_ID_PATTERN)
    config: dict[str, Scalar] = Field(default_factory=dict)
    tool_image: str | None = Field(default=None, max_length=256)
    host: dict[str, Scalar] = Field(default_factory=dict)
    concurrency: int = Field(default=1, ge=1, le=256)
    repeat_index: int = Field(default=0, ge=0)
    injected_fault: str | None = Field(default=None, max_length=64)
    status: RunStatus = "pending"
    exit_code: int | None = None
    wall_s: float | None = Field(default=None, ge=0)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def config_hash(self) -> str:
        return stable_hash(self.config)


class StepRecord(_Strict):
    run_id: str = Field(pattern=_ID_PATTERN)
    step: str = Field(pattern=r"^[A-Za-z0-9_]{1,64}$")
    stage: str = Field(pattern=r"^[a-z_]{1,32}$")
    wall_s: float | None = Field(default=None, ge=0)
    cpu_user_s: float | None = Field(default=None, ge=0)
    cpu_sys_s: float | None = Field(default=None, ge=0)
    peak_rss_mb: float | None = Field(default=None, ge=0)
    metrics: dict[str, Scalar] = Field(default_factory=dict)
    log_path: str | None = Field(default=None, max_length=1024)

    @field_validator("metrics")
    @classmethod
    def _bounded(cls, value: dict[str, Scalar]) -> dict[str, Scalar]:
        if len(value) > 2000:
            raise ValueError("too many metrics in one step")
        return value
