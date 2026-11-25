"""SiliconAI dashboard (Phase 2, minimal; TODO P2-09).

Run:  streamlit run dashboard/app.py
Data: the committed registry snapshot (data/d1/registry/*.jsonl), loaded into an in-memory
SQLite registry. Read-only, no uploads, nothing executed (uploads arrive in Phase 10).
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from siliconai.data.dataset import STAGES, build_table
from siliconai.data.exchange import import_jsonl
from siliconai.data.registry import Registry
from siliconai.runtime_intelligence.predict import predict_unseen

DATA_DIR = Path(os.environ.get("SILICONAI_DASHBOARD_DATA", "data/d1/registry"))

st.set_page_config(page_title="SiliconAI", layout="wide")


@st.cache_data(show_spinner="Loading run registry…")
def load(data_dir: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    with tempfile.TemporaryDirectory() as tmp, Registry(Path(tmp) / "r.sqlite") as reg:
        import_jsonl(reg, Path(data_dir))
        runs = pd.DataFrame([dict(r) for r in reg.runs()])
        designs = pd.DataFrame([dict(d) for d in reg.designs()])
        stages = pd.DataFrame([dict(s) for s in reg.stage_summary()])
        table = build_table(reg)
    runs = runs.merge(designs, on="design_id")
    return runs, stages, table


@st.cache_data(show_spinner="Training on the other designs and calibrating…")
def cached_prediction(run_id: str, target: str, _table: pd.DataFrame) -> dict:
    return predict_unseen(_table, run_id, target)


def fmt_seconds(s: float) -> str:
    return f"{s:,.0f} s" if s < 600 else f"{s / 60:,.1f} min"


st.title("SiliconAI · open-flow runtime intelligence")
st.caption(
    "Real OpenROAD-flow-scripts runs on one 4-vCPU VM, pinned ORFS image. "
    "Phase 2 prototype: numbers are from the run registry; no claims beyond it."
)
if not (DATA_DIR / "runs.jsonl").exists():
    st.error(f"No registry snapshot at {DATA_DIR}. Run `siliconai export --out {DATA_DIR}`.")
    st.stop()

runs, stages, table = load(str(DATA_DIR))
tab_runs, tab_predict = st.tabs(["Runs", "Predict an unseen design"])

with tab_runs:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runs", len(runs))
    c2.metric("Successful", int((runs["status"] == "success").sum()))
    c3.metric("Designs", runs["design_id"].nunique())
    c4.metric("Design groups", runs["design_group"].nunique())

    plats = sorted(runs["platform"].unique())
    pick = st.multiselect("Platform", plats, default=plats)
    view = runs[runs["platform"].isin(pick)][
        ["run_id", "design_id", "platform", "origin", "design_group", "status", "wall_s"]
    ].sort_values("run_id")
    st.dataframe(view, hide_index=True, use_container_width=True)

    run_id = st.selectbox("Per-stage cost of run", view["run_id"].tolist())
    one = stages[stages["run_id"] == run_id].set_index("stage")
    one = one.reindex([s for s in (*STAGES, "other") if s in one.index])
    left, right = st.columns([3, 2])
    left.bar_chart(one["wall_s"], y_label="wall time (s)", x_label="stage")
    right.dataframe(
        one[["wall_s", "cpu_s", "peak_rss_mb"]]
        .round(1)
        .rename(columns={"wall_s": "wall s", "cpu_s": "CPU s", "peak_rss_mb": "peak MB"}),
        use_container_width=True,
    )

with tab_predict:
    st.write(
        "Pick a run. The model is trained **without that run's design group** (same RTL on any "
        "platform, or the same generator family), using only information available after "
        "synthesis. The 90% interval uses group-aware conformal calibration."
    )
    targets = {"Total flow wall time": "y__total__ln_wall", "Route wall time": "y__route__ln_wall"}
    label = st.radio("Target", list(targets), horizontal=True)
    target = targets[label]
    candidates = table.loc[table[target].notna(), "meta__run_id"].tolist()
    if table["meta__design_group"].nunique() < 3 or not candidates:
        st.info("Not enough design groups collected yet.")
        st.stop()
    run_choice = st.selectbox("Run", candidates)
    try:
        res = cached_prediction(run_choice, target, table)
    except ValueError as exc:
        st.warning(str(exc))
        st.stop()
    a, b, c = st.columns(3)
    a.metric("Predicted", fmt_seconds(res["point"]))
    b.metric("90% interval", f"{fmt_seconds(res['lo'])} – {fmt_seconds(res['hi'])}")
    c.metric(
        "Actual (measured)",
        fmt_seconds(res["actual"]),
        delta="inside interval" if res["covered"] else "outside interval",
        delta_color="off" if res["covered"] else "inverse",
    )
    st.caption(
        f"Held-out group: `{res['held_out_group']}` · trained on {res['train_groups']} other "
        "groups · horizon: after synthesis. Coverage across all runs is evaluated in E3 "
        "(docs/experiments.md); a single run inside or outside its interval says little."
    )
    st.info(
        "No runtime model has yet been shown to beat a simple log-linear baseline (cells + "
        "platform) on unseen designs: it won on D1 v1, and on D1 v2 no difference was "
        "significant. Group-aware 90% intervals stay close to their coverage. See "
        "docs/results_d1_v1.md and docs/results_d1_v2.md."
    )
