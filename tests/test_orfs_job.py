from pathlib import Path

import pytest

from siliconai.eda.orfs import OrfsJob, build_docker_argv

CFG = "./designs/nangate45/gcd/config.mk"


def test_job_properties():
    job = OrfsJob(design_config=CFG, variant="run_1", overrides={"CORE_UTILIZATION": "40"})
    assert job.platform == "nangate45" and job.design == "gcd"
    assert job.log_dir(Path("/w")) == Path("/w/logs/nangate45/gcd/run_1")


@pytest.mark.parametrize(
    "cfg",
    [
        "../../etc/passwd",
        "./designs/nangate45/gcd/config.mk; rm -rf /",
        "/abs/designs/x/y/config.mk",
        "./designs/a/b/c/config.mk",
    ],
)
def test_rejects_bad_design_config(cfg):
    with pytest.raises(ValueError):
        OrfsJob(design_config=cfg, variant="v")


@pytest.mark.parametrize(
    "overrides",
    [
        {"SHELL": "/bin/sh"},
        {"CORE_UTILIZATION": "40 SHELL=x"},
        {"CORE_UTILIZATION": "$(shell id)"},
        {"CORE_UTILIZATION": ""},
    ],
)
def test_rejects_bad_overrides(overrides):
    with pytest.raises(ValueError):
        OrfsJob(design_config=CFG, variant="v", overrides=overrides)


def test_rejects_bad_variant_and_target():
    with pytest.raises(ValueError):
        OrfsJob(design_config=CFG, variant="a/b")
    with pytest.raises(ValueError):
        OrfsJob(design_config=CFG, variant="v", target="clean_all")


def test_docker_argv_shape(tmp_path):
    job = OrfsJob(
        design_config=CFG,
        variant="v1",
        overrides={"PLACE_DENSITY": "0.6", "CORE_UTILIZATION": "40"},
    )
    argv = build_docker_argv(
        job, work_dir=tmp_path, image="img@sha256:abc", inner_timeout_s=99, cpuset="0-1"
    )
    assert argv[:2] == ["docker", "run"]
    assert "--network" in argv and argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--cpuset-cpus") + 1] == "0-1"
    i = argv.index("img@sha256:abc")
    assert argv[i + 1 : i + 5] == ["timeout", "--signal=TERM", "--kill-after=30", "99"]
    assert "FLOW_VARIANT=v1" in argv and "WORK_HOME=/work" in argv
    # overrides sorted and passed as separate argv entries; target last
    assert argv[-3:] == ["CORE_UTILIZATION=40", "PLACE_DENSITY=0.6", "finish"]
    assert not any(a in ("bash", "sh", "-c") for a in argv)


def test_docker_argv_rejects_bad_cpuset(tmp_path):
    job = OrfsJob(design_config=CFG, variant="v1")
    with pytest.raises(ValueError):
        build_docker_argv(job, work_dir=tmp_path, image="i", inner_timeout_s=1, cpuset="0;ls")
