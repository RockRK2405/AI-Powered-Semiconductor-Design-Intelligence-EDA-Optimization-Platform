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
- **Amended by ADR-015:** a timing line that belongs to a nested sub-step is subtracted, not added.

## ADR-012 — scikit-learn HistGradientBoosting instead of XGBoost
- **Status:** Accepted (Phase 2, 2026-11-24).
- **Context:** ADR-005 chose gradient-boosted trees; D1 has hundreds of rows, not millions.
- **Alternatives:** XGBoost, LightGBM.
- **Choice:** `sklearn.ensemble.HistGradientBoostingRegressor` (native NaN handling, quantile loss
  for CQR). No extra dependency.
- **Trade-offs:** fewer tuning knobs; XGBoost can be added as a cross-check if HGB looks limiting.

## ADR-013 — Generated designs are bind-mounted read-only into the ORFS image
- **Status:** Accepted (Phase 2).
- **Context:** ORFS expects designs under `flow/designs/<platform>/<name>/` inside the image.
- **Choice:** `rtlgen` writes `config.mk` + SDC + RTL on the host. The run mounts that one
  directory read-only at its ORFS path. Only `sai_*` names may be mounted (never shadows a
  bundled design), and only plain absolute paths (no `--mount` syntax injection).
- **Trade-offs:** v1 supports nangate45 only, reusing gcd's fine power grid for small blocks.

## ADR-014 — Collection in ≤ 2 h chunks; committed JSONL is the durable registry
- **Status:** Accepted (Phase 2).
- **Context:** this container stops background jobs (dockerd included) after 2 h and is
  reclaimed when idle. SQLite in the git-ignored workspace is not durable.
- **Choice:** each chunk restarts dockerd, runs a budgeted `siliconai sweep`, then
  `siliconai export` writes sorted JSONL to `data/d1/registry/` and the chunk's ORFS logs to
  `data/d1/logs/<chunk>.tar.gz`, and both are committed. `siliconai import` restores the registry
  in a fresh container. Runs whose labels were contaminated are removed with `siliconai forget`,
  and parser fixes are applied with `siliconai reparse`; both append to `data/d1/corrections.jsonl`.
- **Trade-offs:** git holds data (a few MB). This is acceptable at this scale; move to object storage if it grows.

## ADR-015 — Nested sub-steps, clean re-runs, and correcting recorded data
- **Status:** Accepted (Phase 2, 2026-11-24). Found while collecting D1 chunk c04.
- **Context:** three defects surfaced while collecting D1.
  - **(1) Nested timing counted twice.** ORFS runs the logic-equivalence check inside CTS
    (`4_rsz_lec` in `4_1_cts`) and inside the final report (`6_final_lec` in `6_report`). It
    echoes the check's `Elapsed time` line into the parent log, and the parent's own line already
    includes that time. Summing per ADR-011 counted it twice, inflating cts and finish labels by up
    to 2.4× on large designs. A survey of all 223 multi-line logs found only this pattern.
  - **(2) A killed run leaves `5_2_route.tmp.log`.** The schema correctly rejected the step name,
    which crashed chunk c04 before the run was recorded.
  - **(3) Re-runs reused stale outputs.** Nothing cleared a variant's directories first, so a
    re-run let ORFS `make` reuse an earlier attempt's results. One run (`aes_gf180_44136fa3_r0`,
    left half-done by an interrupted probe) was recorded as a 29 s success with 591 s of stale
    step logs.
- **Choice:**
  - A step whose (single) timing line appears in another step's log is nested in it. The parent
    keeps its own lines minus the nested ones, so steps add up to the flow time exactly. If the
    subtraction would go negative, the parser warns and sums instead.
  - `X.tmp.log` is recorded as step X, unfinished (no timing). Other unrecognized names are skipped.
  - If step records are rejected, the run is still recorded and the error is logged.
  - Before each run, the sweep deletes that variant's `results/`, `objects/`, `logs/` and
    `reports/`.
  - Recorded data is corrected only by reproducible commands that append to a corrections log:
    `siliconai reparse` re-parses runs from their original logs (run records untouched), and
    `siliconai forget` removes a contaminated run so it is re-collected.
- **Verification:** after the correction, Σ step time ≤ container wall time for every run (max
  ratio 0.995; it was up to 1.12, or 20× for the stale run). Only the cts and finish labels changed
  (median ×0.79 and ×0.89). The Phase 1 report was regenerated, and its corrected numbers are
  marked in PROGRESS.md. No model had been trained, and D1 had not been frozen.
- **Trade-offs:** nesting is detected from identical timing lines (wall, CPU and peak memory to
  the recorded precision), not from ORFS internals. An exact coincidence between unrelated steps is
  negligible, and the negative-remainder guard catches implausible cases.


## ADR-016 — Drain template mining implemented in the repository
- **Status:** Accepted (Phase 3, 2026-11-25).
- **Context:** E5 needs log templates learned from training runs only, with a `match` that never
  learns from test runs, so a held-out design cannot leak into the template set. Installing the
  `drain3` package was refused by this environment's permission policy.
- **Choice:** `log_intelligence/drain.py` is a small, tested implementation of Drain (fixed-depth
  prefix tree, token-similarity threshold). Parameters are depth 4 and similarity 0.5, fixed in the protocol.
  - It masks paths, quoted strings, hex and stand-alone numbers before parsing. Message codes such as `GPL-0301` and units such as `um^2` are kept.
  - `add`/`fit` learn; `match` only looks up.
  - Line length and token count are capped, because logs are untrusted.
- **Consequence found in E5 (post hoc):** masking every stand-alone number also erases make's exit
  code, so `Error 247` (killed for memory) and `Error 2` become one template. A later version
  should keep exit codes and message IDs (TODO P3-13). Under the pre-registered protocol the masking
  was not changed after seeing D2.
- **Trade-offs:** about 150 lines to maintain, and no upstream fixes. It is easy to audit, and its behaviour is fixed by tests.

## ADR-017 — Faults are injected as read-only overlay designs; RTL faults skipped on the slang frontend
- **Status:** Accepted (Phase 3, 2026-11-25).
- **Context:** fault injection must not modify the ORFS image or the original design. It must be
  reproducible from the repository, and every faulted run must be tied to a known label decided before it runs.
- **Choice:**
  - Each faulted design is a directory `sai_fi_<name>_<hash>`. It holds the base `config.mk` followed by an injection block, plus mutated copies of RTL/SDC where the fault needs them. It is bind-mounted read-only next to the original design (as for generated designs, ADR-013).
  - The directory name hashes the content, so a run ID identifies its exact fault.
  - Flow variables that the platform config reassigns are injected with make's `override export`, for example the routing layers on nangate45.
  - On the two bases whose ORFS config uses the slang frontend, the 9 RTL-frontend faults are skipped. In this image slang prints the same single line ("Design elaboration failed") for all of them, so no log-based method could separate them, and including them would only add noise labels.
- **Known defect (post hoc, results_d2 §3):** copying a mutated RTL file into the overlay breaks
  a *relative* `` `include `` in the original source directory. On aes this turned 7 syntax and
  elaboration injections into missing-include failures. Fix before reuse: put the original source directory
  on the include path (TODO P3-11).
- **Trade-offs:**
  - Injected faults are cleaner than real failures.
  - Some injections do not manifest on every design (25 of 320 on D2). They are reported, not relabelled.
