"""JSONL export/import round trip and tamper detection."""

from __future__ import annotations

import json

import pytest

from siliconai.data.exchange import export_jsonl, import_jsonl
from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord


def _fill(reg: Registry) -> None:
    reg.upsert_design(
        DesignRecord(
            design_id="gcd_nangate45",
            name="gcd",
            platform="nangate45",
            origin="orfs",
            source="ORFS",
            design_group="gcd",
        )
    )
    for rep in range(2):
        run = RunRecord(
            run_id=f"gcd_r{rep}",
            design_id="gcd_nangate45",
            config={"CORE_UTILIZATION": "40"},
            host={"cpus": 4},
            repeat_index=rep,
            status="success",
            exit_code=0,
            wall_s=33.0 + rep,
        )
        steps = [
            StepRecord(
                run_id=run.run_id,
                step="5_2_route",
                stage="route",
                wall_s=18.0,
                peak_rss_mb=557.0,
                metrics={"route__wirelength": 1234},
            )
        ]
        reg.record_run(run, steps)


def test_round_trip_is_lossless_and_deterministic(tmp_path):
    with Registry(tmp_path / "a.sqlite") as a:
        _fill(a)
        counts = export_jsonl(a, tmp_path / "out")
        assert counts == {"designs": 1, "runs": 2, "steps": 2}
        before = [dict(r) for r in a.stage_summary()]
    with Registry(tmp_path / "b.sqlite") as b:
        import_jsonl(b, tmp_path / "out")
        assert [dict(r) for r in b.stage_summary()] == before
        export_jsonl(b, tmp_path / "out2")
    for name in ("designs.jsonl", "runs.jsonl", "steps.jsonl"):
        assert (tmp_path / "out" / name).read_bytes() == (tmp_path / "out2" / name).read_bytes()


def test_import_detects_tampered_config(tmp_path):
    with Registry(tmp_path / "a.sqlite") as a:
        _fill(a)
        export_jsonl(a, tmp_path / "out")
    path = tmp_path / "out" / "runs.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[0]["config"]["CORE_UTILIZATION"] = "90"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    with Registry(tmp_path / "b.sqlite") as b, pytest.raises(ValueError, match="config_hash"):
        import_jsonl(b, tmp_path / "out")


def test_import_rejects_unknown_fields(tmp_path):
    with Registry(tmp_path / "a.sqlite") as a:
        _fill(a)
        export_jsonl(a, tmp_path / "out")
    path = tmp_path / "out" / "designs.jsonl"
    row = json.loads(path.read_text())
    row["evil"] = "x"
    path.write_text(json.dumps(row) + "\n")
    with Registry(tmp_path / "b.sqlite") as b, pytest.raises(ValueError):
        import_jsonl(b, tmp_path / "out")
