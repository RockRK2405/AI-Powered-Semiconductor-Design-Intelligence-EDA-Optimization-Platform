"""Runtime models and LOGO evaluation on synthetic tables (sanity checks, not results)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from siliconai.runtime_intelligence.evaluate import (
    group_bootstrap_diff,
    logo_oof,
    point_metrics,
)
from siliconai.runtime_intelligence.models import SYNTH_CELLS, make_model

# tiny grids keep unit tests fast; the pre-registered grids are used in experiments
FAST = {
    "b0": None,
    "b1": None,
    "ridge": [{"alpha": 1.0}, {"alpha": 10.0}],
    "hgb": [{"max_iter": 40, "min_samples_leaf": 3}],
}


def synthetic_table(n_groups=8, per=6, seed=0):
    """ln(route time) = 0.9 ln(cells) + platform offset + noise; cells vary per group."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        cells = 10 ** rng.uniform(2.5, 4.5)
        for _ in range(per):
            plat = "nangate45" if rng.random() < 0.5 else "sky130hd"
            util = rng.choice([30.0, 50.0, np.nan])
            c = cells * rng.uniform(0.9, 1.1)
            y = 0.9 * np.log(c) + (1.5 if plat == "sky130hd" else 0.0) + rng.normal(0, 0.05)
            rows.append(
                {
                    SYNTH_CELLS: c,
                    "plat__nangate45": float(plat == "nangate45"),
                    "plat__sky130hd": float(plat == "sky130hd"),
                    "cfg__CORE_UTILIZATION": util,
                    "group": f"g{g}",
                    "y": y,
                }
            )
    return pd.DataFrame(rows)


def test_baselines_behave():
    df = synthetic_table()
    x, y = df.drop(columns=["group", "y"]), df["y"].to_numpy()
    b0 = make_model("b0").fit(x, y)
    assert set(np.round(b0.predict(x), 6)) <= set(np.round(list(b0.by_platform_.values()), 6))
    b1 = make_model("b1").fit(x, y)
    assert point_metrics(y, b1.predict(x))["mae_ln"] < 0.1
    with pytest.raises(ValueError):
        make_model("b1").fit(x.drop(columns=[SYNTH_CELLS]), y)


def test_logo_oof_predicts_every_row_without_its_group():
    df = synthetic_table()
    x, y, g = df.drop(columns=["group", "y"]), df["y"].to_numpy(), df["group"].to_numpy()
    for name in ("b0", "b1", "ridge", "hgb"):
        res = logo_oof(name, x, y, g, grid=FAST[name])
        assert not np.isnan(res.pred).any()
        assert set(res.chosen) == set(np.unique(g))
    # the log-linear structure is learnable from other groups: B1 beats B0 clearly
    b0 = point_metrics(y, logo_oof("b0", x, y, g).pred)["mae_ln"]
    b1 = point_metrics(y, logo_oof("b1", x, y, g).pred)["mae_ln"]
    assert b1 < 0.5 * b0


def test_logo_detects_memorization():
    """A model fed a group-identity feature looks perfect in-sample but not under LOGO."""
    df = synthetic_table()
    x = df.drop(columns=["group", "y"]).copy()
    x["leaky_group_id"] = df["group"].str[1:].astype(float)
    y, g = df["y"].to_numpy(), df["group"].to_numpy()
    in_sample = make_model("hgb", max_iter=40, min_samples_leaf=3).fit(x, y).predict(x)
    assert (
        point_metrics(y, in_sample)["mae_ln"]
        < point_metrics(y, logo_oof("hgb", x, y, g, grid=FAST["hgb"]).pred)["mae_ln"]
    )


def test_point_metrics_values():
    y = np.log(np.array([100.0, 100.0, 100.0, 100.0]))
    pred = np.log(np.array([100.0, 50.0, 150.0, 100.0]))
    m = point_metrics(y, pred)
    assert m["underestimate_rate"] == 0.25
    assert m["mdape"] == pytest.approx(0.25)


def test_group_bootstrap_ci():
    rng = np.random.default_rng(0)
    groups = np.repeat(np.arange(20), 5)
    a = np.abs(rng.normal(0.1, 0.02, 100))
    b = a + 0.05  # a is uniformly better
    res = group_bootstrap_diff(a, b, groups, n_boot=500)
    assert res["ci_hi"] < 0 and res["diff"] == pytest.approx(-0.05)
    same = group_bootstrap_diff(a, a, groups, n_boot=200)
    assert same["ci_lo"] == same["ci_hi"] == 0.0
