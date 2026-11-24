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
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Context:** every module needs real tool outputs. Runtime/memory labels exist only if we run
  the flow ourselves.
- **Alternatives:** start from external datasets (CircuitNet, OpenABC-D); start from synthetic data.
- **Choice:** Phase 1 brings up the toolchain and a pilot. Phase 2 builds the sweep runner and the
  runtime models on the data it produces.
- **Rationale:** external datasets don't confirm runtime/memory labels; synthetic labels are
  not acceptable for headline results.
- **Trade-offs:** compute-bound; first ML results come later than with a downloaded dataset.

## ADR-003 — Primary research contribution: uncertainty-aware cross-stage flow-cost prediction
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Context:** `research/04` scoring. RTL→PPA and congestion are mature; flow cost + UQ are thin.
- **Alternatives:** RTL→PPA as headline; LLM copilot as headline; verification ranking as headline.
- **Choice:** H1–H4 as the primary contribution; log corpus (H5) as the supporting contribution.
- **Rationale:** feasible on CPU, measurable, reproducible, defensible.
- **Trade-offs:** less "flashy" than an LLM headline; the novelty depends on the systematic search.

## ADR-004 — SQLite + Parquet; defer PostgreSQL
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Context:** single-user, write-light workload.
- **Choice:** SQLite for the registry/metadata; Parquet for analytic datasets.
- **Trade-offs:** no concurrent writers. Migrate (SQLAlchemy Core keeps this cheap) if Phase 10 needs it.

## ADR-005 — Tabular gradient-boosted trees over GNNs
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Context:** no GPU; hundreds to low thousands of rows; tabular stage metrics.
- **Choice:** linear baselines → RF → XGBoost (+ quantile). No PyTorch in the plan.
- **Trade-offs:** cannot learn netlist structure directly. This is acceptable because RTL→PPA SOTA
  is not our claim.

## ADR-006 — Experiment tracking: JSON records first, MLflow later if justified
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Choice:** each experiment writes `experiments/<id>.json` (params, dataset hash, git SHA,
  metrics, seed). Adopt MLflow when comparisons become painful (more than about 50 runs).
- **Trade-offs:** no UI at first; the Streamlit page can render the JSON.

## ADR-007 — Hand-implemented conformal prediction
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Choice:** implement split-conformal, CQR and Mondrian ourselves, with property tests that
  check coverage on synthetic data. MAPIE stays an optional cross-check.
- **Rationale:** about 100 lines of code; deep understanding for interviews; few dependencies.

## ADR-008 — Log diagnosis: classical pipeline first, LLM optional
- **Status:** Accepted (approved 2026-11-24, end of Phase 0).
- **Choice:** Drain templates → features → linear/GBM classifier + anomaly detector + evidence lines.
  An LLM may later *phrase* explanations, but only from the extracted evidence.
- **Rationale:** measurable (F1, evidence precision), cheap, no hallucinated causes.

## ADR-009 — Labels only from real tools; synthetic elements are tagged
- **Status:** Accepted (project rule).
- **Choice:** generated RTL and injected faults are allowed and are recorded as `design_origin`
  and `injected_fault` columns. All metrics and labels come from actual tool runs.

## ADR-010 — Route to OpenROAD: official ORFS Docker image, pinned by digest
- **Status:** Accepted (Phase 1, 2026-11-24).
- **Context:** none of OpenROAD/OpenSTA is packaged in Ubuntu apt; the GitHub release API is not
  reachable from this cloud session; a source build is estimated at ~1 h.
- **Alternatives tried / considered:** (a) prebuilt release binaries: blocked here; (b) source build:
  slow, and pins nothing beyond our own build; (c) **Docker image `openroad/orfs`**; (d) OpenLane 2
  (needs Nix or Docker anyway); (e) your own machine.
- **Choice:** (c). Image `openroad/orfs@sha256:620c13d94b80290ccaa6d6d7fbaef9632bdb06ba7e6aedb88da845159b840c09`
  (built 2026-11-23; contains Yosys 0.68+post, OpenROAD, KLayout). Every run records this digest.
- **Rationale:** one artifact pins every tool version; the same image runs on any Linux/WSL2 machine,
  so data generation can move to your machine later without changing tool versions.
- **Trade-offs / caveats:** in this cloud container the Docker daemon is not started by default; we
  start `dockerd` manually as a background process. The `openroad -version` string inside the
  image reports `unknown`, so the **image digest is the version of record**. A `latest` tag moves:
  datasets must only mix runs with the same digest (enforced in Phase 2 dataset build).

## ADR-011 — Runtime/memory labels come from ORFS's in-container per-step measurement
- **Status:** Accepted (Phase 1).
- **Context:** wrapping `docker run` with GNU time would measure the Docker CLI (≈32 MB), not the
  tools. ORFS's `scripts/run_command.py` already appends, per command, `Elapsed time … CPU time …
  Peak memory …KB` measured inside the container.
- **Choice:** parse those lines per step (`eda/orfs_parse.py`); sum wall/CPU over commands in a
  step, take max peak memory. GNU time (`eda/runner.py`) is used for tools we run directly on the host.
- **Trade-offs:** we depend on ORFS's log format; a regex unit test on real log excerpts guards it,
  and a step with no timing line is stored with NULL timing rather than guessed.
