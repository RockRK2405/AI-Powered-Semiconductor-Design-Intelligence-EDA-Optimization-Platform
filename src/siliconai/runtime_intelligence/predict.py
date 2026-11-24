"""Predict a run's cost as if its design had never been seen, with a conformal interval.

Used by the dashboard: for a chosen run, the model is trained on every *other* design group,
and the interval uses group out-of-fold calibration on those groups (E3 method ii). So what
the page shows is an honest unseen-design prediction, not a fit to data it has seen.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from siliconai.data.dataset import feature_columns
from siliconai.runtime_intelligence.models import make_model
from siliconai.uncertainty.conformal import conformal_quantile, group_oof_predictions

DEFAULT_PARAMS = {"learning_rate": 0.1, "max_leaf_nodes": 15, "min_samples_leaf": 5}


def predict_unseen(
    df: pd.DataFrame,
    run_id: str,
    target: str,
    horizon: str = "h_synth",
    alpha: float = 0.1,
    params: dict | None = None,
) -> dict:
    """Point prediction and (1 - alpha) interval for ``run_id``, in seconds (or MB)."""
    params = DEFAULT_PARAMS if params is None else params
    rows = df[df[target].notna()]
    if run_id not in set(rows["meta__run_id"]):
        raise ValueError(f"{run_id} has no value for {target}")
    group = rows.loc[rows["meta__run_id"] == run_id, "meta__design_group"].iloc[0]
    train = rows[rows["meta__design_group"] != group]
    if train["meta__design_group"].nunique() < 2:
        raise ValueError("need at least two other design groups to train and calibrate")
    feats = feature_columns(train, horizon)
    x, y, g = train[feats], train[target].to_numpy(float), train["meta__design_group"].to_numpy()

    def fit_predict(a, b, c):
        return make_model("hgb", **params).fit(a, b).predict(c)

    scores = np.abs(group_oof_predictions(fit_predict, x, y, g) - y)
    q = conformal_quantile(scores, alpha)
    row = rows[rows["meta__run_id"] == run_id]
    point = float(make_model("hgb", **params).fit(x, y).predict(row[feats])[0])
    actual = float(row[target].iloc[0])
    return {
        "run_id": run_id,
        "target": target,
        "horizon": horizon,
        "held_out_group": group,
        "train_groups": int(train["meta__design_group"].nunique()),
        "point": math.exp(point),
        "lo": math.exp(point - q),
        "hi": math.exp(point + q) if math.isfinite(q) else float("inf"),
        "actual": math.exp(actual),
        "covered": abs(point - actual) <= q,
        "alpha": alpha,
    }
