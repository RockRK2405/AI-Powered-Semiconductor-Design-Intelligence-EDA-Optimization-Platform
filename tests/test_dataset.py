"""Dataset build: inclusion rules, targets, and horizon leakage guarantees."""

from __future__ import annotations

import math

import pytest

from siliconai.data.dataset import (
    HORIZONS,
    PRE_RUN,
    STAGE_INDEX,
    build_table,
    column_stage,
    content_hash,
    feature_columns,
    target_stages,
)
from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord

STEPS = [
    ("1_synth", "synth", {"synth__design__instance__count": 500, "synth__note": "text"}),
    (
        "2_1_floorplan",
        "floorplan",
        {"floorplan__design__core__area": 1e4, "run__flow__platform": 1},
    ),
    ("3_3_place_gp", "place", {"globalplace__design__instance__count": 520}),
    ("4_1_cts", "cts", {"cts__clock__skew__setup": 0.01}),
    ("5_2_route", "route", {"detailedroute__route__wirelength": 9e4}),
    ("6_report", "finish", {"finish__timing__setup__ws": -0.1}),
    ("write_binary_libs", "other", {}),
]


def _registry(tmp_path, *, image="img@sha256:a", cpu="cpu-a", extra=()):
    reg = Registry(tmp_path / "r.sqlite")
    reg.upsert_design(
        DesignRecord(
            design_id="gcd_nangate45",
            name="gcd",
            platform="nangate45",
            origin="orfs",
            source="x",
            design_group="gcd",
        )
    )
    reg.upsert_design(
        DesignRecord(
            design_id="sai_alu_w8_nangate45",
            name="sai_alu_w8",
            platform="nangate45",
            origin="generated",
            source="x",
            design_group="gen_alu",
        )
    )
    specs = [
        ("r1", "gcd_nangate45", {}, "success"),
        ("r2", "gcd_nangate45", {"CORE_UTILIZATION": "40"}, "success"),
        ("r3", "sai_alu_w8_nangate45", {}, "success"),
        ("r4", "gcd_nangate45", {"CORE_UTILIZATION": "90"}, "failed"),
        *extra,
    ]
    for i, (rid, did, cfg, status) in enumerate(specs):
        run = RunRecord(
            run_id=rid,
            design_id=did,
            config=cfg,
            status=status,
            tool_image=image,
            host={"cpu_model": cpu},
            wall_s=1000.0,  # container wall >= sum of step times
        )
        steps = [
            StepRecord(
                run_id=rid,
                step=st,
                stage=sg,
                wall_s=1.0 + i + k,
                cpu_user_s=1.0,
                peak_rss_mb=100.0 * (k + 1),
                metrics=m,
            )
            for k, (st, sg, m) in enumerate(STEPS)
        ]
        reg.record_run(run, steps)
    return reg


def test_table_rows_targets_and_inclusion(tmp_path):
    with _registry(tmp_path) as reg:
        df = build_table(reg)
    assert list(df["meta__run_id"]) == ["r1", "r2", "r3"]  # failed run excluded
    r1 = df.iloc[0]
    assert r1["y__route__ln_wall"] == pytest.approx(math.log(1.0 + 0 + 4))
    assert r1["y__total__ln_wall"] == pytest.approx(math.log(sum(1.0 + k for k in range(6))))
    assert r1["y__route__ln_peak"] == pytest.approx(math.log(500.0))
    assert math.isnan(r1["cfg__CORE_UTILIZATION"]) and df.iloc[1]["cfg__CORE_UTILIZATION"] == 40
    assert list(df["origin__gen"]) == [0.0, 0.0, 1.0]
    # non-numeric and bookkeeping metrics are dropped; "other" stage ignored
    assert not any("synth__note" in c or "run__flow" in c for c in df.columns)
    assert not any(c.startswith("t__other") for c in df.columns)


def test_refuses_to_mix_hosts_or_images(tmp_path):
    with _registry(tmp_path) as reg:
        reg.record_run(
            RunRecord(
                run_id="x",
                design_id="gcd_nangate45",
                status="success",
                tool_image="img@sha256:b",
                host={"cpu_model": "cpu-a"},
            )
        )
        with pytest.raises(ValueError, match="mix"):
            build_table(reg)
        assert len(build_table(reg, tool_image="img@sha256:a")) == 3


@pytest.mark.parametrize("horizon", list(HORIZONS))
def test_no_feature_from_the_future(tmp_path, horizon):
    with _registry(tmp_path) as reg:
        df = build_table(reg)
    h = HORIZONS[horizon]
    feats = feature_columns(df, horizon)
    assert feats, "every horizon has at least the pre-run features"
    for col in feats:
        assert not col.startswith(("meta__", "y__"))
        assert column_stage(col) <= h
    for stage in target_stages(horizon):
        assert STAGE_INDEX[stage] > h
        # the measurement of a target stage is never an admissible feature
        assert f"t__{stage}__wall_s" not in feats


def test_pre_run_horizon_has_no_design_measurements(tmp_path):
    with _registry(tmp_path) as reg:
        df = build_table(reg)
    feats = feature_columns(df, "h0")
    assert all(column_stage(c) == PRE_RUN for c in feats)
    assert "m__1_synth__synth__design__instance__count" in feature_columns(df, "h_synth")


def test_content_hash_is_order_independent(tmp_path):
    with _registry(tmp_path) as reg:
        df = build_table(reg)
    assert content_hash(df) == content_hash(df.sample(frac=1.0, random_state=0))
    changed = df.copy()
    changed.loc[0, "y__route__ln_wall"] += 0.01
    assert content_hash(changed) != content_hash(df)


def test_build_refuses_runs_whose_steps_exceed_wall_time():
    from siliconai.data.dataset import check_step_times

    runs = [{"run_id": "ok", "wall_s": 100.0}, {"run_id": "stale", "wall_s": 29.0}]
    steps = {
        "ok": [{"wall_s": 60.0}, {"wall_s": 39.5}],
        "stale": [{"wall_s": 300.0}, {"wall_s": None}],
    }
    check_step_times(runs[:1], steps)
    with pytest.raises(ValueError, match="stale"):
        check_step_times(runs, steps)
