"""Conformal prediction, hand-implemented (ADR-007; TODO P2-06).

All functions work on plain numpy arrays and are model-agnostic. Intervals are produced on
whatever scale the caller uses (we use ln(seconds) and ln(MB)).

Methods (see docs/experiments.md, E3):
  * split conformal          -- absolute-residual scores on a calibration set
  * group out-of-fold (OOF)  -- calibration scores from leave-one-group-out predictions on the
                                training groups, so each score is "error on an unseen design"
  * CQR                      -- conformalized quantile regression (Romano et al., 2019)
  * Mondrian                 -- a separate quantile per category (e.g. per platform)

Guarantee: split conformal gives >= 1 - alpha marginal coverage when calibration and test points
are exchangeable. The group-OOF variant assumes exchangeability between *design groups*, which
is the assumption that matches the unseen-design setting. Its guarantee is approximate (like
cross-conformal), so we measure its coverage empirically rather than assume it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

import numpy as np

FitPredict = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]


def conformal_quantile(scores: Sequence[float] | np.ndarray, alpha: float) -> float:
    """The ceil((n + 1)(1 - alpha))-th smallest score; +inf if n is too small."""
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    s = np.sort(np.asarray(scores, dtype=float))
    if s.size == 0 or np.isnan(s).any():
        raise ValueError("scores must be non-empty and finite")
    k = math.ceil((s.size + 1) * (1 - alpha))
    return float("inf") if k > s.size else float(s[k - 1])


def split_conformal(
    cal_true: np.ndarray, cal_pred: np.ndarray, test_pred: np.ndarray, alpha: float
) -> tuple[np.ndarray, np.ndarray]:
    """Symmetric intervals ``test_pred +- q`` from absolute calibration residuals."""
    q = conformal_quantile(np.abs(np.asarray(cal_true) - np.asarray(cal_pred)), alpha)
    test_pred = np.asarray(test_pred, dtype=float)
    return test_pred - q, test_pred + q


def cqr(
    cal_true: np.ndarray,
    cal_lo: np.ndarray,
    cal_hi: np.ndarray,
    test_lo: np.ndarray,
    test_hi: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Conformalized quantile regression: widen (or shrink) quantile bands by q."""
    y = np.asarray(cal_true, dtype=float)
    scores = np.maximum(np.asarray(cal_lo) - y, y - np.asarray(cal_hi))
    q = conformal_quantile(scores, alpha)
    return np.asarray(test_lo, dtype=float) - q, np.asarray(test_hi, dtype=float) + q


def mondrian_quantiles(
    scores: np.ndarray,
    cal_classes: np.ndarray,
    test_classes: np.ndarray,
    alpha: float,
    min_class_size: int = 10,
) -> np.ndarray:
    """Per-test-point quantile, computed within each class.

    Classes with fewer than ``min_class_size`` calibration points fall back to the pooled
    quantile, which is reported rather than hidden: callers can check ``fallback_classes``.
    """
    scores = np.asarray(scores, dtype=float)
    cal_classes = np.asarray(cal_classes)
    pooled = conformal_quantile(scores, alpha)
    out = np.empty(len(test_classes), dtype=float)
    for i, c in enumerate(np.asarray(test_classes)):
        mask = cal_classes == c
        out[i] = conformal_quantile(scores[mask], alpha) if mask.sum() >= min_class_size else pooled
    return out


def fallback_classes(cal_classes: np.ndarray, min_class_size: int = 10) -> list:
    values, counts = np.unique(np.asarray(cal_classes), return_counts=True)
    return [v for v, n in zip(values, counts, strict=True) if n < min_class_size]


def group_oof_predictions(
    fit_predict: FitPredict, x: np.ndarray, y: np.ndarray, groups: np.ndarray
) -> np.ndarray:
    """Leave-one-group-out predictions for every row (each row predicted by a model that never
    saw its group). Used to build group-aware calibration scores."""
    x, y, groups = np.asarray(x), np.asarray(y), np.asarray(groups)
    uniq = np.unique(groups)
    if uniq.size < 2:
        raise ValueError("need at least two groups")
    pred = np.empty(y.shape[0], dtype=float)
    for g in uniq:
        test = groups == g
        pred[test] = fit_predict(x[~test], y[~test], x[test])
    return pred


def coverage(y: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> float:
    y = np.asarray(y)
    return float(np.mean((y >= np.asarray(lo)) & (y <= np.asarray(hi))))


def mean_width(lo: np.ndarray, hi: np.ndarray) -> float:
    return float(np.mean(np.asarray(hi) - np.asarray(lo)))
