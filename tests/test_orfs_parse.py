from pathlib import Path

import pytest

from siliconai.eda.orfs_parse import (
    collect_steps,
    parse_elapsed_lines,
    parse_step_metrics,
    stage_of,
)

FIXTURES = Path(__file__).parent / "fixtures" / "orfs_gcd_logs"


def test_parse_single_elapsed_line():
    line = (
        "Elapsed time: 0:01.05[h:]min:sec. CPU time: user 0.96 sys 0.35 (124%). "
        "Peak memory: 265592KB."
    )
    t = parse_elapsed_lines(line)
    assert t is not None
    assert t.wall_s == pytest.approx(1.05)
    assert t.user_s == pytest.approx(0.96) and t.sys_s == pytest.approx(0.35)
    assert t.peak_rss_mb == pytest.approx(265592 / 1024)
    assert t.n_commands == 1


def test_parse_hours_and_aggregation():
    text = (
        "Elapsed time: 1:02:03.50[h:]min:sec. CPU time: user 10 sys 1 (99%). Peak memory: 1000KB.\n"
        "noise\n"
        "Elapsed time: 0:10.00[h:]min:sec. CPU time: user 2 sys 0.5 (99%). Peak memory: 3000KB.\n"
    )
    t = parse_elapsed_lines(text)
    assert t.wall_s == pytest.approx(3723.5 + 10.0)
    assert t.user_s == pytest.approx(12) and t.sys_s == pytest.approx(1.5)
    assert t.peak_rss_mb == pytest.approx(3000 / 1024)  # max, not sum
    assert t.n_commands == 2


def test_no_timing_returns_none():
    assert parse_elapsed_lines("Error: something broke") is None


@pytest.mark.parametrize(
    ("step", "stage"),
    [
        ("1_2_yosys", "synth"),
        ("2_1_floorplan", "floorplan"),
        ("3_3_place_gp", "place"),
        ("4_1_cts", "cts"),
        ("5_2_route", "route"),
        ("6_report", "finish"),
        ("write_binary_libs", "other"),
        ("9_bad", "other"),
    ],
)
def test_stage_of(step, stage):
    assert stage_of(step) == stage


def test_metrics_real_fixture():
    m = parse_step_metrics(FIXTURES / "3_3_place_gp.json")
    assert m["globalplace__design__instance__count"] == 699.0
    assert isinstance(m["globalplace__timing__setup__ws"], float)


def test_metrics_drop_non_finite_and_nested(tmp_path):
    p = tmp_path / "x.json"
    p.write_text('{"a": NaN, "b": Infinity, "c": 1, "d": {"x": 1}, "e": [1], "f": "ok", "g": true}')
    assert parse_step_metrics(p) == {"c": 1.0, "f": "ok", "g": 1.0}


def test_metrics_malformed_json_is_empty():
    assert parse_step_metrics(FIXTURES / "9_bad.json") == {}


def test_collect_steps_on_real_fixture():
    steps = {s.step: s for s in collect_steps(FIXTURES)}
    assert [s.stage for s in collect_steps(FIXTURES)][0] == "synth"  # flow order
    place = steps["3_3_place_gp"]
    assert place.stage == "place"
    assert place.timing.wall_s == pytest.approx(1.05)
    assert place.metrics["globalplace__design__nets"] == 726.0
    assert steps["1_2_yosys"].timing is not None
    assert steps["1_2_yosys"].metrics == {}


def test_collect_missing_dir(tmp_path):
    assert collect_steps(tmp_path / "nope") == []


ELAPSED = (
    "Elapsed time: 0:01.50[h:]min:sec. CPU time: user 1.40 sys 0.05 (96%). Peak memory: 100000KB.\n"
)


def test_collect_maps_leftover_tmp_log_to_unfinished_step(tmp_path):
    # Regression: a run killed mid detailed-route leaves "5_2_route.tmp.log" (c04_core crash).
    (tmp_path / "5_1_grt.log").write_text(ELAPSED)
    (tmp_path / "5_2_route.tmp.log").write_text("[INFO DRT-0195] Start detailed routing.\n")
    steps = {s.step: s for s in collect_steps(tmp_path)}
    assert set(steps) == {"5_1_grt", "5_2_route"}
    assert steps["5_2_route"].stage == "route"
    assert steps["5_2_route"].timing is None  # unfinished: no timing line
    assert steps["5_2_route"].log_path.name == "5_2_route.tmp.log"


def test_collect_prefers_finished_step_over_tmp_and_skips_odd_names(tmp_path):
    (tmp_path / "5_2_route.log").write_text(ELAPSED)
    (tmp_path / "5_2_route.tmp.log").write_text("stale\n")
    (tmp_path / "weird name.log").write_text(ELAPSED)
    (tmp_path / "a.b.c.log").write_text(ELAPSED)
    steps = collect_steps(tmp_path)
    assert [s.step for s in steps] == ["5_2_route"]
    assert steps[0].timing is not None


# Real lines from ibex_gf180_3d726e63_r0: the LEC check runs inside CTS, and its timing line is
# echoed into 4_1_cts.log before CTS's own (inclusive) line.
LEC = (
    "Elapsed time: 0:17.23[h:]min:sec. CPU time: user 17.39 sys 0.11 (101%). Peak memory: 193288KB."
)
CTS = (
    "Elapsed time: 1:14.01[h:]min:sec. CPU time: user 125.11 sys 10.60 (183%). "
    "Peak memory: 399948KB."
)


def test_nested_substep_time_is_not_double_counted(tmp_path):
    (tmp_path / "4_rsz_lec.log").write_text(f"[naja] No difference was found.\n{LEC}\n")
    (tmp_path / "4_1_cts.log").write_text(f"repair_timing\n{LEC}\nRepair timing passed\n{CTS}\n")
    steps = {s.step: s.timing for s in collect_steps(tmp_path)}
    assert steps["4_rsz_lec"].wall_s == pytest.approx(17.23)
    assert steps["4_1_cts"].wall_s == pytest.approx(74.01 - 17.23)
    assert steps["4_1_cts"].user_s == pytest.approx(125.11 - 17.39)
    assert steps["4_1_cts"].n_commands == 1
    assert steps["4_1_cts"].peak_rss_mb == pytest.approx(399948 / 1024)  # its own line only
    # the stage total equals the enclosing command's wall time (the file timeline agrees)
    assert sum(t.wall_s for t in steps.values()) == pytest.approx(74.01)


def test_identical_lines_without_a_separate_substep_log_still_add_up(tmp_path):
    (tmp_path / "1_2_yosys.log").write_text(f"{LEC}\n{CTS}\n")
    (t,) = [s.timing for s in collect_steps(tmp_path)]
    assert t.wall_s == pytest.approx(17.23 + 74.01) and t.n_commands == 2


def test_nested_longer_than_enclosing_falls_back_to_plain_sum():
    t = parse_elapsed_lines(f"{CTS}\n{LEC}\n", nested=frozenset({CTS}))
    assert t.wall_s == pytest.approx(17.23 + 74.01)  # implausible nesting: not subtracted
