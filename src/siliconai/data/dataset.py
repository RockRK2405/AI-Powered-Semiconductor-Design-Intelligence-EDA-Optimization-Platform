"""Build the D1 analysis table from the run registry (TODO P2-03).

One row per run. Column families (the prefix encodes the stage at which a value exists):

  meta__*        identifiers and bookkeeping; never features
  plat__<p>      platform one-hot                    (stage -1: known before the run)
  cfg__<KNOB>    flow-config override, NaN = default (stage -1)
  origin__gen    1 if generated RTL                  (stage -1)
  m__<step>__<k> numeric METRICS2.1 value of a step  (stage of that step)
  t__<stage>__*  measured wall/cpu/peak of a stage   (that stage)
  y__<stage>__*  regression targets                  (never features)

Leakage rule (docs/experiments.md §1): at horizon h a model may use only feature columns
whose stage <= h. :func:`feature_columns` enforces that, and tests check it.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict

import numpy as np
import pandas as pd

from siliconai.data.registry import Registry
from siliconai.eda.orfs import ALLOWED_OVERRIDES
from siliconai.eda.orfs_parse import stage_of

STAGES = ("synth", "floorplan", "place", "cts", "route", "finish")
STAGE_INDEX = {s: i for i, s in enumerate(STAGES)}
PRE_RUN = -1
HORIZONS = {"h0": PRE_RUN, **{f"h_{s}": i for i, s in enumerate(STAGES[:-1])}}
# Metric keys that are bookkeeping, not design properties.
_DROP_METRIC_PREFIXES = ("run__flow__",)


def _is_number(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)


def _cfg_value(v: object) -> float:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")


def build_table(
    registry: Registry,
    *,
    tool_image: str | None = None,
    statuses: tuple[str, ...] = ("success",),
    concurrency: int = 1,
) -> pd.DataFrame:
    """Analysis table for runs matching the inclusion rules (docs/experiments.md §0).

    Runs from more than one tool image or host CPU model are refused: they must not be mixed.
    """
    designs = {d["design_id"]: dict(d) for d in registry.designs()}
    runs = [
        dict(r)
        for r in registry.runs()
        if r["status"] in statuses
        and r["concurrency"] == concurrency
        and (tool_image is None or r["tool_image"] == tool_image)
    ]
    images = {r["tool_image"] for r in runs}
    cpus = {json.loads(r["host_json"]).get("cpu_model") for r in runs}
    if len(images) > 1 or len(cpus) > 1:
        raise ValueError(f"refusing to mix tool images {images} or hosts {cpus}")

    steps_by_run: dict[str, list[dict]] = defaultdict(list)
    for s in registry.all_steps():
        steps_by_run[s["run_id"]].append(dict(s))

    rows = []
    for run in runs:
        design = designs[run["design_id"]]
        row: dict[str, object] = {
            "meta__run_id": run["run_id"],
            "meta__design_id": run["design_id"],
            "meta__design_group": design["design_group"],
            "meta__platform": design["platform"],
            "meta__origin": design["origin"],
            "meta__config_hash": run["config_hash"],
            "meta__repeat_index": run["repeat_index"],
            "meta__status": run["status"],
            f"plat__{design['platform']}": 1.0,
            "origin__gen": 1.0 if design["origin"] == "generated" else 0.0,
        }
        for key, value in json.loads(run["config_json"]).items():
            row[f"cfg__{key}"] = _cfg_value(value)
        wall: dict[str, float] = defaultdict(float)
        cpu: dict[str, float] = defaultdict(float)
        peak: dict[str, float] = defaultdict(float)
        for step in sorted(steps_by_run[run["run_id"]], key=lambda s: s["step"]):
            stage = step["stage"]
            if stage not in STAGE_INDEX:
                continue
            if step["wall_s"] is not None:
                wall[stage] += step["wall_s"]
                cpu[stage] += (step["cpu_user_s"] or 0.0) + (step["cpu_sys_s"] or 0.0)
                peak[stage] = max(peak[stage], step["peak_rss_mb"] or 0.0)
            for key, value in json.loads(step["metrics_json"]).items():
                if _is_number(value) and not key.startswith(_DROP_METRIC_PREFIXES):
                    row[f"m__{step['step']}__{key}"] = float(value)
        for stage in STAGES:
            if stage in wall:
                row[f"t__{stage}__wall_s"] = wall[stage]
                row[f"t__{stage}__cpu_s"] = cpu[stage]
                row[f"t__{stage}__peak_mb"] = peak[stage]
                row[f"y__{stage}__ln_wall"] = math.log(max(wall[stage], 1e-3))
                row[f"y__{stage}__ln_peak"] = math.log(max(peak[stage], 1.0))
        if wall:
            row["y__total__ln_wall"] = math.log(max(sum(wall.values()), 1e-3))
        rows.append(row)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    plat_cols = [c for c in df.columns if c.startswith("plat__")]
    df[plat_cols] = df[plat_cols].fillna(0.0)
    missing = [f"cfg__{k}" for k in sorted(ALLOWED_OVERRIDES) if f"cfg__{k}" not in df.columns]
    if missing:  # stable schema: every allowlisted knob has a column (NaN = ORFS default)
        df = pd.concat([df, pd.DataFrame(np.nan, index=df.index, columns=missing)], axis=1)
    return df.sort_values("meta__run_id").reset_index(drop=True)


def column_stage(column: str) -> int | None:
    """Stage index at which a column's value exists; None for non-features (meta/targets)."""
    if column.startswith(("meta__", "y__")):
        return None
    if column.startswith(("plat__", "cfg__", "origin__")):
        return PRE_RUN
    if column.startswith("t__"):
        return STAGE_INDEX[column.split("__")[1]]
    if column.startswith("m__"):
        return STAGE_INDEX[stage_of(column.split("__")[1])]
    raise ValueError(f"unknown column family: {column}")


def feature_columns(df: pd.DataFrame, horizon: str) -> list[str]:
    """Feature columns admissible at ``horizon`` (stage <= h), excluding all-NaN columns."""
    h = HORIZONS[horizon]
    cols = []
    for c in df.columns:
        st = column_stage(c)
        if st is not None and st <= h and df[c].notna().any():
            cols.append(c)
    return sorted(cols)


def target_stages(horizon: str) -> list[str]:
    """Stages a model at ``horizon`` may predict (strictly after the horizon)."""
    h = HORIZONS[horizon]
    return [s for s in STAGES if STAGE_INDEX[s] > h]


def content_hash(df: pd.DataFrame) -> str:
    """Order-independent content hash of the table (freezes a dataset version)."""
    canon = df.sort_values("meta__run_id")[sorted(df.columns)]
    blob = canon.to_csv(index=False, float_format="%.10g").encode()
    return hashlib.sha256(blob).hexdigest()[:16]
