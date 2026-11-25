"""E5 / H5: log diagnosis on held-out designs and fault variants (docs/experiments.md §11)."""

from __future__ import annotations

import json
import tarfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from sklearn.metrics import roc_auc_score

from siliconai.log_intelligence.diagnose import (
    RawTextClassifier,
    TemplateClassifier,
    template_novelty,
)
from siliconai.log_intelligence.logs import Line, load_run_lines
from siliconai.log_intelligence.rules import (
    FAILURE_CLASSES,
    error_line_evidence,
    has_gold,
    is_gold,
    keyword_predict,
)

N_BOOT = 2000
LABELLED_STATUSES = ("failed", "timeout")


@dataclass
class Run:
    run_id: str
    group: str
    origin: str
    platform: str
    cls: str
    variant: str
    status: str
    lines: list[Line]


def extract_archives(archives: list[Path], dest: Path) -> Path:
    """Extract log tarballs with the ``data`` filter (no absolute paths, links or traversal)."""
    dest.mkdir(parents=True, exist_ok=True)
    for a in archives:
        with tarfile.open(a) as t:
            t.extractall(dest, filter="data")
    return dest


def load_d2(records: Path, logs_root: Path) -> list[Run]:
    recs: dict[str, dict] = {}
    for line in Path(records).read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            recs[r["run_id"]] = r
    runs = []
    for r in recs.values():
        if r["status"] not in ("success", "failed", "timeout"):
            continue
        log_dir = logs_root / r["log_dir"] if r.get("log_dir") else None
        lines = load_run_lines(logs_root / r["console_log"], log_dir)
        runs.append(
            Run(
                r["run_id"],
                r["group"],
                r["origin"],
                r["platform"],
                r["fault_class"],
                r["variant"],
                r["status"],
                lines,
            )
        )
    runs.sort(key=lambda x: x.run_id)
    return runs


def macro_f1(y: np.ndarray, p: np.ndarray) -> float:
    f1s = []
    for c in FAILURE_CLASSES:
        tp = np.sum((p == c) & (y == c))
        fp = np.sum((p == c) & (y != c))
        fn = np.sum((p != c) & (y == c))
        f1s.append(0.0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    return float(np.mean(f1s))


def per_class_f1(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    out = {}
    for c in FAILURE_CLASSES:
        tp = np.sum((p == c) & (y == c))
        fp = np.sum((p == c) & (y != c))
        fn = np.sum((p != c) & (y == c))
        out[c] = 0.0 if tp == 0 else float(2 * tp / (2 * tp + fp + fn))
    return out


def _boot_idx(groups: np.ndarray, seed: int):
    uniq = np.unique(groups)
    idx = [np.flatnonzero(groups == g) for g in uniq]
    rng = np.random.default_rng(seed)
    for _ in range(N_BOOT):
        yield np.concatenate([idx[j] for j in rng.integers(0, len(uniq), len(uniq))])


def boot_diff(stat, a, b, groups, seed: int = 0) -> dict:
    """Paired group bootstrap of stat(a) - stat(b); ``stat`` takes a row-index array."""
    diffs = np.array([stat(a, rows) - stat(b, rows) for rows in _boot_idx(groups, seed)])
    all_rows = np.arange(len(groups))
    return {
        "a": float(stat(a, all_rows)),
        "b": float(stat(b, all_rows)),
        "diff": float(stat(a, all_rows) - stat(b, all_rows)),
        "ci_lo": float(np.percentile(diffs, 2.5)),
        "ci_hi": float(np.percentile(diffs, 97.5)),
        "n_groups": int(np.unique(groups).size),
        "n": int(len(groups)),
    }


def _f1_stat(y):
    return lambda p, rows: macro_f1(y[rows], p[rows])


def confusion(y, p) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {c: {} for c in FAILURE_CLASSES}
    for a, b in zip(y, p, strict=True):
        out[a][b] = out[a].get(b, 0) + 1
    return out


def _fit_predict(train: list[Run], test: list[Run]) -> dict:
    xs, ys = [r.lines for r in train], [r.cls for r in train]
    tpl = TemplateClassifier().fit(xs, ys)
    tests = [r.lines for r in test]
    pred = tpl.predict(tests)
    ev = [tpl.evidence(r.lines, c) for r, c in zip(test, pred, strict=True)]
    return {
        "tpl": pred,
        "tpl_ev": ev,
        "svc": TemplateClassifier(svm=True).fit(xs, ys).predict(tests),
        "raw": RawTextClassifier().fit(xs, ys).predict(tests),
    }


def run_e5(runs: list[Run], natural: dict[str, tuple[str, list[Line]]] | None = None) -> dict:
    lab = [r for r in runs if r.cls != "none" and r.status in LABELLED_STATUSES]
    clean = [r for r in runs if r.cls == "none" and r.status == "success"]
    y = np.array([r.cls for r in lab])
    g = np.array([r.group for r in lab])
    kw = [keyword_predict(r.lines) for r in lab]
    p_kw = np.array([c for c, _ in kw])
    out: dict = {"n_labelled": len(lab), "n_clean_success": len(clean)}

    # ---- S-design: leave one design group out
    pd_ = {k: np.empty(len(lab), dtype=object) for k in ("tpl", "svc", "raw")}
    ev_tpl: list = [None] * len(lab)
    for grp in np.unique(g):
        te = np.flatnonzero(g == grp)
        tr = np.flatnonzero(g != grp)
        res = _fit_predict([lab[i] for i in tr], [lab[i] for i in te])
        for k in pd_:
            pd_[k][te] = res[k]
        for j, i in enumerate(te):
            ev_tpl[i] = res["tpl_ev"][j]
    # ---- S-variant: leave one (class, variant) out
    pv = {k: np.empty(len(lab), dtype=object) for k in ("tpl", "svc", "raw")}
    keys = np.array([f"{r.cls}/{r.variant}" for r in lab])
    for key in np.unique(keys):
        te = np.flatnonzero(keys == key)
        tr = np.flatnonzero(keys != key)
        res = _fit_predict([lab[i] for i in tr], [lab[i] for i in te])
        for k in pv:
            pv[k][te] = res[k]

    st = _f1_stat(y)
    out["P1_design_macro_f1_tpl_minus_kw"] = boot_diff(st, pd_["tpl"], p_kw, g)
    out["P2_variant_macro_f1_tpl_minus_kw"] = boot_diff(st, pv["tpl"], p_kw, g)

    # ---- P3: top-3 evidence (S-design)
    ok = np.array([has_gold(r.cls, r.lines) for r in lab])
    hit_t = np.array([any(is_gold(r.cls, ln) for ln in ev_tpl[i]) for i, r in enumerate(lab)])
    hit_b = np.array([any(is_gold(r.cls, ln) for ln in error_line_evidence(r.lines)) for r in lab])
    hit_kw = np.array(
        [kw[i][1] is not None and is_gold(r.cls, kw[i][1]) for i, r in enumerate(lab)]
    )

    def mean_stat(v, rows):
        return float(np.mean(v[rows])) if len(rows) else float("nan")

    sel = np.flatnonzero(ok)
    out["P3_evidence_top3_tpl_minus_errorlines"] = boot_diff(
        mean_stat, hit_t[sel], hit_b[sel], g[sel]
    )
    out["P3_excluded_no_gold_line"] = int((~ok).sum())
    p1, p2, p3 = (
        out[k]
        for k in (
            "P1_design_macro_f1_tpl_minus_kw",
            "P2_variant_macro_f1_tpl_minus_kw",
            "P3_evidence_top3_tpl_minus_errorlines",
        )
    )
    out["H5a_supported"] = p1["ci_lo"] > 0 and p2["ci_lo"] > 0
    out["H5b_supported"] = p3["ci_lo"] > 0

    # ---- secondary 1/2
    out["S1"] = {
        split: {k: macro_f1(y, preds[k]) for k in ("tpl", "svc", "raw")} | {"kw": macro_f1(y, p_kw)}
        for split, preds in (("design", pd_), ("variant", pv))
    }
    out["S1"]["raw_minus_tpl_design"] = boot_diff(st, pd_["raw"], pd_["tpl"], g)
    out["S1"]["svc_minus_tpl_design"] = boot_diff(st, pd_["svc"], pd_["tpl"], g)
    origin = np.array([r.origin for r in lab])
    out["S2"] = {
        "per_class_f1_design": {"tpl": per_class_f1(y, pd_["tpl"]), "kw": per_class_f1(y, p_kw)},
        "per_class_f1_variant": {"tpl": per_class_f1(y, pv["tpl"]), "kw": per_class_f1(y, p_kw)},
        "confusion_design": {"tpl": confusion(y, pd_["tpl"]), "kw": confusion(y, p_kw)},
        "confusion_variant": {"tpl": confusion(y, pv["tpl"])},
        "macro_f1_by_origin_design": {
            o: {
                "n": int((origin == o).sum()),
                "tpl": macro_f1(y[origin == o], pd_["tpl"][origin == o]),
                "kw": macro_f1(y[origin == o], p_kw[origin == o]),
            }
            for o in np.unique(origin)
        },
        "class_counts": dict(Counter(y.tolist())),
    }
    # ---- secondary 3: anomaly and novel-class detection
    groups_all = sorted({r.group for r in runs})
    sc, lbl = [], []
    for grp in groups_all:
        train_clean = [r.lines for r in clean if r.group != grp]
        test = [r for r in lab + clean if r.group == grp]
        if not test or not train_clean:
            continue
        sc += list(template_novelty(train_clean, [r.lines for r in test]))
        lbl += [int(r.cls != "none") for r in test]
    out["S3a_anomaly_auroc_failed_vs_clean"] = (
        float(roc_auc_score(lbl, sc)) if len(set(lbl)) == 2 else None
    )
    nov_s, nov_l = [], []
    for c in FAILURE_CLASSES:
        for grp in np.unique(g):
            tr = [r for r in lab if r.cls != c and r.group != grp]
            te = [r for r in lab if r.group == grp]
            if not te or len({r.cls for r in tr}) < 2:
                continue
            m = TemplateClassifier().fit([r.lines for r in tr], [r.cls for r in tr])
            nov_s += list(1 - m.predict_proba([r.lines for r in te]).max(axis=1))
            nov_l += [int(r.cls == c) for r in te]
    out["S3b_novel_class_auroc"] = float(roc_auc_score(nov_l, nov_s))
    out["S4_keyword_line_evidence_hit_rate"] = float(hit_kw[sel].mean())
    out["P3_detail"] = {
        "tpl_hit_rate_by_class": {
            c: float(hit_t[sel][y[sel] == c].mean()) for c in FAILURE_CLASSES if (y[sel] == c).any()
        },
        "errorlines_hit_rate_by_class": {
            c: float(hit_b[sel][y[sel] == c].mean()) for c in FAILURE_CLASSES if (y[sel] == c).any()
        },
    }
    # ---- secondary 5: natural failures
    if natural:
        m = TemplateClassifier().fit([r.lines for r in lab], list(y))
        nat = {}
        for rid, (label, lines) in sorted(natural.items()):
            proba = m.predict_proba([lines])[0]
            pred = str(m.classes_[int(np.argmax(proba))])
            kwp, kwl = keyword_predict(lines)
            nat[rid] = {
                "label": label,
                "tpl": pred,
                "tpl_max_proba": float(proba.max()),
                "tpl_evidence": [ln.text[:200] for ln in m.evidence(lines, pred)],
                "kw": kwp,
                "kw_line": kwl.text[:200] if kwl else None,
            }
        out["S5_natural"] = nat
    # ---- secondary 6: manifestation table
    man: dict[str, Counter] = defaultdict(Counter)
    for r in runs:
        man[f"{r.cls}/{r.variant}"][r.status] += 1
    out["S6_manifestation"] = {k: dict(v) for k, v in sorted(man.items())}
    return out


def load_natural(labels_yaml: Path, root: Path) -> dict[str, tuple[str, list[Line]]]:
    labels = yaml.safe_load(Path(labels_yaml).read_text())["runs"]
    out = {}
    for rid, label in labels.items():
        dirs = list((root / "logs").glob(f"*/*/{rid}"))
        out[rid] = (
            label,
            load_run_lines(root / "console" / f"{rid}.log", dirs[0] if dirs else None),
        )
    return out
