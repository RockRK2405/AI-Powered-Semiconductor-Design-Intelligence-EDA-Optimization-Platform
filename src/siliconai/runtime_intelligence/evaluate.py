"""Leave-one-group-out evaluation, inner model selection and group-bootstrap CIs (E1/E2).

Every prediction for a row comes from a model that never saw the row's design group, and
hyperparameters are chosen using the *training* groups only (inner GroupKFold).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import GroupKFold

from siliconai.runtime_intelligence.models import grid_points, make_model

INNER_FOLDS = 5
UNDERESTIMATE_RATIO = 0.8  # "underestimate" = prediction below 80% of actual


@dataclass
class OofResult:
    model: str
    pred: np.ndarray  # out-of-group prediction for every row (ln scale)
    chosen: dict[str, dict] = field(default_factory=dict)  # outer group -> params


def _select_params(
    name: str, x: pd.DataFrame, y: np.ndarray, groups: np.ndarray, seed: int, points: list[dict]
) -> dict:
    if len(points) <= 1:
        return points[0] if points else {}
    n_splits = min(INNER_FOLDS, len(np.unique(groups)))
    best, best_err = points[0], np.inf
    for params in points:
        errs = []
        for tr, te in GroupKFold(n_splits=n_splits).split(x, y, groups):
            model = make_model(name, seed=seed, **params).fit(x.iloc[tr], y[tr])
            errs.append(np.abs(model.predict(x.iloc[te]) - y[te]))
        err = float(np.mean(np.concatenate(errs)))
        if err < best_err:
            best, best_err = params, err
    return best


def logo_oof(
    name: str,
    x: pd.DataFrame,
    y: np.ndarray,
    groups: np.ndarray,
    seed: int = 0,
    grid: list[dict] | None = None,
) -> OofResult:
    """Out-of-group predictions for every row under leave-one-group-out.

    ``grid`` overrides the pre-registered grid (tests use tiny grids for speed).
    """
    points = list(grid_points(name)) if grid is None else grid
    y = np.asarray(y, dtype=float)
    groups = np.asarray(groups)
    pred = np.full(y.shape[0], np.nan)
    result = OofResult(name, pred)
    for g in np.unique(groups):
        test = groups == g
        params = _select_params(name, x[~test], y[~test], groups[~test], seed, points)
        model = clone(make_model(name, seed=seed, **params)).fit(x[~test], y[~test])
        pred[test] = model.predict(x[test])
        result.chosen[str(g)] = params
    return result


def point_metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    y, pred = np.asarray(y, dtype=float), np.asarray(pred, dtype=float)
    err = pred - y
    ratio = np.exp(err)  # predicted / actual on the original scale
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "mae_ln": float(np.mean(np.abs(err))),
        "mdape": float(np.median(np.abs(ratio - 1.0))),
        "r2_ln": 1.0 - float(np.sum(err**2)) / ss_tot if ss_tot > 0 else float("nan"),
        "underestimate_rate": float(np.mean(ratio < UNDERESTIMATE_RATIO)),
        "n": int(y.size),
    }


def group_bootstrap_diff(
    abs_err_a: np.ndarray,
    abs_err_b: np.ndarray,
    groups: np.ndarray,
    n_boot: int = 2000,
    seed: int = 0,
) -> dict[str, float]:
    """Paired group bootstrap of MAE(a) - MAE(b): resample design groups with replacement."""
    a, b, groups = np.asarray(abs_err_a), np.asarray(abs_err_b), np.asarray(groups)
    uniq = np.unique(groups)
    idx = [np.flatnonzero(groups == g) for g in uniq]
    rng = np.random.default_rng(seed)
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        rows = np.concatenate([idx[j] for j in rng.integers(0, len(uniq), len(uniq))])
        diffs[i] = a[rows].mean() - b[rows].mean()
    return {
        "diff": float(a.mean() - b.mean()),
        "ci_lo": float(np.percentile(diffs, 2.5)),
        "ci_hi": float(np.percentile(diffs, 97.5)),
        "n_groups": int(uniq.size),
    }
