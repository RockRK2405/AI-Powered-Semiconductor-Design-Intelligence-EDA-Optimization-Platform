# Progress Log

## Phase 0 — Research & Strategy

- **Status:** Complete. Strategy approved by you on 2026-11-24 (ADR-002…008 accepted).
- **Completed tasks**
  - Inspected workspace. The repository was renamed from `AI-Driven-RTL-Optimization-PPA-Prediction-Framework`
    to `AI-Powered-Semiconductor-Design-Intelligence-EDA-Optimization-Platform`; both were empty.
  - Checked the environment: Python 3.13.18, 4 vCPU, 15 GB RAM, no GPU, Docker CLI without a daemon,
    no EDA tools installed. apt offers yosys 0.33, iverilog 12.0, verilator 5.020; no opensta.
    The scikit-learn 1.9.1 wheel for cp313 is available.
  - Web research: about 35 verified sources across ML-for-EDA surveys, datasets, RTL→PPA,
    physical-design prediction, flow tuning, runtime prediction, logs, verification, LLMs and UQ.
  - Wrote `research/01–08`, `PLAN.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `TODO.md`, `README.md`.
- **Implemented features:** none (by design: Phase 0 has no implementation).
- **Tests executed:** none (no code).
- **Results:** a recommended contribution (ADR-003) and hypotheses H1–H5.
- **Issues / limitations**
  - Papers were not read in full; claims are abstract-level and marked as such.
  - The absence of prior work on G1/G4 is a search result, not proof. A systematic
    proceedings search is still owed (TODO P0-R1…R5).
  - OpenROAD availability is unresolved (TODO P1-03).
- **Next:** Phase 1 (done, see below).

## Phase 1 — Foundation & toolchain

- **Status:** Complete (2026-11-24). **Awaiting your approval to start Phase 2.**
- **Implemented features**
  - Package skeleton, config from env, logging, CI (ruff + unit tests on Python 3.11/3.13).
  - `eda/runner.py`: shell-free tool runner (argv only, env allowlist, timeout that kills the
    process group, GNU-time peak RSS, optional RLIMIT_AS).
  - `eda/orfs.py`: ORFS in a digest-pinned Docker image (ADR-010); allowlisted flow variables and
    regex-validated values; `--network none`; inner `timeout` plus `docker kill` backstop.
  - `eda/orfs_parse.py`: per-step wall/CPU/peak-memory from ORFS's in-container timing lines
    (ADR-011) and METRICS2.1 JSON; size caps; NaN/inf dropped.
  - `data/schemas.py` + `data/registry.py`: pydantic records and a SQLite registry
    (designs, runs, steps); deterministic run IDs make runs resumable.
  - `siliconai` CLI (`doctor`, `orfs-run`, `runs`); `scripts/pilot_phase1.sh`, `scripts/pilot_report.py`.
- **Tests:** 52 passed (`pytest -q`), including 2 end-to-end tests that run the real ORFS flow
  (marker `eda`). `ruff check` and `ruff format --check` clean.
- **Toolchain:** ORFS image `openroad/orfs@sha256:620c13d9…` (Yosys 0.68+post, OpenROAD, KLayout).
  On the host: Yosys 0.33, Icarus Verilog 12, Verilator 5.020 (apt).

### Pilot results (P1-09) — measured, not estimated

Machine: this cloud container (Intel Xeon @ 2.30 GHz, 4 vCPU, 15.7 GB RAM). One run at a time
(concurrency 1). 16 runs, 4,015 s of total run time (≈ 67 min). Raw numbers:
[`data/pilot_phase1/`](data/pilot_phase1/) (`runs.csv`, `stage_summary.csv`, `report.md`).

**Cost per design (default ORFS config; flow wall time = sum of step times; peak = max over steps)**

| Design | Platform | Runs | Flow wall s | Route share | Peak memory MB |
|---|---|---|---|---|---|
| gcd | nangate45 | 3 | 32.6 (mean) | 55% | 557 |
| gcd | sky130hd | 1 | 30.3 | 62% | 450 |
| aes | nangate45 | 3 | 297.1 (mean) | 67% | 925 |
| ibex | nangate45 | 1 | 285.7 | 60% | 959 |
| jpeg | nangate45 | 1 | 820.7 | 62% | 1,856 |
| aes | sky130hd | 1 | 1,571.9 | 93% | 2,867 |

- Docker start-up, teardown and make overhead add about 7–10 s per run on top of the step times. The runtime labels
  use the step times, not the outer wall time.
- Detailed routing dominates (55–93% of flow time). The same RTL (aes) costs **5.3×** more on
  sky130hd than on nangate45, almost all in routing. So the platform is a first-order feature.
- Peak memory stayed below 3 GB, so memory is not the binding constraint on this machine; time is.

> **Correction (2026-11-24, during Phase 2):** the numbers above were first published with the
> cts and finish stages over-counted. ORFS runs the logic-equivalence check (`4_rsz_lec`,
> `6_final_lec`) *inside* the CTS and report steps and echoes its timing line into their logs, and
> the parser added that line a second time. After the parser fix the pilot registry was re-parsed
> from the original logs (`siliconai reparse`, logged in `data/pilot_phase1/corrections.jsonl`). Flow
> times dropped by 0–5% (jpeg 860.0 → 820.7 s); route time and every conclusion are unchanged.
> Details: ADR-015.

**Run-to-run noise (3 repeats of an identical configuration)**

| Design | Whole-flow CV (outer wall) | Per-stage wall-time CV (stages > 0.5 s) | Per-stage peak-memory CV |
|---|---|---|---|
| gcd nangate45 | 1.7% | 2.1–5.9% | 0.1–2.1% |
| aes nangate45 | 0.7% | 0.7–4.6% | 0.1–3.0% |

Interpretation: on this machine, labels are reproducible to within a few percent, so a model
cannot meaningfully claim per-stage errors below ~5% on short stages. Caveat: n = 3 repeats on
2 designs, within about an hour on one shared cloud VM. This is a lower bound on noise, not a
full characterization (no cross-day or cross-host repeats).

**Sweep runs that failed (6 of 16): a real finding, not a code bug**

The `aes` utilization sweep (CORE_UTILIZATION = 30 and 50, 3 repeats each) failed at floorplan in
≈ 40 s with `Error: Floorplan initialization methods are mutually exclusive, pick one.`
`designs/nangate45/aes/config.mk` fixes the floorplan with `FLOORPLAN_DEF`, so a utilization
override conflicts with it. In the image, 20 design configs fix the floorplan (`FLOORPLAN_DEF`,
`DIE_AREA` or `CORE_AREA`). Consequences:
- Phase 2's sweep spec needs a **preflight compatibility check** per design (new TODO P2-10).
- These runs stay in the registry as `failed`. They are the first *real* (not injected) failure
  logs, useful for H5, and are excluded from runtime-model training sets.
- So the pilot measured noise on **2** repeated configurations, not the planned 3.

**Constraints discovered for Phase 2**

1. **Disk:** 16 runs produced 2.8 GB of ORFS artifacts (≈ 175 MB/run, mostly `objects/` and
   `results/`); the logs are only 3.5 MB in total. The sweep runner must prune large artifacts once
   metrics are parsed (new TODO P2-11).
2. **Session limits here:** a background command can run for at most 2 h, and this container is
   reclaimed when idle. Sweeps must run in ≤ 2 h resumable chunks, with the registry exported and
   committed after each chunk, or run on a persistent machine (your decision, see below).

- **Issues / limitations**
  - All timings come from one shared cloud VM; other tenants can add noise that we don't control.
  - `openroad -version` reports `unknown` inside the image; the image digest is the version of record.
  - The pilot covered 4 ORFS designs on 2 platforms; no generated designs yet.
- **Next:** Phase 2 (data engine + runtime intelligence), gated on your approval, plus two decisions:
  the dataset machine and the license (P0-D1).

## Phase 2 — Data engine + runtime intelligence

- **Status:** Implementation and first experiments complete (2026-11-25). **Awaiting your review
  before Phase 3.** Full results: [`docs/results_d1_v1.md`](docs/results_d1_v1.md).
- **Implemented features**
  - **Sweep engine:**
    - YAML sweep specs.
    - Deterministic, resumable plans with a floorplan-compatibility preflight.
    - Budgeted ≤ 2 h chunks with a registry export after each chunk (`scripts/run_chunk.sh`).
    - Outputs of an earlier attempt are cleared before every run.
    - Large ORFS artifacts are pruned after parsing.
  - **RTL generators** (adder tree, ALU, CRC, FIFO, FSM, MAC array, multiplier), tagged `generated`.
  - **Dataset builder:**
    - Horizon-tagged features, with leakage tests.
    - Refuses mixed tool images or hosts.
    - Refuses runs whose step times exceed wall time.
  - **Models and uncertainty:** baselines B0/B1, Ridge/RF/HGB, LOGO evaluation with inner GroupKFold selection and group-bootstrap CIs; conformal methods (split, group-OOF, CQR, Mondrian); OOD scoring and selective risk.
  - **Pre-registered protocols E1–E4** ([`docs/experiments.md`](docs/experiments.md)), written before any data existed.
  - **Tooling:** `siliconai reparse`/`forget` with an append-only `corrections.jsonl`, and a minimal Streamlit dashboard.
- **Data collected (D1 v1):**
  - 186 runs (10.4 h of flow time) in chunks c01–c07.
  - 175 successful runs: 44 designs, 16 design groups, 5 platforms. Also 8 failed and 3 timeout runs.
  - Frozen as `data/d1/d1_v1.parquet`, hash `ee0aebdd56278380`.
  - Logs are archived per chunk in `data/d1/logs/`.
- **Results (pre-registered; numbers from `experiments/*.json`):**

  | Hypothesis | Verdict | Key number |
  |---|---|---|
  | H1: learned model beats baselines on unseen designs | **Not supported**, and reversed on the primary endpoints | Route MAE (ln): B1 0.397 vs HGB 0.586; total: 0.327 vs 0.474 |
  | H2: observing more stages improves downstream prediction | **Not supported** | Route, h_place − h_synth: −0.076 [−0.191, +0.074] |
  | H3: naive conformal fails on unseen designs; group-aware restores coverage | **Supported** | Naive 53–57% under LOGO; group-OOF 92–94% |
  | H4: OOD abstention reduces large errors | **Not supported** | CIs include 0 at 80% and 90% coverage |

  - Secondary: HGB beats B1 on place/cts/finish peak memory (CIs exclude 0).
  - Exploratory (not pre-registered): HGB's loss comes from sparse platform × size coverage. Outside nangate45 there are no mid-size designs.
- **Tests:** 155 passed; ruff check and format clean.
- **Issues found and fixed during Phase 2 (all logged):**
  - Nested LEC timing was double-counted, plus stale re-run outputs and unrecognized `.tmp` logs (ADR-015). Both registries were re-parsed and the Phase 1 table corrected.
  - The scikit-learn 1.9.1 HGB crash on all-missing training columns (change log in `docs/experiments.md`).
  - One container restart mid-chunk: no data lost; the post-restart runs were checked against repeats (results §1).
- **Limitations:**
  - One VM type.
  - 16 design groups, so CIs are wide.
  - Generated RTL only on nangate45.
  - `d1_ext` not collected.
  - E4's widest-interval comparison not implemented.
- **Next:**
  - Your review.
  - Proposed: before Phase 3, a short D1 v2 round. Pre-register the hybrid vs B1 vs HGB comparison, then collect generated and mid-size designs on the other four platforms (P2-16, P2-18). Alternatively, move straight to Phase 3 (log intelligence: fault injectors, the D2 failure-log corpus, E5) and treat D1 v2 as later work. Phase 2's acceptance criteria (E1–E4 executed with reported numbers; leakage tests pass) are met either way.

### D1 v2 round (your decision, 2026-11-25: option A, before Phase 3)

- **Pre-registered first.** Protocol E1b (`docs/experiments.md` §10) was committed in `8feed44`, before any D1 v2 run. It tests the residual hybrid against B1, scoring only rows new since D1 v1.
- **Generated designs on all five platforms** (P2-16). Clock periods are scaled per platform. All 8 validation runs succeeded, with final setup slack at 59–75% of the period on every platform; on nangate45 it is 66%.
- **Collection** (`sweeps/d1_v2.yaml`):
  - 186 runs in about 4–5 chunks, with no new gcd runs.
  - The stopping rule is to freeze when the sweep completes or after 5 chunks.
  - First observation: high-utilization configs without routability-driven placement can congest detailed routing on sky130hd. Example: a 2.2k-cell FSM with about 30k open violations after 6 min. Such runs are kept as genuine `timeout` outcomes.
- **Collected and frozen.** `d1_v2.yaml` completed in 5 chunks (v2c01–v2c05; v2c00 was the validation round).
  - New runs: 186, of which 179 succeeded, 3 failed and 4 timed out. Every failure and timeout is a genuine flow outcome:
    - PDN-0185 on a tiny FSM on ihp-sg13g2;
    - ORFS's own LEC check cannot load tage_update's generated SRAMs;
    - detailed-route congestion for chi_async_bridge on asap7 and a 128-state FSM on sky130hd.
  - D1 v2: `data/d1/d1_v2.parquet`, hash `3f601a94fdbaf60d`, git `f765795`. 354 rows, 18 groups. Every platform now has 16–27 rows of 1k–5k cells.
- **E1b result ([`docs/results_d1_v2.md`](docs/results_d1_v2.md)): H1b not supported.**
  - On the 179 new rows the hybrid has the lowest MAE: route 0.537 vs B1 0.673 vs HGB 0.575; total 0.430 vs 0.565 vs 0.439.
  - ΔMAE hybrid − B1: route −0.135 [−0.312, +0.062], total −0.135 [−0.311, +0.054]. Only 9 groups have new rows, and they disagree (gen_alu goes the other way).
  - Secondary 1: the D1 v1 ordering "B1 beats HGB" did not repeat. HGB − B1 is −0.098 / −0.126, with CIs that include 0.
  - Secondary 4: group-OOF intervals on new rows cover 87.7% (HGB) and 82–83% (hybrid, about 10% narrower). Every CI includes 90%.
  - Secondary 5: placement information still does not help (−0.008 [−0.097, +0.084]).
  - **Conclusion:** no runtime model has been shown to beat B1 on unseen design groups. The limit is the number of design groups, not the number of runs.

## Phase 3 — Log intelligence

- **Status:** Implementation, D2 collection and E5 complete (2026-11-25). **Awaiting your review
  before Phase 4.** Full results: [`docs/results_d2.md`](docs/results_d2.md).
- **Acceptance criteria (PLAN §12):** E5 executed, per-class F1 reported. **Met.** The hypothesis
  itself is not supported (below).
- **Implemented features** (`src/siliconai/log_intelligence/`):
  - **Fault injectors** (`faults.py`): 26 faults in 8 classes.
    - A faulted design is a read-only overlay directory mounted next to the original ORFS design. It holds the base config plus an injection block, and mutated copies of RTL/SDC (ADR-017).
    - Out-of-memory and timeout limits are scaled to each base's measured clean run. `run_orfs` gained a validated `--memory` limit.
    - Injectors that the dev probe found masked or misattributed are listed in `MASKED_FAULTS`, not used.
  - **Corpus collector** (`corpus.py`, `scripts/run_d2_chunk.sh`, `scripts/freeze_d2.py`): seeded plan, budgeted chunks, JSONL records, per-chunk log archives, and a freeze manifest with archive hashes.
  - **Log loading** (`logs.py`): step logs in flow order, then the console. Logs are untrusted input: size, line and line-count caps, symlinks skipped.
  - **Drain template miner** (`drain.py`): implemented in the repo (ADR-016). It masks paths, quoted strings, hex and numbers, but keeps message codes.
  - **Diagnosis** (`diagnose.py`, `rules.py`):
    - the keyword baseline;
    - a template + TF-IDF + logistic regression classifier with evidence lines;
    - a raw-text classifier and an SVM variant;
    - template-novelty anomaly scoring;
    - gold root-cause patterns.
  - **E5 runner** (`e5.py`, `scripts/run_e5.py`): verifies archives against the manifest and extracts them with tarfile's `data` filter, which blocks path traversal (tested).
- **Pre-registered first.** The E5 protocol (`docs/experiments.md` §11), the keyword rules and the gold patterns were committed before any D2 run was collected. They were written from the development design (gcd) only, which is never in D2.
- **Data collected (D2 v1):**
  - 333 runs (13 bases × 26 faults + clean, minus the RTL-frontend faults on slang bases) in chunks d2c01–d2c02, 3.3 h of flow time.
  - Outcomes: 295 labelled failures and timeouts, 25 masked injections (excluded, as pre-registered), 13 of 13 clean runs succeeded.
  - Frozen: `data/d2/d2_v1.manifest.json`, hash `3d6cb327b1ed3b5d`, git `50c6aca`.
- **Results (pre-registered; `experiments/e5_3d6cb327b1ed3b5d.json`):**

  | Hypothesis | Verdict | Key number |
  |---|---|---|
  | H5a: template classifier beats keyword rules on unseen designs and unseen fault variants | **Not supported, reversed** | Macro-F1 Δ: −0.102 [−0.126, −0.078] (designs); −0.450 [−0.479, −0.416] (variants). Keyword rules 0.970 |
  | H5b: its top-3 evidence contains a root-cause line more often than "last 3 error lines" | **Not supported, reversed** | 0.372 vs 0.440, Δ −0.067 [−0.093, −0.045] |

  - Secondary:
    - template novelty separates failed from clean runs with AUROC 0.81;
    - novel-class detection is weak, AUROC 0.61;
    - the keyword rule's own trigger line is a root-cause line in 95% of runs;
    - a linear SVM on the same features scores 0.918, still below the rules.
  - Exploratory (post hoc, `scripts/exploratory_e5.py`):
    - Number masking merges the OOM exit code (`Error 247`) with every `Error 2`, so the model recognises OOM and timeout by the stage the run reached. That shortcut breaks on unseen variants.
    - The top-3 distinct evidence lines are filled by progress-table rows.
- **Issues found (post hoc, logged in results §3):**
  - **Injector artefact.** On aes, 7 RTL mutations broke a relative `` `include ``, so those runs failed as missing includes. Their labels are wrong. The sensitivity check gives the same verdict (Δ −0.102 [−0.126, −0.078]).
  - **Unseen frontend.** dynamic_node uses ORFS's newer SYN frontend, whose messages neither the rules nor the model had seen. The rules say `unknown` and the model says `sdc_error` on all 7 RTL-frontend runs.
- **Tests:** 219 passed with the Docker daemon running (217 passed + 2 Docker end-to-end tests skipped without it); ruff check and format clean.
- **Limitations:**
  - Injected faults are cleaner than real failures, and each class has a near-unique message, which favours rules.
  - 13 design groups, one image, one host type.
  - Routing has only 15 labelled runs.
- **Next:**
  - Your review.
  - **Proposed for the product:** diagnosis is rules first, with the triggering line as evidence. Template novelty flags runs the rules cannot classify, and those are shown as "unfamiliar" rather than given a guessed class.
  - **Proposed fixes, as a later pre-registered D2 v2 (TODO P3-11…P3-15):**
    - severity-aware masking that keeps exit codes and message IDs;
    - features restricted to error and warning lines;
    - the include-path fix for overlays;
    - SYN-frontend bases.
  - **Phase 4** (RTL intelligence: pyslang + Yosys feature extractor, Verilator lint gate) per PLAN §12 can start on your go-ahead. PLAN names Phases 1–3 plus a minimal dashboard as the portfolio cut, so the alternative is consolidation first (P3-10, P2-21).
