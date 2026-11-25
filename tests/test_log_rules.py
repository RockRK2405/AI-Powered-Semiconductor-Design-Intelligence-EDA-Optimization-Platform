from siliconai.log_intelligence.corpus import _skipped, plan, run_timeout
from siliconai.log_intelligence.faults import BaseDesign, build_faulted, generated_base
from siliconai.log_intelligence.logs import MAX_LINE_CHARS, Line, load_run_lines
from siliconai.log_intelligence.rules import (
    FAILURE_CLASSES,
    GOLD,
    error_line_evidence,
    has_gold,
    keyword_predict,
)


def L(*texts):
    return [Line("console", i + 1, t) for i, t in enumerate(texts)]


def test_keyword_priority_timeout_beats_earlier_errors():
    lines = L("[ERROR GRT-0232] Routing congestion too high.", "make[1]: *** [x] Terminated")
    assert keyword_predict(lines)[0] == "timeout"


def test_keyword_examples_from_dev_logs():
    cases = {
        "syntax_error": "gcd.v:753: ERROR: syntax error, unexpected TOK_END",
        "elaboration_error": "ERROR: Module `gcd_x' not found!",
        "missing_file": "make: *** No rule to make target 'a.sdc', needed by 'b'.  Stop.",
        "sdc_error": 'invalid command name "sai_set_bogus_constraint"',
        "floorplan_capacity": "[ERROR PDN-0185] Insufficient width (3.80 um) to add straps",
        "routing_resources": "[ERROR GRT-0232] Routing congestion too high.",
        "out_of_memory": "make[1]: *** [Makefile:629: do-5_2_route] Error 247",
    }
    for cls, text in cases.items():
        pred, hit = keyword_predict(L("ok", text, "make: *** [x] Error 2"))
        assert pred == cls and hit.text == text
        assert has_gold(cls, L(text))
    assert keyword_predict(L("all good"))[0] == "unknown"
    assert set(GOLD) == set(FAILURE_CLASSES)


def test_error_line_evidence_last_distinct():
    lines = L("error a", "fine", "Error b", "error a", "ERROR c", "error c")
    ev = [x.text for x in error_line_evidence(lines)]
    assert ev == ["error c", "ERROR c", "error a"]


def test_load_run_lines_orders_steps_then_console_and_caps(tmp_path):
    d = tmp_path / "logs"
    d.mkdir()
    (d / "5_1_grt.log").write_text("route\n")
    (d / "1_2_yosys.log").write_text("synth\n")
    (d / "2_1_floorplan.log").write_text("fp " + "x" * 5000 + "\n")
    (d / "notes.txt").write_text("ignored\n")
    con = tmp_path / "c.log"
    con.write_text("make: done\n")
    (d / "evil.log").symlink_to(con)
    lines = load_run_lines(con, d)
    assert [x.source for x in lines] == ["1_2_yosys", "2_1_floorplan", "5_1_grt", "console"]
    assert len(lines[1].text) == MAX_LINE_CHARS
    assert load_run_lines(None, tmp_path / "missing") == []


def test_plan_skips_and_timeouts():
    base = generated_base("alu", {"width": 8}, "nangate45", "gen_alu")
    base = BaseDesign(**{**base.__dict__, "ref_wall_s": 30.0, "ref_peak_mb": 500.0})
    p = plan([(base, ["syntax_error/*", "missing_file/include"])], seed=1)
    keys = {(x.fault_class, x.variant) for x in p}
    assert not any(c == "syntax_error" for c, _ in keys)
    assert ("missing_file", "include") not in keys and ("missing_file", "verilog") in keys
    assert p == plan([(base, ["syntax_error/*", "missing_file/include"])], seed=1)
    assert _skipped(["sdc_error/*"], "sdc_error", "bad_value")
    fd = build_faulted(base, "timeout", "t_50pct")
    assert run_timeout(fd, base, 1800) == 15
    fd = build_faulted(base, "none", "clean")
    assert run_timeout(fd, base, 1800) == 300 and run_timeout(fd, base, 200) == 200
