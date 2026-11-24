# Architecture Decision Records

Status values: **Proposed** (awaiting your review) · **Accepted** · **Superseded**.

---

## ADR-001 — One repository, modular monolith
- **Status:** Accepted (by your direction to merge four projects into one).
- **Context:** four separate projects would duplicate data plumbing and fail to show integration.
- **Alternatives:** separate repos; microservices.
- **Choice:** one Python package with internal module boundaries.
- **Rationale:** shared run registry and features; simplest deployment.
- **Trade-offs:** module boundaries must be enforced by discipline and tests, not by the network.

## ADR-002 — Data engine before models; reorder Phase 2 as "Data engine + Runtime"
- **Status:** Proposed.
- **Context:** every module needs real tool outputs. Runtime/memory labels exist only if we run
  the flow ourselves.
- **Alternatives:** start from external datasets (CircuitNet, OpenABC-D); start from synthetic data.
- **Choice:** Phase 1 brings up the toolchain and a pilot. Phase 2 builds the sweep runner and the
  runtime models on the data it produces.
- **Rationale:** external datasets don't confirm runtime/memory labels; synthetic labels are
  not acceptable for headline results.
- **Trade-offs:** compute-bound; first ML results come later than with a downloaded dataset.

## ADR-003 — Primary research contribution: uncertainty-aware cross-stage flow-cost prediction
- **Status:** Proposed — **needs your approval**.
- **Context:** `research/04` scoring. RTL→PPA and congestion are mature; flow cost + UQ are thin.
- **Alternatives:** RTL→PPA as headline; LLM copilot as headline; verification ranking as headline.
- **Choice:** H1–H4 as the primary contribution; log corpus (H5) as the supporting contribution.
- **Rationale:** feasible on CPU, measurable, reproducible, defensible.
- **Trade-offs:** less "flashy" than an LLM headline; the novelty depends on the systematic search.

## ADR-004 — SQLite + Parquet; defer PostgreSQL
- **Status:** Proposed.
- **Context:** single-user, write-light workload.
- **Choice:** SQLite for the registry/metadata; Parquet for analytic datasets.
- **Trade-offs:** no concurrent writers. Migrate (SQLAlchemy Core keeps this cheap) if Phase 10 needs it.

## ADR-005 — Tabular gradient-boosted trees over GNNs
- **Status:** Proposed.
- **Context:** no GPU; hundreds to low thousands of rows; tabular stage metrics.
- **Choice:** linear baselines → RF → XGBoost (+ quantile). No PyTorch in the plan.
- **Trade-offs:** cannot learn netlist structure directly. This is acceptable because RTL→PPA SOTA
  is not our claim.

## ADR-006 — Experiment tracking: JSON records first, MLflow later if justified
- **Status:** Proposed.
- **Choice:** each experiment writes `experiments/<id>.json` (params, dataset hash, git SHA,
  metrics, seed). Adopt MLflow when comparisons become painful (more than about 50 runs).
- **Trade-offs:** no UI at first; the Streamlit page can render the JSON.

## ADR-007 — Hand-implemented conformal prediction
- **Status:** Proposed.
- **Choice:** implement split-conformal, CQR and Mondrian ourselves, with property tests that
  check coverage on synthetic data. MAPIE stays an optional cross-check.
- **Rationale:** about 100 lines of code; deep understanding for interviews; few dependencies.

## ADR-008 — Log diagnosis: classical pipeline first, LLM optional
- **Status:** Proposed.
- **Choice:** Drain templates → features → linear/GBM classifier + anomaly detector + evidence lines.
  An LLM may later *phrase* explanations, but only from the extracted evidence.
- **Rationale:** measurable (F1, evidence precision), cheap, no hallucinated causes.

## ADR-009 — Labels only from real tools; synthetic elements are tagged
- **Status:** Accepted (project rule).
- **Choice:** generated RTL and injected faults are allowed and are recorded as `design_origin`
  and `injected_fault` columns. All metrics and labels come from actual tool runs.

## ADR-010 — Route to OpenROAD
- **Status:** Open (decided in Phase 1 after trials; see `research/06`).
