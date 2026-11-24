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
        "./designs/-x/gcd/config.mk",
        "./designs/nangate45/--help/config.mk",
        "./designs/nan gate/gcd/config.mk",
        "./designs/../gcd/config.mk",
    ],
)
def test_rejects_bad_design_config(cfg):
    with pytest.raises(ValueError):
        OrfsJob(design_config=cfg, variant="v")


@pytest.mark.parametrize(
    "cfg", ["./designs/ihp-sg13g2/gcd/config.mk", "./designs/asap7/aes-block/config.mk"]
)
def test_accepts_hyphenated_names(cfg):
    assert OrfsJob(design_config=cfg, variant="v").design_config == cfg


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


def test_log_dir_follows_design_nickname(tmp_path):
    job = OrfsJob(design_config="./designs/nangate45/picorv32/config.mk", variant="run_x")
    assert job.log_dir(tmp_path) == tmp_path / "logs/nangate45/picorv32/run_x"
    nick = tmp_path / "logs/nangate45/picorv32_top/run_x"
    nick.mkdir(parents=True)
    assert job.log_dir(tmp_path) == nick


def test_generated_design_mount_is_readonly_and_restricted(tmp_path):
    from siliconai.eda.orfs import build_docker_argv

    d = tmp_path / "sai_alu_w8"
    d.mkdir()
    (d / "config.mk").write_text("export DESIGN_NAME = sai_alu_w8\n")
    job = OrfsJob(design_config="./designs/nangate45/sai_alu_w8/config.mk", variant="v1")
    argv = build_docker_argv(job, work_dir=tmp_path, image="img", inner_timeout_s=60, design_dir=d)
    mount = argv[argv.index("--mount") + 1]
    assert mount.endswith(",readonly")
    assert "target=/OpenROAD-flow-scripts/flow/designs/nangate45/sai_alu_w8" in mount
    # a bundled design can never be shadowed by a mount
    bundled = OrfsJob(design_config="./designs/nangate45/gcd/config.mk", variant="v1")
    with pytest.raises(ValueError, match="sai_"):
        build_docker_argv(bundled, work_dir=tmp_path, image="img", inner_timeout_s=60, design_dir=d)


@pytest.mark.parametrize("dirname", ["has,comma", "has space", "no_config"])
def test_generated_design_mount_rejects_unsafe_dirs(tmp_path, dirname):
    from siliconai.eda.orfs import design_mount_args

    d = tmp_path / dirname
    d.mkdir()
    if dirname != "no_config":
        (d / "config.mk").write_text("x")
    job = OrfsJob(design_config="./designs/nangate45/sai_x/config.mk", variant="v1")
    with pytest.raises(ValueError):
        design_mount_args(job, d)
