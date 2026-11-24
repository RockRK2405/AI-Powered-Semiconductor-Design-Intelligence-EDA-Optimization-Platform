"""Sweep specification (YAML) and deterministic planning of runs.

A spec lists designs and a discrete parameter space. Planning is a pure function of the spec
and of which designs fix their floorplan, so re-planning in a later chunk reproduces exactly
the same run ids (that is what makes chunked execution resumable).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from siliconai.data.schemas import stable_hash
from siliconai.eda.collect import make_run_id, orfs_design_id
from siliconai.eda.orfs import ALLOWED_OVERRIDES, DESIGN_CONFIG_RE, VALUE_RE
from siliconai.rtlgen.generators import generate
from siliconai.rtlgen.orfs_design import design_config_path
from siliconai.sweep.preflight import FLOORPLAN_SIZING_OVERRIDES

_MAX_SPEC_BYTES = 1024 * 1024
_ID = r"^[A-Za-z0-9_\-]{1,64}$"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class GenerateSpec(_Strict):
    """A design produced by ``siliconai.rtlgen`` instead of a bundled ORFS design."""

    family: str = Field(pattern=r"^[a-z0-9_]{1,32}$")
    params: dict[str, int]
    platform: str = Field(default="nangate45", pattern=_ID)


class DesignSpec(_Strict):
    config: str
    generate: GenerateSpec | None = None
    # RTL lineage: the same RTL on any platform belongs to the same group (leakage-safe splits).
    group: str = Field(pattern=_ID)
    n_configs: int = Field(default=1, ge=1, le=500, description="including the default config")
    expected_s: float | None = Field(default=None, gt=0, description="runtime guess if unmeasured")
    default_repeats: int | None = Field(
        default=None, ge=1, le=10, description="overrides the spec-level default_repeats"
    )

    @model_validator(mode="before")
    @classmethod
    def _derive_generated(cls, data: object) -> object:
        """For ``generate:`` entries, derive ``config`` (and default ``group``) from the
        generator, so a generated design is addressed exactly like a bundled one."""
        if isinstance(data, dict) and data.get("generate") is not None:
            gen = GenerateSpec.model_validate(data["generate"])
            design = generate(gen.family, gen.params)  # validates family/params
            data = dict(data)
            expected = design_config_path(gen.platform, design.name)
            if data.setdefault("config", expected) != expected:
                raise ValueError(f"config of a generated design must be {expected}")
            data.setdefault("group", f"gen_{gen.family}")
        return data

    @field_validator("config")
    @classmethod
    def _config_ok(cls, value: str) -> str:
        if not DESIGN_CONFIG_RE.match(value):
            raise ValueError(f"design config not allowed: {value!r}")
        return value

    @property
    def design_id(self) -> str:
        return orfs_design_id(self.config)

    @property
    def platform(self) -> str:
        return self.config.split("/")[2]


class SweepSpec(_Strict):
    name: str = Field(pattern=_ID)
    target: Literal["synth", "floorplan", "place", "cts", "route", "finish"] = "finish"
    timeout_s: int = Field(ge=60, le=24 * 3600)
    seed: int = 0
    default_repeats: int = Field(default=1, ge=1, le=10, description="repeats of default config")
    space: dict[str, list[str]] = Field(default_factory=dict)
    designs: list[DesignSpec] = Field(min_length=1)

    @field_validator("space")
    @classmethod
    def _space_ok(cls, space: dict[str, list[str]]) -> dict[str, list[str]]:
        for key, values in space.items():
            if key not in ALLOWED_OVERRIDES:
                raise ValueError(f"override not allowed in space: {key!r}")
            if not values or len(set(values)) != len(values):
                raise ValueError(f"space[{key}] must be a non-empty list of distinct values")
            for v in values:
                if not VALUE_RE.match(str(v)):
                    raise ValueError(f"space value not allowed: {key}={v!r}")
        return space

    @model_validator(mode="after")
    def _unique_designs(self) -> SweepSpec:
        configs = [d.config for d in self.designs]
        if len(set(configs)) != len(configs):
            raise ValueError("each design config may appear only once")
        return self


def load_spec(path: Path) -> SweepSpec:
    raw = Path(path).read_bytes()
    if len(raw) > _MAX_SPEC_BYTES:
        raise ValueError("sweep spec too large")
    return SweepSpec.model_validate(yaml.safe_load(raw))


@dataclass(frozen=True)
class PlannedRun:
    design: DesignSpec
    overrides: dict[str, str] = field(hash=False)
    repeat_index: int
    run_id: str


def design_space(spec: SweepSpec, fixed_floorplan: bool) -> dict[str, list[str]]:
    """Parameter space for one design: floorplan-sizing knobs are dropped if it is fixed."""
    if not fixed_floorplan:
        return dict(spec.space)
    return {k: v for k, v in spec.space.items() if k not in FLOORPLAN_SIZING_OVERRIDES}


def sample_configs(space: dict[str, list[str]], n: int, seed_material: object) -> list[dict]:
    """``n`` distinct override dicts: the default ``{}`` first, then random grid points.

    Sampling is seeded from ``seed_material`` so it is reproducible across processes.
    """
    configs: list[dict[str, str]] = [{}]
    keys = sorted(space)
    total = math.prod(len(space[k]) for k in keys) if keys else 0
    want = min(n - 1, total)
    rng = random.Random(int(stable_hash(seed_material), 16))  # noqa: S311 (sampling, not crypto)
    seen: set[tuple[str, ...]] = set()
    attempts = 0
    while len(seen) < want and attempts < 1000 * max(want, 1):
        attempts += 1
        point = tuple(rng.choice(space[k]) for k in keys)
        if point not in seen:
            seen.add(point)
            configs.append(dict(zip(keys, point, strict=True)))
    return configs


def plan(spec: SweepSpec, fixed_floorplan: dict[str, bool]) -> list[PlannedRun]:
    """All runs of the sweep in a deterministic, seeded-shuffled order.

    The shuffle spreads every design over the whole collection period, so slow drift of the
    machine (time of day, noisy neighbours) does not line up with design identity.
    """
    runs: list[PlannedRun] = []
    for d in spec.designs:
        space = design_space(spec, fixed_floorplan.get(d.config, False))
        for overrides in sample_configs(space, d.n_configs, [spec.seed, d.config]):
            base = d.default_repeats if d.default_repeats is not None else spec.default_repeats
            repeats = base if not overrides else 1
            for rep in range(repeats):
                run_id = make_run_id(d.design_id, overrides, rep, spec.target)
                runs.append(PlannedRun(d, overrides, rep, run_id))
    random.Random(spec.seed).shuffle(runs)  # noqa: S311 (sampling, not crypto)
    return runs
