"""Baselines and candidate regressors for per-stage runtime / memory (docs/experiments.md §3).

All models predict on the ln scale. Hyperparameter grids are small and fixed in advance.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin, TransformerMixin
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

SYNTH_CELLS = "m__1_synth__synth__design__instance__count"


def signed_log1p(x: np.ndarray) -> np.ndarray:
    return np.sign(x) * np.log1p(np.abs(x))


class PlatformMedian(BaseEstimator, RegressorMixin):
    """B0: training median of the target per platform (global median for unseen platforms)."""

    def fit(self, x: pd.DataFrame, y: np.ndarray) -> PlatformMedian:
        plats = _platform_of(x)
        y = np.asarray(y, dtype=float)
        self.global_ = float(np.median(y))
        self.by_platform_ = {p: float(np.median(y[plats == p])) for p in np.unique(plats)}
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return np.array([self.by_platform_.get(p, self.global_) for p in _platform_of(x)])


class LogLinearCells(BaseEstimator, RegressorMixin):
    """B1: ln(y) ~ a + b ln(synth cell count) + platform one-hot (needs horizon >= h_synth)."""

    def _design(self, x: pd.DataFrame) -> np.ndarray:
        cells = np.log(np.maximum(x[SYNTH_CELLS].to_numpy(dtype=float), 1.0))
        cells = np.where(np.isfinite(cells), cells, self.fill_)
        plats = np.column_stack([x.get(c, pd.Series(0.0, index=x.index)) for c in self.plat_cols_])
        return np.column_stack([cells, plats])

    def fit(self, x: pd.DataFrame, y: np.ndarray) -> LogLinearCells:
        if SYNTH_CELLS not in x:
            raise ValueError("B1 needs synthesis cell count (horizon >= h_synth)")
        self.plat_cols_ = sorted(c for c in x.columns if c.startswith("plat__"))
        cells = np.log(np.maximum(x[SYNTH_CELLS].to_numpy(dtype=float), 1.0))
        self.fill_ = float(np.nanmedian(cells))
        self.lr_ = LinearRegression().fit(self._design(x), y)
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.lr_.predict(self._design(x))


class DropAllMissing(BaseEstimator, TransformerMixin):
    """Drop columns that are entirely missing in the training rows.

    Such a column carries no information. scikit-learn 1.9.1's HistGradientBoosting crashes
    on one (``window shape cannot be larger than input array shape`` while binning), which
    happens when a fold's training groups never produce a given metric.
    """

    def fit(self, x: pd.DataFrame | np.ndarray, y: object = None) -> DropAllMissing:
        values = np.asarray(x, dtype=float)
        self.keep_ = ~np.isnan(values).all(axis=0)
        return self

    def transform(self, x: pd.DataFrame | np.ndarray) -> pd.DataFrame | np.ndarray:
        if isinstance(x, pd.DataFrame):
            return x.loc[:, self.keep_]
        return np.asarray(x)[:, self.keep_]


class ResidualHybrid(BaseEstimator, RegressorMixin):
    """B1 (log-linear in synth cells + platform), then HGB on B1's residuals (E1b).

    B1 carries the size trend shared across platforms, which trees cannot extrapolate when a
    platform has few large designs. HGB then models what B1 misses.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        max_leaf_nodes: int = 15,
        min_samples_leaf: int = 5,
        max_iter: int = 300,
        random_state: int = 0,
    ) -> None:
        self.learning_rate = learning_rate
        self.max_leaf_nodes = max_leaf_nodes
        self.min_samples_leaf = min_samples_leaf
        self.max_iter = max_iter
        self.random_state = random_state

    def fit(self, x: pd.DataFrame, y: np.ndarray) -> ResidualHybrid:
        y = np.asarray(y, dtype=float)
        self.base_ = LogLinearCells().fit(x, y)
        self.resid_ = make_model(
            "hgb",
            seed=self.random_state,
            learning_rate=self.learning_rate,
            max_leaf_nodes=self.max_leaf_nodes,
            min_samples_leaf=self.min_samples_leaf,
            max_iter=self.max_iter,
        ).fit(x, y - self.base_.predict(x))
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.base_.predict(x) + self.resid_.predict(x)


def _platform_of(x: pd.DataFrame) -> np.ndarray:
    plat_cols = [c for c in x.columns if c.startswith("plat__")]
    if not plat_cols:
        return np.array(["all"] * len(x))
    values = x[plat_cols].to_numpy(dtype=float)
    names = np.array([c.removeprefix("plat__") for c in plat_cols])
    return np.where(values.max(axis=1) > 0, names[values.argmax(axis=1)], "unknown")


def make_model(name: str, seed: int = 0, **params: object) -> BaseEstimator:
    if name == "b0":
        return PlatformMedian()
    if name == "b1":
        return LogLinearCells()
    if name == "ridge":
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            FunctionTransformer(signed_log1p),
            StandardScaler(),
            Ridge(**params),
        )
    if name == "rf":
        return make_pipeline(
            SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True),
            RandomForestRegressor(
                **{"n_estimators": 300, "random_state": seed, "n_jobs": 1, **params}
            ),
        )
    if name == "hgb":
        return make_pipeline(
            DropAllMissing(),
            HistGradientBoostingRegressor(**{"max_iter": 300, "random_state": seed, **params}),
        )
    if name == "hybrid":
        return ResidualHybrid(**{"random_state": seed, **params})
    if name == "hgb_q":  # quantile model for CQR; pass quantile=...
        return make_pipeline(
            DropAllMissing(),
            HistGradientBoostingRegressor(
                **{"loss": "quantile", "max_iter": 300, "random_state": seed, **params}
            ),
        )
    raise ValueError(f"unknown model {name!r}")


GRIDS: dict[str, dict[str, list]] = {
    "b0": {},
    "b1": {},
    "ridge": {"alpha": [0.1, 1.0, 10.0, 100.0]},
    "rf": {"min_samples_leaf": [1, 3], "max_features": [0.33, 1.0]},
    "hgb": {"learning_rate": [0.05, 0.1], "max_leaf_nodes": [7, 15], "min_samples_leaf": [5, 10]},
}
GRIDS["hybrid"] = GRIDS["hgb"]  # E1b: the residual HGB uses the E1 grid


def grid_points(name: str) -> Iterable[dict]:
    grid = GRIDS[name]
    keys = sorted(grid)
    for values in itertools.product(*(grid[k] for k in keys)):
        yield dict(zip(keys, values, strict=True))
