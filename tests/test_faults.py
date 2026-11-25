import pytest

from siliconai.eda.orfs import DESIGN_CONFIG_RE
from siliconai.log_intelligence.faults import (
    FAULTS,
    MASKED_FAULTS,
    BaseDesign,
    build_faulted,
    drop_end,
    drop_semicolon,
    generated_base,
    misspell_endmodule,
    stray_token,
    write_faulted,
)

TOY_V = """module top (input clk, input a, output reg q);
  wire b;
  assign b = ~a;
  always @(posedge clk) begin
    q <= b;
  end
endmodule
"""
TOY_SDC = "set clk_period 1.5\ncreate_clock -name c -period $clk_period [get_ports clk]\n"


def toy_bundled(fixed: bool = False) -> BaseDesign:
    return BaseDesign(
        name="top",
        platform="nangate45",
        group="toy",
        origin="orfs",
        config_text="export DESIGN_NAME = top\nexport PLATFORM = nangate45\n",
        sources=("src/toy/a.v", "src/toy/top.v"),
        top_file="src/toy/top.v",
        sdc="nangate45/toy/constraint.sdc",
        files={"src/toy/top.v": TOY_V, "nangate45/toy/constraint.sdc": TOY_SDC},
        fixed_floorplan=fixed,
        ref_wall_s=40.0,
        ref_peak_mb=560.0,
    )


def test_text_transforms():
    assert "q <= b\n" in drop_semicolon(TOY_V)
    assert drop_semicolon(TOY_V).count(";") == TOY_V.count(";") - 1
    assert misspell_endmodule(TOY_V).rstrip().endswith("endmodul")
    assert "@@ sai_stray_token @@" in stray_token(TOY_V, "top")
    out = drop_end(TOY_V)
    assert out.count("\n  end\n") == 0 and "begin" in out


def test_transforms_refuse_when_nothing_to_change():
    assert drop_end("module m;\nendmodule\n") == "module m;\n  end\nendmodule\n"
    assert drop_semicolon("module m (input a);\n  foo u ();\nendmodule") == (
        "module m (input a);\n  foo u ()\nendmodule"
    )
    with pytest.raises(ValueError):
        drop_semicolon("module m\nendmodule")
    with pytest.raises(ValueError):
        stray_token(TOY_V, "other")


@pytest.mark.parametrize("key", list(FAULTS))
def test_every_fault_builds_on_bundled_and_generated(key, tmp_path):
    gen = generated_base("alu", {"width": 8}, "sky130hd", "gen_alu")
    gen = BaseDesign(**{**gen.__dict__, "ref_wall_s": 30.0, "ref_peak_mb": 400.0})
    for base in (toy_bundled(), gen):
        fd = build_faulted(base, *key)
        assert DESIGN_CONFIG_RE.match(fd.design_config)
        cfg = fd.files["config.mk"]
        assert cfg.startswith(base.config_text.rstrip("\n"))  # base config kept verbatim
        assert f"fault injection: {key[0]}/{key[1]}" in cfg
        d = write_faulted(fd, tmp_path)
        assert (d / "config.mk").read_text() == cfg


def test_bundled_sources_referenced_in_place_unless_mutated():
    clean = build_faulted(toy_bundled(), "none", "clean").files["config.mk"]
    assert "$(DESIGN_HOME)/src/toy/a.v $(DESIGN_HOME)/src/toy/top.v" in clean
    assert "SDC_FILE = $(DESIGN_HOME)/nangate45/toy/constraint.sdc" in clean
    fd = build_faulted(toy_bundled(), "syntax_error", "missing_semicolon")
    cfg = fd.files["config.mk"]
    assert f"$(DESIGN_HOME)/src/toy/a.v $(DESIGN_HOME)/nangate45/{fd.dir_name}/top.v" in cfg
    assert fd.files["top.v"] != TOY_V and "a.v" not in fd.files


def test_sdc_and_runtime_faults():
    inj = MASKED_FAULTS[("timing_infeasible", "impossible_clock")](toy_bundled())
    assert "set clk_period 0.001" in inj.sdc
    assert build_faulted(toy_bundled(), "out_of_memory", "mem_55pct").memory_mb == 308
    assert build_faulted(toy_bundled(), "out_of_memory", "mem_30pct").memory_mb == 168
    assert build_faulted(toy_bundled(), "timeout", "t_25pct").timeout_s == 10
    small = BaseDesign(**{**toy_bundled().__dict__, "ref_wall_s": 8.0, "ref_peak_mb": 200.0})
    assert build_faulted(small, "timeout", "t_25pct").timeout_s == 5  # floor
    assert build_faulted(small, "out_of_memory", "mem_30pct").memory_mb == 128  # floor
    nores = BaseDesign(**{**toy_bundled().__dict__, "ref_wall_s": None, "ref_peak_mb": None})
    with pytest.raises(ValueError):
        build_faulted(nores, "timeout", "t_50pct")


def test_fixed_floorplan_uses_outline_not_utilization():
    cfg = build_faulted(toy_bundled(fixed=True), "floorplan_capacity", "core_util_high")
    assert "DIE_AREA" in cfg.files["config.mk"]
    assert "CORE_UTILIZATION" not in cfg.files["config.mk"]


def test_dir_names_are_deterministic_and_distinct():
    names = {build_faulted(toy_bundled(), *k).dir_name for k in FAULTS}
    assert len(names) == len(FAULTS)
    a = build_faulted(toy_bundled(), "none", "clean").dir_name
    assert a == build_faulted(toy_bundled(), "none", "clean").dir_name
    assert a.startswith("sai_fi_")


def test_base_rejects_path_traversal_and_bad_names():
    good = toy_bundled()
    with pytest.raises(ValueError):
        BaseDesign(**{**good.__dict__, "sources": ("../etc/passwd",), "top_file": "../etc/passwd"})
    with pytest.raises(ValueError):
        BaseDesign(**{**good.__dict__, "name": "top; rm -rf /"})
    with pytest.raises(ValueError):
        BaseDesign(**{**good.__dict__, "platform": "tsmc5"})


def test_unknown_fault_rejected():
    with pytest.raises(KeyError):
        build_faulted(toy_bundled(), "syntax_error", "nope")
