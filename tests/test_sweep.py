"""Sweep: preflight, spec validation, deterministic planning and budgeted chunk execution.

No Docker needed: the config reader, executor and clock are injected fakes.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from siliconai.data.registry import Registry
from siliconai.data.schemas import RunRecord
from siliconai.eda.collect import classify_status, make_run_id
from siliconai.sweep.preflight import (
    assigned_variables,
    fixes_floorplan,
    incompatible_overrides,
)
from siliconai.sweep.runner import prune_artifacts, run_sweep
from siliconai.sweep.spec import SweepSpec, plan, sample_configs

AES_FIXED = """export DESIGN_NICKNAME = aes
export FLOORPLAN_DEF = $(DESIGN_HOME)/$(PLATFORM)/$(DESIGN_NICKNAME)/aes_ng45_fp.def
# export DIE_AREA = 0 0 10 10   (commented out: must not count)
export PLACE_DENSITY_LB_ADDON = 0.20
"""
GCD_FREE = "export DESIGN_NAME = gcd\nexport CORE_UTILIZATION ?= 55\nexport PLACE_DENSITY = 0.6\n"
CONFIGS = {
    "./designs/nangate45/aes/config.mk": AES_FIXED,
    "./designs/nangate45/gcd/config.mk": GCD_FREE,
}
SPACE = {
    "CORE_UTILIZATION": ["30", "40", "50"],
    "PLACE_DENSITY_LB_ADDON": ["0.1", "0.2"],
}


def make_spec(**kw) -> SweepSpec:
    base = dict(
        name="t",
        timeout_s=600,
        seed=7,
        default_repeats=2,
        space=SPACE,
        designs=[
            {"config": "./designs/nangate45/aes/config.mk", "group": "aes", "n_configs": 3},
            {"config": "./designs/nangate45/gcd/config.mk", "group": "gcd", "n_configs": 4},
        ],
    )
    base.update(kw)
    return SweepSpec.model_validate(base)


# ---------------------------------------------------------------- preflight
def test_preflight_detects_fixed_floorplan_and_ignores_comments():
    assert "FLOORPLAN_DEF" in assigned_variables(AES_FIXED)
    assert "DIE_AREA" not in assigned_variables(AES_FIXED)
    assert fixes_floorplan(AES_FIXED)
    assert not fixes_floorplan(GCD_FREE)


def test_preflight_flags_only_floorplan_sizing_overrides():
    over = {"CORE_UTILIZATION": "30", "PLACE_DENSITY_LB_ADDON": "0.1"}
    assert incompatible_overrides(AES_FIXED, over) == ["CORE_UTILIZATION"]
    assert incompatible_overrides(GCD_FREE, over) == []


# ---------------------------------------------------------------- spec + plan
@pytest.mark.parametrize(
    "patch",
    [
        {"space": {"CLOCK_PERIOD": ["1"]}},  # not allowlisted
        {"space": {"CORE_UTILIZATION": ["$(shell id)"]}},  # make injection
        {"space": {"CORE_UTILIZATION": ["30", "30"]}},  # duplicate values
        {"designs": [{"config": "../../etc/passwd", "group": "x"}]},
        {"timeout_s": 5},
        {"unknown_field": 1},
    ],
)
def test_spec_rejects_bad_input(patch):
    with pytest.raises(ValidationError):
        make_spec(**patch)


def test_sample_configs_default_first_distinct_and_reproducible():
    a = sample_configs(SPACE, 4, ["seed", "x"])
    assert a[0] == {}
    assert len(a) == 4 and len({tuple(sorted(c.items())) for c in a}) == 4
    assert a == sample_configs(SPACE, 4, ["seed", "x"])
    # asking for more points than the grid holds returns the whole grid (+ default)
    assert len(sample_configs(SPACE, 100, 1)) == 1 + 6


def test_plan_respects_fixed_floorplan_and_repeats_default():
    runs = plan(make_spec(), {"./designs/nangate45/aes/config.mk": True})
    aes = [r for r in runs if r.design.group == "aes"]
    gcd = [r for r in runs if r.design.group == "gcd"]
    assert all("CORE_UTILIZATION" not in r.overrides for r in aes)
    assert any("CORE_UTILIZATION" in r.overrides for r in gcd)
    # aes: only 2 non-default grid points exist without CORE_UTILIZATION
    assert len(aes) == 2 + 2  # default x2 repeats + 2 sampled
    assert len(gcd) == 2 + 3
    assert len({r.run_id for r in runs}) == len(runs)
    assert [r.run_id for r in runs] == [
        r.run_id for r in plan(make_spec(), {"./designs/nangate45/aes/config.mk": True})
    ]


# ---------------------------------------------------------------- runner
class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t


def fake_executor(clock: FakeClock, cost: dict[str, float], status: str = "success"):
    calls = []

    def run(registry, design, job_config, overrides, **kw):
        calls.append((design.design_id, dict(overrides), kw))
        registry.upsert_design(design)
        wall = cost[design.design_id]
        clock.t += wall
        rec = RunRecord(
            run_id=make_run_id(design.design_id, overrides, kw["repeat_index"], kw["target"]),
            design_id=design.design_id,
            config=dict(overrides),
            repeat_index=kw["repeat_index"],
            status=status,
            exit_code=0,
            wall_s=wall,
        )
        registry.record_run(rec, [])
        return rec

    run.calls = calls
    return run


def test_sweep_is_budgeted_and_resumable(tmp_path):
    clock = FakeClock()
    cost = {"aes_nangate45": 100.0, "gcd_nangate45": 10.0}
    spec = make_spec(
        designs=[
            {
                "config": "./designs/nangate45/aes/config.mk",
                "group": "aes",
                "n_configs": 3,
                "expected_s": 100,
            },
            {
                "config": "./designs/nangate45/gcd/config.mk",
                "group": "gcd",
                "n_configs": 4,
                "expected_s": 10,
            },
        ]
    )
    with Registry(tmp_path / "r.sqlite") as reg:
        ex = fake_executor(clock, cost)
        kw = dict(
            work_dir=tmp_path,
            image="img",
            config_reader=CONFIGS.__getitem__,
            executor=ex,
            clock=clock,
            health_check=lambda: True,
            prune=False,
        )
        first = run_sweep(spec, reg, budget_s=250, **kw)
        assert first.planned == 9
        assert sum(first.executed.values()) == len(ex.calls) > 0
        assert clock.t <= 250  # never started a run that could not fit
        assert first.deferred_budget > 0
        # every executed run respects the preflight
        for design_id, over, _ in ex.calls:
            if design_id == "aes_nangate45":
                assert "CORE_UTILIZATION" not in over

        clock.t = 0.0
        second = run_sweep(spec, reg, budget_s=10_000, **kw)
        assert second.already_done == sum(first.executed.values())
        assert second.remaining == 0
        clock.t = 0.0
        third = run_sweep(spec, reg, budget_s=10_000, **kw)
        assert third.already_done == 9 and not third.executed


def test_sweep_stops_when_docker_is_down(tmp_path):
    with Registry(tmp_path / "r.sqlite") as reg:
        ex = fake_executor(FakeClock(), {"aes_nangate45": 1.0, "gcd_nangate45": 1.0})
        report = run_sweep(
            make_spec(),
            reg,
            work_dir=tmp_path,
            image="img",
            budget_s=10_000,
            config_reader=CONFIGS.__getitem__,
            executor=ex,
            health_check=lambda: False,
        )
    assert report.stopped_reason and not ex.calls


def test_sweep_marks_budget_capped_timeouts(tmp_path):
    clock = FakeClock()
    with Registry(tmp_path / "r.sqlite") as reg:
        ex = fake_executor(clock, {"aes_nangate45": 1.0, "gcd_nangate45": 1.0})
        spec = make_spec(
            timeout_s=3600,
            designs=[
                {"config": "./designs/nangate45/gcd/config.mk", "group": "gcd", "expected_s": 5}
            ],
        )
        run_sweep(
            spec,
            reg,
            work_dir=tmp_path,
            image="img",
            budget_s=600,
            config_reader=CONFIGS.__getitem__,
            executor=ex,
            clock=clock,
            health_check=lambda: True,
            prune=False,
        )
    kw = ex.calls[0][2]
    assert kw["timeout_s"] < 3600 and kw["budget_capped"] is True


def test_classify_status_aborted_cases():
    assert classify_status(124, False) == "timeout"
    assert classify_status(124, True, budget_capped=True) == "aborted"
    assert classify_status(125, False) == "aborted"  # docker daemon error
    assert classify_status(2, False) == "failed"


# ---------------------------------------------------------------- pruning
def test_prune_removes_only_bulky_dirs_of_that_run(tmp_path):
    for sub in ("results", "objects", "logs", "reports"):
        for variant in ("run_a", "run_b"):
            d = tmp_path / sub / "nangate45" / "gcd" / variant
            d.mkdir(parents=True)
            (d / "f").write_text("x")
    assert prune_artifacts(tmp_path, "nangate45", "run_a") == 2
    assert not (tmp_path / "results/nangate45/gcd/run_a").exists()
    assert not (tmp_path / "objects/nangate45/gcd/run_a").exists()
    assert (tmp_path / "logs/nangate45/gcd/run_a/f").exists()
    assert (tmp_path / "reports/nangate45/gcd/run_a/f").exists()
    assert (tmp_path / "results/nangate45/gcd/run_b/f").exists()


@pytest.mark.parametrize("variant", ["*", "../x", "a/b", ""])
def test_prune_rejects_unsafe_names(tmp_path, variant):
    with pytest.raises(ValueError):
        prune_artifacts(tmp_path, "nangate45", variant)


def test_prune_refuses_symlink_escape(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("x")
    work = tmp_path / "work"
    (work / "results/nangate45/gcd").mkdir(parents=True)
    (work / "results/nangate45/gcd/run_a").symlink_to(outside)
    with pytest.raises(ValueError):
        prune_artifacts(work, "nangate45", "run_a")
    assert (outside / "keep").exists()


# ---------------------------------------------------------------- generated designs
def test_generated_design_spec_derives_config_and_group():
    spec = make_spec(designs=[{"generate": {"family": "mult", "params": {"width": 8}}}])
    d = spec.designs[0]
    assert d.config == "./designs/nangate45/sai_mult_w8/config.mk"
    assert d.group == "gen_mult" and d.design_id == "sai_mult_w8_nangate45"


@pytest.mark.parametrize(
    "entry",
    [
        {"generate": {"family": "mult", "params": {"width": 999}}},
        {"generate": {"family": "rm -rf", "params": {}}},
        {
            "config": "./designs/nangate45/gcd/config.mk",
            "generate": {"family": "mult", "params": {"width": 8}},
        },
    ],
)
def test_generated_design_spec_rejects_bad_entries(entry):
    with pytest.raises((ValidationError, ValueError)):
        make_spec(designs=[entry])


def test_sweep_materializes_and_mounts_generated_designs(tmp_path):
    clock = FakeClock()
    spec = make_spec(
        designs=[
            {"generate": {"family": "alu", "params": {"width": 8}}, "n_configs": 2, "expected_s": 5}
        ]
    )
    with Registry(tmp_path / "r.sqlite") as reg:
        ex = fake_executor(clock, {"sai_alu_w8_nangate45": 5.0})
        report = run_sweep(
            spec,
            reg,
            work_dir=tmp_path,
            image="img",
            budget_s=1000,
            config_reader=lambda c: pytest.fail("must not read image"),
            executor=ex,
            clock=clock,
            health_check=lambda: True,
            prune=False,
            gen_root=tmp_path / "gen",
        )
        assert report.remaining == 0
        design_dir = ex.calls[0][2]["design_dir"]
        assert (design_dir / "rtl.v").is_file()
        assert design_dir == tmp_path / "gen" / "nangate45" / "sai_alu_w8"
        (row,) = reg.designs()
        assert row["origin"] == "generated" and row["design_group"] == "gen_alu"


def test_per_design_default_repeats_override():
    spec = make_spec(
        default_repeats=1,
        designs=[
            {
                "config": "./designs/nangate45/gcd/config.mk",
                "group": "gcd",
                "n_configs": 2,
                "default_repeats": 3,
            }
        ],
    )
    runs = plan(spec, {})
    assert sum(1 for r in runs if not r.overrides) == 3
    assert sum(1 for r in runs if r.overrides) == 1
