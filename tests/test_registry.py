from pathlib import Path

import pytest
from pydantic import ValidationError

from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord, stable_hash
from siliconai.eda.collect import classify_status, make_run_id, steps_from_log_dir

FIXTURES = Path(__file__).parent / "fixtures" / "orfs_gcd_logs"


def _design():
    return DesignRecord(
        design_id="gcd_nangate45",
        name="gcd",
        platform="nangate45",
        origin="orfs",
        source="test",
        design_group="gcd",
    )


def _run(run_id="r1", status="success"):
    return RunRecord(
        run_id=run_id,
        design_id="gcd_nangate45",
        config={"CORE_UTILIZATION": "40"},
        status=status,
        exit_code=0,
        wall_s=12.5,
    )


def test_round_trip_and_summary():
    with Registry(":memory:") as reg:
        reg.upsert_design(_design())
        steps = [
            StepRecord(
                run_id="r1",
                step="3_1_a",
                stage="place",
                wall_s=1.0,
                cpu_user_s=1.0,
                cpu_sys_s=0.5,
                peak_rss_mb=100,
                metrics={"x": 1.0},
            ),
            StepRecord(
                run_id="r1",
                step="3_2_b",
                stage="place",
                wall_s=2.0,
                cpu_user_s=2.0,
                cpu_sys_s=0.0,
                peak_rss_mb=300,
            ),
            StepRecord(run_id="r1", step="5_1_c", stage="route", wall_s=4.0),
        ]
        reg.record_run(_run(), steps)
        assert [r["run_id"] for r in reg.runs()] == ["r1"]
        summary = {row["stage"]: row for row in reg.stage_summary()}
        assert summary["place"]["wall_s"] == pytest.approx(3.0)
        assert summary["place"]["cpu_s"] == pytest.approx(3.5)
        assert summary["place"]["peak_rss_mb"] == pytest.approx(300)
        # re-recording replaces steps rather than duplicating them
        reg.record_run(_run(), steps[:1])
        assert len(reg.steps("r1")) == 1


def test_step_must_match_run():
    with Registry(":memory:") as reg:
        reg.upsert_design(_design())
        with pytest.raises(ValueError):
            reg.record_run(_run(), [StepRecord(run_id="other", step="s", stage="place")])
        assert reg.runs() == []  # nothing half-written


def test_foreign_key_enforced():
    import sqlite3

    with Registry(":memory:") as reg, pytest.raises(sqlite3.IntegrityError):
        reg.record_run(_run())  # design not registered


def test_schema_validation():
    with pytest.raises(ValidationError):
        DesignRecord(
            design_id="bad id!", name="x", platform="p", origin="orfs", source="", design_group="g"
        )
    with pytest.raises(ValidationError):
        RunRecord(run_id="r", design_id="d", unexpected_field=1)
    with pytest.raises(ValidationError):
        StepRecord(run_id="r", step="s", stage="place", wall_s=-1)


def test_run_id_is_deterministic():
    a = make_run_id("gcd_nangate45", {"A": "1", "B": "2"}, 0)
    b = make_run_id("gcd_nangate45", {"B": "2", "A": "1"}, 0)
    assert a == b and a.endswith("_r0")
    assert make_run_id("g", {"A": "1"}, 1) != make_run_id("g", {"A": "1"}, 0)
    assert make_run_id("g", {}, 0, target="synth") != make_run_id("g", {}, 0)
    assert stable_hash({"x": 1}) == stable_hash({"x": 1})


@pytest.mark.parametrize(
    ("code", "timed_out", "expected"),
    [
        (0, False, "success"),
        (2, False, "failed"),
        (124, False, "timeout"),
        (None, True, "timeout"),
        (None, False, "failed"),
    ],
)
def test_classify_status(code, timed_out, expected):
    assert classify_status(code, timed_out) == expected


def test_steps_from_real_logs():
    steps = {s.step: s for s in steps_from_log_dir("r1", FIXTURES)}
    assert steps["3_3_place_gp"].wall_s == pytest.approx(1.05)
    assert steps["3_3_place_gp"].metrics["globalplace__design__nets"] == 726.0
    assert steps["5_2_route"].stage == "route"


def test_delete_run_cascades_to_steps(tmp_path):
    from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord

    with Registry(tmp_path / "r.sqlite") as reg:
        reg.upsert_design(
            DesignRecord(
                design_id="d", name="d", platform="p", origin="orfs", source="s", design_group="g"
            )
        )
        reg.record_run(
            RunRecord(run_id="r1", design_id="d", status="success"),
            [StepRecord(run_id="r1", step="1_synth", stage="synth", wall_s=1.0)],
        )
        assert reg.delete_run("r1") is True
        assert reg.runs() == [] and reg.all_steps() == []
        assert reg.delete_run("r1") is False
