"""End-to-end test with the real ORFS Docker image (skipped when unavailable).

Runs gcd/nangate45 up to synthesis only (~10 s) through the full SiliconAI path:
validated job -> docker -> ORFS -> log/metric parsing -> registry.
"""

import shutil
import subprocess

import pytest

from siliconai.config import Settings
from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord
from siliconai.eda.collect import execute_and_record
from siliconai.eda.orfs import OrfsJob, run_orfs
from siliconai.eda.orfs_parse import collect_steps

IMAGE = Settings.from_env().orfs_image


def _image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    proc = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    return proc.returncode == 0


pytestmark = [
    pytest.mark.eda,
    pytest.mark.skipif(not _image_available(), reason="ORFS docker image not available"),
]


def test_gcd_synth_end_to_end(tmp_path):
    job = OrfsJob(
        design_config="./designs/nangate45/gcd/config.mk", variant="itest_synth", target="synth"
    )
    result = run_orfs(job, work_dir=tmp_path, image=IMAGE, timeout_s=600)
    assert result.ok, (tmp_path / "console" / "itest_synth.log").read_text()[-2000:]
    steps = {s.step: s for s in collect_steps(job.log_dir(tmp_path))}
    assert "1_2_yosys" in steps and steps["1_2_yosys"].timing is not None
    assert steps["1_2_yosys"].timing.peak_rss_mb > 1
    synth_metrics = steps["1_synth"].metrics
    assert synth_metrics["synth__design__instance__count__stdcell"] > 100


def test_execute_and_record_synth(tmp_path):
    design = DesignRecord(
        design_id="gcd_nangate45",
        name="gcd",
        platform="nangate45",
        origin="orfs",
        source="ORFS",
        design_group="gcd",
    )
    with Registry(tmp_path / "r.sqlite") as reg:
        run = execute_and_record(
            reg,
            design,
            "./designs/nangate45/gcd/config.mk",
            {"CORE_UTILIZATION": "40"},
            work_dir=tmp_path / "runs",
            image=IMAGE,
            timeout_s=600,
            target="synth",
        )
        assert run.status == "success"
        assert run.tool_image and "sha256" in run.tool_image
        stages = {row["stage"] for row in reg.stage_summary()}
        # "other" = write_binary_libs (ORFS liberty cache step), real time but not a flow stage
        assert "synth" in stages and stages <= {"synth", "other"}
        # second call is skipped (resumable sweeps)
        again = execute_and_record(
            reg,
            design,
            "./designs/nangate45/gcd/config.mk",
            {"CORE_UTILIZATION": "40"},
            work_dir=tmp_path / "runs",
            image=IMAGE,
            timeout_s=600,
            target="synth",
        )
        assert again.run_id == run.run_id and len(reg.runs()) == 1
