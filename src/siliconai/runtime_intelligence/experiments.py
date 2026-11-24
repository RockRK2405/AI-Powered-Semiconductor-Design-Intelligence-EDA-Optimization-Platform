"""Experiments E1-E4 exactly as pre-registered in docs/experiments.md.

Each ``run_eN`` takes the frozen analysis table and returns a JSON-serialisable dict. The
script ``scripts/run_experiments.py`` adds provenance (dataset hash, git SHA, seed) and writes
``experiments/<id>.json``.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.model_selection import KFold
from sklearn.neighbors import NearestNeighbors
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from siliconai.data.dataset import HORIZONS, STAGE_INDEX, feature_columns, target_stages
from siliconai.runtime_intelligence.evaluate import (
    group_bootstrap_diff,
    logo_oof,
    point_metrics,
)
from siliconai.runtime_intelligence.models import make_model, signed_log1p
from siliconai.uncertainty.conformal import (
    conformal_quantile,
    coverage,
    group_oof_predictions,
    mean_width,
    mondrian_quantiles,
)

PRIMARY_HORIZON = "h_synth"
PRIMARY_TARGETS = ("y__route__ln_wall", "y__total__ln_wall")
BASELINES = ("b0", "b1")
PRIMARY_MODEL = "hgb"
SECONDARY_MODELS = ("ridge", "rf")
E3_PARAMS = {"learning_rate": 0.1, "max_leaf_nodes": 15, "min_samples_leaf": 5}
ALPHA = 0.1
LARGE_ERROR = math.log(1.5)


def _xyg(df: pd.DataFrame, horizon: str, target: str):
    rows = df[target].notna()
    sub = df[rows]
    x = sub[feature_columns(sub, horizon)]
    return x, sub[target].to_numpy(dtype=float), sub["meta__design_group"].to_numpy(), sub


def secondary_targets(horizon: str) -> list[str]:
    out = []
    for stage in target_stages(horizon):
        out += [f"y__{stage}__ln_wall", f"y__{stage}__ln_peak"]
    return out


# ------------------------------------------------------------------------------------- E1
def run_e1(
    df: pd.DataFrame, seed: int = 0, grids: dict | None = None
) -> tuple[dict, dict[str, dict[str, np.ndarray]]]:
    """H1: HGB vs the better baseline under LOGO at h_synth (primary: route, total)."""
    grids = grids or {}
    results: dict[str, dict] = {}
    oof: dict[str, dict[str, np.ndarray]] = {}
    for target in (*PRIMARY_TARGETS, *secondary_targets(PRIMARY_HORIZON)):
        if target in results or target not in df:
            continue
        x, y, g, _ = _xyg(df, PRIMARY_HORIZON, target)
        if len(np.unique(g)) < 3:
            continue
        per_model, preds = {}, {}
        for name in (*BASELINES, PRIMARY_MODEL, *SECONDARY_MODELS):
            res = logo_oof(name, x, y, g, seed=seed, grid=grids.get(name))
            preds[name] = res.pred
            per_model[name] = point_metrics(y, res.pred)
        best_base = min(BASELINES, key=lambda b: per_model[b]["mae_ln"])
        comparison = group_bootstrap_diff(
            np.abs(preds[PRIMARY_MODEL] - y), np.abs(preds[best_base] - y), g, seed=seed
        )
        results[target] = {
            "metrics": per_model,
            "best_baseline": best_base,
            "hgb_minus_best_baseline_mae": comparison,
            "supported": comparison["ci_hi"] < 0,
            "primary": target in PRIMARY_TARGETS,
        }
        oof[target] = {"y": y, "groups": g, **preds}
    h1 = all(results[t]["supported"] for t in PRIMARY_TARGETS if t in results)
    return {"horizon": PRIMARY_HORIZON, "targets": results, "H1_supported": h1}, oof


# ------------------------------------------------------------------------------------- E2
def run_e2(df: pd.DataFrame, seed: int = 0, grids: dict | None = None) -> dict:
    """H2: error at each admissible horizon for route and finish wall time."""
    grids = grids or {}
    out: dict[str, dict] = {}
    for stage in ("route", "finish"):
        target = f"y__{stage}__ln_wall"
        per_h, abs_err = {}, {}
        for horizon, h in HORIZONS.items():
            if h < 0 or h >= STAGE_INDEX[stage]:
                continue
            x, y, g, _ = _xyg(df, horizon, target)
            pred = logo_oof(PRIMARY_MODEL, x, y, g, seed=seed, grid=grids.get("hgb")).pred
            per_h[horizon] = point_metrics(y, pred)
            abs_err[horizon] = (np.abs(pred - y), g)
        cmp = None
        if "h_place" in abs_err and "h_synth" in abs_err:
            (a, g), (b, _) = abs_err["h_place"], abs_err["h_synth"]
            cmp = group_bootstrap_diff(a, b, g, seed=seed)
        out[target] = {"by_horizon": per_h, "h_place_minus_h_synth_mae": cmp}
    supported = all(
        v["h_place_minus_h_synth_mae"] is not None and v["h_place_minus_h_synth_mae"]["ci_hi"] < 0
        for v in out.values()
    )
    return {"targets": out, "H2_supported": supported}


# ------------------------------------------------------------------------------------- E3
def _intervals_for_split(x, y, g, plat, tr, te, seed, rng, params) -> dict[str, tuple]:
    """All four interval methods for one outer split (train rows ``tr``, test rows ``te``)."""
    xtr, ytr, gtr = x.iloc[tr], y[tr], g[tr]
    out = {}

    def _hgb(seed: int, **kw):
        return make_model("hgb", seed=seed, **{**params, **kw})

    # (i) naive split conformal: random 25% of training rows for calibration
    perm = rng.permutation(len(tr))
    cal, fit = perm[: max(len(tr) // 4, 2)], perm[max(len(tr) // 4, 2) :]
    model = _hgb(seed).fit(xtr.iloc[fit], ytr[fit])
    q = conformal_quantile(np.abs(model.predict(xtr.iloc[cal]) - ytr[cal]), ALPHA)
    p = model.predict(x.iloc[te])
    out["naive_split"] = (p - q, p + q)

    # (ii) group-OOF conformal: scores are errors on unseen training groups
    def fp(a, b, c):
        return _hgb(seed).fit(a, b).predict(c)

    oof = group_oof_predictions(fp, xtr, ytr, gtr)
    scores = np.abs(oof - ytr)
    full = _hgb(seed).fit(xtr, ytr)
    p = full.predict(x.iloc[te])
    q = conformal_quantile(scores, ALPHA)
    out["group_oof"] = (p - q, p + q)

    # (iv) Mondrian by platform on the same scores
    qm = mondrian_quantiles(scores, plat[tr], plat[te], ALPHA)
    out["mondrian_platform"] = (p - qm, p + qm)

    # (iii) CQR with group-OOF calibration
    def fq(quant):
        def f(a, b, c):
            return _hgb(seed, loss="quantile", quantile=quant).fit(a, b).predict(c)

        return f

    lo_oof = group_oof_predictions(fq(ALPHA / 2), xtr, ytr, gtr)
    hi_oof = group_oof_predictions(fq(1 - ALPHA / 2), xtr, ytr, gtr)
    q = conformal_quantile(np.maximum(lo_oof - ytr, ytr - hi_oof), ALPHA)
    lo = fq(ALPHA / 2)(xtr, ytr, x.iloc[te])
    hi = fq(1 - ALPHA / 2)(xtr, ytr, x.iloc[te])
    out["cqr_group_oof"] = (lo - q, hi + q)
    return out


def run_e3(df: pd.DataFrame, seed: int = 0, params: dict | None = None) -> dict:
    """H3: coverage of four interval methods under random 5-fold vs LOGO."""
    params = E3_PARAMS if params is None else params
    rng = np.random.default_rng(seed)
    out: dict[str, dict] = {}
    for target in PRIMARY_TARGETS:
        x, y, g, sub = _xyg(df, PRIMARY_HORIZON, target)
        plat = sub["meta__platform"].to_numpy()
        splits = {
            "random5": list(KFold(5, shuffle=True, random_state=seed).split(x)),
            "logo": [(np.flatnonzero(g != v), np.flatnonzero(g == v)) for v in np.unique(g)],
        }
        out[target] = {}
        for split_name, folds in splits.items():
            lo = {m: np.full(len(y), np.nan) for m in _METHODS}
            hi = {m: np.full(len(y), np.nan) for m in _METHODS}
            for tr, te in folds:
                for m, (a, b) in _intervals_for_split(
                    x, y, g, plat, tr, te, seed, rng, params
                ).items():
                    lo[m][te], hi[m][te] = a, b
            out[target][split_name] = {
                m: {
                    "coverage": coverage(y, lo[m], hi[m]),
                    "coverage_ci": _group_boot_coverage(y, lo[m], hi[m], g, seed),
                    "mean_width_ln": mean_width(lo[m], hi[m]),
                }
                for m in _METHODS
            }
    return {"alpha": ALPHA, "targets": out, "H3": _judge_h3(out)}


_METHODS = ("naive_split", "group_oof", "cqr_group_oof", "mondrian_platform")


def _group_boot_coverage(y, lo, hi, g, seed, n_boot=2000) -> list[float]:
    hit = (y >= lo) & (y <= hi)
    uniq = np.unique(g)
    idx = [np.flatnonzero(g == v) for v in uniq]
    rng = np.random.default_rng(seed)
    vals = [
        hit[np.concatenate([idx[j] for j in rng.integers(0, len(uniq), len(uniq))])].mean()
        for _ in range(n_boot)
    ]
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def _judge_h3(out: dict) -> dict:
    verdict = {}
    for target, res in out.items():
        naive_ok_random = res["random5"]["naive_split"]["coverage"] >= 0.88
        naive_under_logo = res["logo"]["naive_split"]["coverage"] < 0.85
        restored = any(
            res["logo"][m]["coverage"] >= 0.88
            for m in ("group_oof", "cqr_group_oof", "mondrian_platform")
        )
        verdict[target] = {
            "naive_covers_random": naive_ok_random,
            "naive_undercovers_logo": naive_under_logo,
            "group_aware_restores": restored,
            "supported": naive_ok_random and naive_under_logo and restored,
        }
    return verdict


# ------------------------------------------------------------------------------------- E4
def ood_scores_logo(x: pd.DataFrame, g: np.ndarray, k: int = 5) -> np.ndarray:
    """Mean distance to the k nearest *training-group* rows, for every row (LOGO)."""
    scores = np.empty(len(x))
    for v in np.unique(g):
        te = g == v
        prep = make_pipeline(
            SimpleImputer(strategy="median", keep_empty_features=True),
            FunctionTransformer(signed_log1p),
            StandardScaler(),
        ).fit(x[~te])
        nn = NearestNeighbors(n_neighbors=min(k, int((~te).sum()))).fit(prep.transform(x[~te]))
        dist, _ = nn.kneighbors(prep.transform(x[te]))
        scores[te] = dist.mean(axis=1)
    return scores


def selective_large_error(abs_err, score, cov) -> float:
    keep = np.argsort(score, kind="stable")[: max(1, int(round(cov * len(score))))]
    return float(np.mean(abs_err[keep] > LARGE_ERROR))


def run_e4(df: pd.DataFrame, e1_oof: dict, seed: int = 0) -> dict:
    """H4: abstaining on high-OOD rows vs random abstention, using E1's HGB predictions."""
    rng = np.random.default_rng(seed)
    out = {}
    for target in PRIMARY_TARGETS:
        if target not in e1_oof:
            continue
        x, y, g, _ = _xyg(df, PRIMARY_HORIZON, target)
        abs_err = np.abs(e1_oof[target][PRIMARY_MODEL] - y)
        score = ood_scores_logo(x, g)
        res = {"overall_large_error_rate": float(np.mean(abs_err > LARGE_ERROR))}
        for cov in (0.8, 0.9):
            ood = selective_large_error(abs_err, score, cov)
            rand = [selective_large_error(abs_err, rng.random(len(y)), cov) for _ in range(1000)]
            boot = _boot_selective(abs_err, score, g, cov, seed)
            res[f"coverage_{cov}"] = {
                "ood_abstention": ood,
                "random_abstention_mean": float(np.mean(rand)),
                "ood_minus_random_ci": boot,
                "supported": boot[1] < 0,
            }
        res["supported"] = all(res[f"coverage_{c}"]["supported"] for c in (0.8, 0.9))
        out[target] = res
    return {"targets": out, "H4_supported": all(v["supported"] for v in out.values())}


def _boot_selective(abs_err, score, g, cov, seed, n_boot=1000) -> list[float]:
    """Group bootstrap of [large-error rate | OOD abstention] - [rate | random abstention]."""
    uniq = np.unique(g)
    idx = [np.flatnonzero(g == v) for v in uniq]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        rows = np.concatenate([idx[j] for j in rng.integers(0, len(uniq), len(uniq))])
        e, s = abs_err[rows], score[rows]
        rand = float(np.mean(e > LARGE_ERROR))  # expected rate under random abstention
        diffs.append(selective_large_error(e, s, cov) - rand)
    return [float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))]
