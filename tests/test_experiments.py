"""Smoke tests: E1-E4 run end to end on a small synthetic table and return sane structure."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from siliconai.runtime_intelligence.experiments import (
    ood_scores_logo,
    run_e1,
    run_e1b,
    run_e2,
    run_e3,
    run_e4,
    selective_large_error,
)

CELLS = "m__1_synth__synth__design__instance__count"
FAST = {
    "ridge": [{"alpha": 1.0}],
    "rf": [{"n_estimators": 20}],
    "hgb": [{"max_iter": 30, "min_samples_leaf": 3}],
    "hybrid": [{"max_iter": 30, "min_samples_leaf": 3}],
}


def table(n_groups=7, per=8, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for gi in range(n_groups):
        base = rng.uniform(5, 10)
        for r in range(per):
            plat = ["nangate45", "sky130hd"][r % 2]
            cells = np.exp(base) * rng.uniform(0.9, 1.1)
            place_area = cells * rng.uniform(0.8, 1.2)
            route = (
                0.8 * np.log(place_area) + (1.0 if plat == "sky130hd" else 0) + rng.normal(0, 0.1)
            )
            rows.append(
                {
                    "meta__run_id": f"g{gi}_{r}",
                    "meta__design_group": f"g{gi}",
                    "meta__platform": plat,
                    "meta__origin": "orfs" if gi % 2 else "generated",
                    "plat__nangate45": float(plat == "nangate45"),
                    "plat__sky130hd": float(plat == "sky130hd"),
                    "origin__gen": 0.0,
                    "cfg__CORE_UTILIZATION": np.nan,
                    CELLS: cells,
                    "t__synth__wall_s": cells / 1e3,
                    "m__3_3_place_gp__globalplace__design__instance__area": place_area,
                    "t__place__wall_s": place_area / 1e3,
                    "y__route__ln_wall": route,
                    "y__finish__ln_wall": route - 1.0,
                    "y__total__ln_wall": route + 0.3,
                }
            )
    return pd.DataFrame(rows)


def test_e1_structure():
    res, oof = run_e1(table(), grids=FAST)
    t = res["targets"]["y__route__ln_wall"]
    assert t["primary"] and set(t["metrics"]) == {"b0", "b1", "hgb", "ridge", "rf"}
    assert t["best_baseline"] in {"b0", "b1"}
    assert isinstance(res["H1_supported"], bool)
    assert len(oof["y__route__ln_wall"]["hgb"]) == len(table())


def test_e2_structure():
    res = run_e2(table(), grids=FAST)
    assert set(res["targets"]["y__route__ln_wall"]["by_horizon"]) >= {"h_synth", "h_place"}
    assert "h_route" not in res["targets"]["y__route__ln_wall"]["by_horizon"]
    assert set(res["targets"]["y__finish__ln_wall"]["by_horizon"]) >= {"h_place", "h_route"}


def test_e3_structure_and_coverage_bounds():
    res = run_e3(table(), params={"max_iter": 30, "min_samples_leaf": 3})
    for split in ("random5", "logo"):
        for m in ("naive_split", "group_oof", "cqr_group_oof", "mondrian_platform"):
            r = res["targets"]["y__route__ln_wall"][split][m]
            assert 0.0 <= r["coverage"] <= 1.0 and r["mean_width_ln"] > 0
            lo, hi = r["coverage_ci"]
            assert lo <= r["coverage"] <= hi
    assert set(res["H3"]["y__total__ln_wall"]) >= {"supported"}


def test_e4_ood_scores_and_selection():
    df = table()
    x = df[[CELLS, "plat__nangate45"]]
    s = ood_scores_logo(x, df["meta__design_group"].to_numpy())
    assert s.shape == (len(df),) and (s >= 0).all()
    err = np.array([0.0, 1.0, 0.0, 1.0])
    assert selective_large_error(err, np.array([0, 9, 1, 8]), 0.5) == 0.0
    _, oof = run_e1(df, grids=FAST)
    res = run_e4(df, oof)
    assert "coverage_0.8" in res["targets"]["y__route__ln_wall"]


def test_predict_unseen_never_trains_on_the_runs_group():
    from siliconai.runtime_intelligence.predict import predict_unseen

    df = table()
    res = predict_unseen(
        df, "g3_0", "y__route__ln_wall", params={"max_iter": 30, "min_samples_leaf": 3}
    )
    assert res["held_out_group"] == "g3" and res["train_groups"] == 6
    assert 0 < res["lo"] <= res["point"] <= res["hi"]
    assert res["actual"] > 0 and isinstance(res["covered"], bool)
    with pytest.raises(ValueError):
        predict_unseen(df, "nope", "y__route__ln_wall")


def test_e1b_scores_only_new_rows():
    df = table()
    seen = set(df.loc[df["meta__design_group"].isin(["g0", "g1", "g2"]), "meta__run_id"])
    seen |= set(df["meta__run_id"].iloc[::2])  # half of the other groups' rows are "old"
    res = run_e1b(df, seen, grids=FAST)
    n_new = int((~df["meta__run_id"].isin(seen)).sum())
    for target in ("y__route__ln_wall", "y__total__ln_wall"):
        r = res["targets"][target]
        assert r["n_new"] == n_new
        assert r["new_rows"]["hybrid"]["n"] == n_new
        assert r["all_rows"]["b1"]["n"] == len(df)
        assert sum(v["n"] for v in r["new_rows_by_platform"].values()) == n_new
        assert isinstance(r["supported"], bool)
        for m in ("hgb", "hybrid"):
            assert 0.0 <= r["group_oof_intervals_new"][m]["coverage"] <= 1.0
    assert isinstance(res["H1b_supported"], bool)
    assert "ci_hi" in res["hybrid_route_h_place_minus_h_synth_mae_new"]


def test_e1b_refuses_when_nothing_is_new():
    df = table()
    with pytest.raises(ValueError):
        run_e1b(df, set(df["meta__run_id"]), grids=FAST, with_intervals=False)
