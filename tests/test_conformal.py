"""Property tests for the conformal module on synthetic data (sanity checks, not results)."""

from __future__ import annotations

import numpy as np
import pytest

from siliconai.uncertainty.conformal import (
    conformal_quantile,
    coverage,
    cqr,
    fallback_classes,
    group_oof_predictions,
    mondrian_quantiles,
    split_conformal,
)

ALPHA = 0.1


def test_quantile_definition_and_edge_cases():
    scores = np.arange(1, 20, dtype=float)  # n = 19 -> k = ceil(20 * 0.9) = 18
    assert conformal_quantile(scores, ALPHA) == 18.0
    assert conformal_quantile([1.0, 2.0], ALPHA) == float("inf")  # too few points
    with pytest.raises(ValueError):
        conformal_quantile([], ALPHA)
    with pytest.raises(ValueError):
        conformal_quantile([1.0], 1.5)


def test_split_conformal_marginal_coverage_iid():
    rng = np.random.default_rng(0)
    covs = []
    for _ in range(300):
        y = rng.normal(size=200)
        pred = np.zeros(200)  # any fixed predictor works under exchangeability
        lo, hi = split_conformal(y[:100], pred[:100], pred[100:], ALPHA)
        covs.append(coverage(y[100:], lo, hi))
    mean = float(np.mean(covs))
    # theory: 1 - alpha <= E[coverage] <= 1 - alpha + 1/(n+1)
    assert 0.885 <= mean <= 0.92


def test_cqr_coverage_with_heteroscedastic_noise():
    rng = np.random.default_rng(1)
    covs = []
    for _ in range(200):
        x = rng.uniform(0, 1, 400)
        y = rng.normal(scale=0.1 + x)
        # deliberately mis-scaled quantile estimates: CQR must still fix the coverage
        lo, hi = -0.5 * (0.1 + x), 0.5 * (0.1 + x)
        tlo, thi = cqr(y[:200], lo[:200], hi[:200], lo[200:], hi[200:], ALPHA)
        covs.append(coverage(y[200:], tlo, thi))
    assert 0.88 <= float(np.mean(covs)) <= 0.93


def test_mondrian_covers_each_class_where_pooled_fails():
    rng = np.random.default_rng(2)
    n = 4000
    cls = rng.integers(0, 2, n)
    y = rng.normal(scale=np.where(cls == 1, 3.0, 0.3))
    scores = np.abs(y[: n // 2])
    test_y, test_cls = y[n // 2 :], cls[n // 2 :]
    q_pooled = conformal_quantile(scores, ALPHA)
    q_mond = mondrian_quantiles(scores, cls[: n // 2], test_cls, ALPHA)
    noisy = test_cls == 1
    assert coverage(test_y[noisy], -q_pooled, q_pooled) < 0.85  # pooled under-covers
    for c in (0, 1):
        m = test_cls == c
        assert coverage(test_y[m], -q_mond[m], q_mond[m]) >= 0.88
    assert fallback_classes(cls[:5]) == sorted(set(cls[:5].tolist()))


def _mean_fit_predict(x_tr, y_tr, x_te):
    return np.full(len(x_te), y_tr.mean())


def test_group_oof_predictions_never_see_own_group():
    groups = np.array([0, 0, 1, 1, 2, 2])
    y = np.array([10.0, 10.0, 20.0, 20.0, 30.0, 30.0])
    pred = group_oof_predictions(_mean_fit_predict, np.zeros((6, 1)), y, groups)
    assert pred.tolist() == [25.0, 25.0, 20.0, 20.0, 15.0, 15.0]
    with pytest.raises(ValueError):
        group_oof_predictions(_mean_fit_predict, np.zeros((2, 1)), y[:2], groups[:2])


def test_group_shift_naive_undercovers_group_oof_recovers():
    """Mirror of H3 on synthetic data: rows share a per-group random effect, so residuals of
    rows from *training* groups underestimate the error on a *new* group."""
    rng = np.random.default_rng(3)
    naive_cov, oof_cov = [], []
    for _ in range(60):
        n_groups, per = 30, 20
        groups = np.repeat(np.arange(n_groups), per)
        effect = rng.normal(scale=1.0, size=n_groups)[groups]
        y = effect + rng.normal(scale=0.2, size=groups.size)
        test = groups == 0
        tr_y, tr_g = y[~test], groups[~test]

        # "model": per-group memorizer on seen groups, global mean otherwise
        def fit_predict(x_tr, y_tr, x_te, _g=None):
            return np.full(len(x_te), y_tr.mean())

        # naive: calibration residuals of in-sample group means (memorized groups)
        means = {g: tr_y[tr_g == g].mean() for g in np.unique(tr_g)}
        cal_pred = np.array([means[g] for g in tr_g])
        lo, hi = split_conformal(tr_y, cal_pred, np.full(test.sum(), tr_y.mean()), ALPHA)
        naive_cov.append(coverage(y[test], lo, hi))

        oof = group_oof_predictions(fit_predict, np.zeros((tr_y.size, 1)), tr_y, tr_g)
        lo, hi = split_conformal(tr_y, oof, np.full(test.sum(), tr_y.mean()), ALPHA)
        oof_cov.append(coverage(y[test], lo, hi))
    assert np.mean(naive_cov) < 0.6
    assert np.mean(oof_cov) >= 0.85
