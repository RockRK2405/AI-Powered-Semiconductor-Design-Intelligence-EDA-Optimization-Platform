# SiliconAI — Master Plan

*AI-Powered Semiconductor Design Intelligence & EDA Optimization Platform*

**Status:** Phase 0 (research & strategy) complete, first pass. Awaiting review of the
strategy. **No platform code exists yet.**
Research package: [`research/`](research/) · Architecture: [`ARCHITECTURE.md`](ARCHITECTURE.md) ·
Decisions: [`DECISIONS.md`](DECISIONS.md) · Backlog: [`TODO.md`](TODO.md)

---

## 1. Vision

An intelligence layer over an **open-source** RTL-to-GDS flow. It predicts what a run will
cost and how it will turn out, *with calibrated uncertainty*. It diagnoses failed runs with
evidence from the logs, prioritizes verification and turns all of this into grounded
engineering recommendations.

## 2. Problem statement

Design teams spend large amounts of compute and engineer time on EDA runs whose cost
and outcome are only known after they finish. Failures are diagnosed by hand-reading
long logs. Published ML-for-EDA work mostly predicts **quality of results** (area,
timing, congestion) one stage at a time. It rarely addresses **flow cost**
(runtime, memory) and rarely quantifies **how confident** a prediction is on a design the model has
never seen (see `research/01`, §4 and §8).

## 3. Target users and use cases

| User | Use case |
|---|---|
| Physical design / flow engineer | "How long will placement and routing take on this config, and how much memory? Is this run going to fail timing?" |
| Verification engineer | "Which regression tests should run first after this change?" |
| CAD / infra engineer | "Why did last night's runs fail? Which failures are new?" |
| Student / researcher (you) | A reproducible ML-for-EDA testbed with honest evaluation |

## 4. Research findings (summary; details in `research/01`, `research/02`)

- RTL→PPA (SNS, MasterRTL) and congestion/timing prediction (RouteNet, timing GNNs) are
  **mature**. We use them as context and baselines, not as novelty.
- Open flow-metrics infrastructure exists (METRICS2.1, AutoTuner, EDALearn, EDA-schema).
- **Per-stage runtime and memory prediction** for open flows appears only as a side component
  of larger systems (IICPilot) or for proprietary FPGA tools.
- **Conformal / calibrated uncertainty** for EDA prediction: only one adjacent example
  (post-silicon Vmin) was found.
- EDA log diagnosis is **LLM-first**, with no public labelled open-EDA failure corpus found.

## 5. Research gaps and proposed novelty (details in `research/03`, `research/04`)

**Primary contribution (proposed):** *uncertainty-aware, cross-stage prediction of open
RTL-to-GDS flow cost (per-stage runtime, peak memory) and outcome risk, evaluated on
unseen designs.* Hypotheses H1–H4.

**Supporting contribution:** fault-injected, labelled open-EDA log corpus with
evidence-linked classical diagnosis (H5).

Both are **candidate** claims pending the systematic literature check (TODO P0-R1/R2).

## 6. Architecture (summary; full version in `ARCHITECTURE.md`)

A modular monolith in Python: `ingestion → features → model services → decision engine →
API/dashboard/copilot`. A flow runner produces all data. A SQLite run registry and Parquet
datasets are the single source of truth.

## 7. Technology stack (justified in `research/06`)

Python · pandas/NumPy/PyArrow · scikit-learn · XGBoost · hand-written conformal ·
SHAP (later) · Yosys/ABC · OpenROAD/ORFS (incl. OpenSTA) · Icarus/Verilator · pyslang ·
Drain · SQLite · pydantic · Streamlit → FastAPI · pytest/ruff · GitHub Actions ·
Docker (when available). Deferred: MLflow, PostgreSQL, FAISS, LLM, PyTorch.

## 8. Data strategy (details in `research/05`)

Real tool outputs from **our own scripted runs** (D1 flow runs, D2 fault-injected logs,
D3 RTL features, D4 simulated mutation histories). Design sources come from ORFS designs plus
parameterized generators (labelled `design_origin`). External datasets (EDALearn,
EDA-schema) are inspected for augmentation. Every artifact is versioned with a manifest.

## 9. ML strategy

| Task | Targets | Baselines | Models | Metrics | Split |
|---|---|---|---|---|---|
| Stage runtime | log(wall seconds) per stage | per-stage median; log-linear on cell count | Ridge, RF, XGBoost (+ quantile) | MAE(log), MAPE, R², underestimation rate | GroupKFold by design group |
| Peak memory | log(peak RSS) per stage | same | same | same | same |
| Progressive (cross-stage) | downstream runtime/QoR at horizon *h* | horizon-0 model | XGBoost per horizon | Error vs. *h*, interval width vs. *h* | same |
| Uncertainty | intervals for the above | — | split-conformal, CQR, Mondrian, OOD-gated | coverage ± CI, width, risk–coverage | random vs. leave-design-out |
| Outcome risk | WNS<0, DRC>0, run failure | prior rate; logistic on utilization | Logistic, XGBoost | PR-AUC, ROC-AUC, Brier, calibration | GroupKFold |
| Log diagnosis | failure class | keyword/regex rules | TF-IDF/template counts + LogReg/LinearSVC/XGBoost | macro-F1, top-3 evidence precision | design- and variant-held-out |
| Log anomaly | novel failure | — | IsolationForest / template-rarity | AUROC | held-out classes |
| RTL→PPA | cell count, area, critical-path delay | linear on Yosys pre-map stats | RF, XGBoost | MAE, R², MAPE | GroupKFold |
| Test prioritization | P(fail) per test | random, historical fail rate, shortest-first | LogReg, XGBoost ranker | APFD, APFDc | held-out commits |

Rigour checklist (applies to all): fixed seeds, dataset hash in every experiment record,
leakage unit tests, duplicate-design grouping, error analysis by design size and family,
and paired-bootstrap CIs for model comparisons. **No metric is reported unless it was
produced by a script in the repo.**

## 10. EDA integration strategy

1. Yosys stand-alone (apt) for synthesis-level features: fast, available now.
2. OpenROAD via ORFS (route decided in Phase 1, `research/06`) for full-flow data.
3. Subprocess wrapper: no shell, argument lists, timeouts, resource limits, captured
   logs, `/usr/bin/time -v` for peak RSS. Tool versions are recorded per run.
4. METRICS2.1 JSON parsing is the canonical metric source; log scraping is the fallback.

## 11. Evaluation strategy

- Primary experiments E1–E5 map to H1–H5 (`research/04`). Each has a pre-written protocol
  in `docs/experiments.md` (created in Phase 2) **before** results are seen.
- Report negative results.
- Runtime noise floor measured from repeated runs. No claimed error below it.

## 12. Development phases and milestones

| Phase | Goal | Key deliverables | Acceptance criteria | Est. effort* |
|---|---|---|---|---|
| **0** | Research & strategy | `research/01–08`, this plan | Reviewed and approved by you | done (first pass) |
| **1** | Foundation & toolchain | package skeleton, config, logging, SQLite registry, safe subprocess runner, CI; **OpenROAD/ORFS working**; pilot of ~20 runs with timing/memory capture | `pytest` green in CI; one ORFS design runs end-to-end with metrics + peak RSS stored; pilot cost measured | 1.5–2 wk |
| **2** | Data engine + Runtime intelligence | sweep runner (resumable), D1 v1 dataset, baselines, GBM, conformal, progressive models, minimal Streamlit page | E1–E4 executed with reported numbers; leakage tests pass | 3–4 wk |
| **3** | Log intelligence | fault injectors, D2 corpus, Drain parser, classifier, anomaly detector, evidence lines | E5 executed; per-class F1 reported | 2–3 wk |
| **4** | RTL intelligence | pyslang + Yosys feature extractor, Verilator lint gate, validation on hand-counted designs | Feature unit tests pass on ≥5 hand-checked designs | 1.5 wk |
| **5** | PPA baseline | synthesis-level PPA models + SHAP | Leave-design-out MAE/R² vs. linear baseline | 1.5 wk |
| **6** | Verification intelligence | mutation harness, D4, ranker | APFD vs. baselines on held-out commits | 2–3 wk |
| **7** | Physical-design risk | design-level risk classifiers from D1 | PR-AUC, calibration | 1 wk |
| **8** | Decision engine | risk aggregation, resource recommendations, abstention policy | Offline regret / simulated scheduling on held-out runs | 1.5 wk |
| **9** | Copilot | evidence-tagged tool-calling assistant over the DB | Citation precision on a gold question set | 2 wk |
| **10** | Unified app | FastAPI + Streamlit pages, uploads, history | E2E test: upload RTL → prediction with interval → report | 2 wk |
| **11** | Deployment & validation | Docker, CI, docs, demo, interview prep | Fresh-clone reproduction of a headline experiment | 1.5 wk |

\* Calendar estimates at roughly 15–20 h/week. Total ~20–26 weeks for the full scope. A
**credible portfolio cut** (Phases 1–3 + minimal dashboard) takes ~7–9 weeks.

## 13. Risks (top items; full register in `ARCHITECTURE.md` §8)

| Risk | Impact | Mitigation |
|---|---|---|
| OpenROAD can't be installed here | Blocks D1 | Source build / prebuilt / your machine (`research/06`) |
| Too few unique designs | Wide CIs, weak generalization | Generators, report CIs, honest scope |
| Runtime label noise and concurrency effects | Misleading accuracy | Fixed concurrency, repeats, noise floor |
| Hidden prior work | Novelty claim weakens | Systematic search before any claim |
| Scope creep (8 modules) | Nothing finished | Phase gates; portfolio cut after Phase 3 |
| LLM cost / hallucination | Copilot unreliable | Last phase; structured evidence tags |

## 14. Success criteria

- Every reported number is reproducible from a script and a dataset hash.
- H1–H5 each have a protocol, a result (positive or negative) and a limitations paragraph.
- A fresh clone can regenerate a small version of D1 and rerun E1 via one command.
- You can explain every module, decision and limitation without notes (`interview_prep/`).
