"""EXPLORATORY follow-up to E1 (not pre-registered; see docs/experiments.md §9).

E1 found the log-linear baseline B1 beating HGB on the primary endpoints. This script asks why,
on the same frozen dataset and the same LOGO splits:

1. Per held-out design group: MAE of B1 and HGB, and whether the group's targets lie outside
   the range seen in training (trees cannot predict beyond the training range of the target).
2. A residual hybrid (B1, then HGB on B1's residuals). This is a *candidate* hypothesis for a
   future pre-registered experiment on new data; a number from it here is not evidence.

HGB uses the fixed E3 parameters (no inner selection) to keep this cheap.

Usage: python scripts/exploratory_e1.py --data data/d1/d1_v1.parquet
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from siliconai.data.dataset import content_hash, feature_columns
from siliconai.runtime_intelligence.models import make_model
from siliconai.runtime_intelligence.predict import DEFAULT_PARAMS

TARGETS = ("y__route__ln_wall", "y__total__ln_wall")
HORIZON = "h_synth"


class Hybrid:
    """B1 log-linear fit, then HGB on its residuals."""

    def __init__(self, seed: int = 0) -> None:
        self.base = make_model("b1")
        self.resid = make_model("hgb", seed=seed, **DEFAULT_PARAMS)

    def fit(self, x: pd.DataFrame, y: np.ndarray) -> Hybrid:
        self.base.fit(x, y)
        self.resid.fit(x, y - self.base.predict(x))
        return self

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return self.base.predict(x) + self.resid.predict(x)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=Path("experiments"))
    args = parser.parse_args()
    df = pd.read_parquet(args.data)
    out: dict = {"exploratory": True, "dataset_hash": content_hash(df), "targets": {}}
    for target in TARGETS:
        rows = df[df[target].notna()].reset_index(drop=True)
        feats = feature_columns(rows, HORIZON)
        x, y = rows[feats], rows[target].to_numpy(float)
        g = rows["meta__design_group"].to_numpy()
        preds = {k: np.full(len(y), np.nan) for k in ("b1", "hgb", "hybrid")}
        per_group = {}
        for grp in np.unique(g):
            te = g == grp
            models = {
                "b1": make_model("b1"),
                "hgb": make_model("hgb", **DEFAULT_PARAMS),
                "hybrid": Hybrid(),
            }
            for k, m in models.items():
                preds[k][te] = m.fit(x[~te], y[~te]).predict(x[te])
            lo, hi = y[~te].min(), y[~te].max()
            per_group[str(grp)] = {
                "n": int(te.sum()),
                "share_outside_train_range": float(np.mean((y[te] < lo) | (y[te] > hi))),
                **{f"mae_{k}": float(np.mean(np.abs(preds[k][te] - y[te]))) for k in preds},
            }
        outside = np.array([per_group[str(v)]["share_outside_train_range"] > 0 for v in g])
        out["targets"][target] = {
            "mae": {k: float(np.mean(np.abs(p - y))) for k, p in preds.items()},
            "mae_rows_in_groups_with_out_of_range_targets": {
                k: float(np.mean(np.abs(p - y)[outside])) for k, p in preds.items()
            },
            "mae_other_rows": {
                k: float(np.mean(np.abs(p - y)[~outside])) for k, p in preds.items()
            },
            "n_rows_in_out_of_range_groups": int(outside.sum()),
            "per_group": per_group,
        }
    path = args.out_dir / f"exploratory_e1_{out['dataset_hash']}.json"
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps({t: v["mae"] for t, v in out["targets"].items()}, indent=2))
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
