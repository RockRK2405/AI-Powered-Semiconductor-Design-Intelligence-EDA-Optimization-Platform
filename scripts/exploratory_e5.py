"""Exploratory analyses of E5, chosen AFTER seeing its result (docs/experiments.md §9).

Not pre-registered: these can motivate a new pre-registered test on new data, never a claim.
Reported in docs/results_d2.md §3 and §5.

1. ``templates``: fit M-tpl on all labelled D2 runs. For each class, list the top-weighted
   templates and the rank of that class's gold-line templates.
2. ``sensitivity``: drop the aes runs whose RTL mutation broke a relative `include` (their real
   failure is a missing include, not the injected class). Recompute P1 (S-design macro-F1,
   M-tpl − B-kw) with the same group bootstrap.
3. ``kw_misses``: every labelled run B-kw gets wrong, with M-tpl's S-design prediction.

Usage: python scripts/exploratory_e5.py --manifest data/d2/d2_v1.manifest.json --scratch <dir>
(``<dir>`` is the scratch directory given to scripts/run_e5.py; archives are re-extracted.)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from siliconai.log_intelligence.diagnose import TemplateClassifier
from siliconai.log_intelligence.e5 import (
    _f1_stat,
    _fit_predict,
    boot_diff,
    extract_archives,
    load_d2,
)
from siliconai.log_intelligence.rules import GOLD, keyword_predict

LABELLED = ("failed", "timeout")
AES_INCLUDE_ARTEFACT = "Can't open include file `timescale.v'"


def mislabelled(r) -> bool:
    return r.group == "aes" and any(AES_INCLUDE_ARTEFACT in ln.text for ln in r.lines)


def templates(lab) -> dict:
    m = TemplateClassifier().fit([r.lines for r in lab], [r.cls for r in lab])
    tpl = m.tpl.drain.templates
    gold_t: dict[str, set[int]] = {c: set() for c in GOLD}
    for r in lab:
        for ln in r.lines:
            if GOLD[r.cls].search(ln.text):
                t = m.tpl.tid(ln.text)
                if t is not None:
                    gold_t[r.cls].add(t)
    out = {"n_templates": len(tpl), "classes": {}}
    for i, c in enumerate(m.classes_):
        w = m.model.coef_[i]
        out["classes"][str(c)] = {
            "best_gold_rank": min((int((w > w[t]).sum()) + 1 for t in gold_t[c]), default=None),
            "top5": [
                {"coef": round(float(w[t]), 3), "template": " ".join(tpl[t].tokens)[:160]}
                for t in np.argsort(-w)[:5]
            ],
        }
    return out


def design_split_tpl(lab) -> np.ndarray:
    g = np.array([r.group for r in lab])
    pred = np.empty(len(lab), dtype=object)
    for grp in np.unique(g):
        te, tr = np.flatnonzero(g == grp), np.flatnonzero(g != grp)
        pred[te] = _fit_predict([lab[i] for i in tr], [lab[i] for i in te])["tpl"]
    return pred


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--scratch", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, default=Path("experiments"))
    args = ap.parse_args()
    man = json.loads(args.manifest.read_text())
    d2 = args.manifest.parent
    root = extract_archives(sorted((d2 / "logs").glob("*.tar.gz")), args.scratch / "d2x")
    runs = load_d2(d2 / man["records"], root)
    lab = [r for r in runs if r.cls != "none" and r.status in LABELLED]

    out: dict = {"exploratory": True, "dataset_hash": man["content_hash"]}
    out["templates"] = templates(lab)

    y = np.array([r.cls for r in lab])
    g = np.array([r.group for r in lab])
    kw = np.array([keyword_predict(r.lines)[0] for r in lab])
    tpl = design_split_tpl(lab)
    out["kw_misses"] = [
        {"group": r.group, "class": r.cls, "variant": r.variant, "kw": str(kw[i]), "tpl": tpl[i]}
        for i, r in enumerate(lab)
        if kw[i] != r.cls
    ]
    keep = np.array([not mislabelled(r) for r in lab])
    out["sensitivity"] = {
        "dropped": sorted(f"{r.cls}/{r.variant}" for r, k in zip(lab, keep, strict=True) if not k),
        "P1_design_macro_f1_tpl_minus_kw": boot_diff(
            _f1_stat(y[keep]), tpl[keep], kw[keep], g[keep]
        ),
    }
    path = args.out_dir / f"exploratory_e5_{man['content_hash']}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps(out["sensitivity"], indent=2))
    for c, v in out["templates"]["classes"].items():
        print(c, "best gold rank", v["best_gold_rank"])


if __name__ == "__main__":
    main()
