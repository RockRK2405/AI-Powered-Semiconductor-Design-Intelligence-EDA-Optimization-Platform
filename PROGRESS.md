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
| gcd | nangate45 | 3 | 33.1 (mean) | 54% | 557 |
| gcd | sky130hd | 1 | 31.2 | 60% | 450 |
| aes | nangate45 | 3 | 300.1 (mean) | 66% | 925 |
| ibex | nangate45 | 1 | 300.0 | 57% | 959 |
| jpeg | nangate45 | 1 | 860.0 | 60% | 1,856 |
| aes | sky130hd | 1 | 1,576.3 | 93% | 2,867 |

- Docker start-up and teardown add about 5–7 s per run on top of the step times. The runtime labels
  use the step times, not the outer wall time.
- Detailed routing dominates (54–93% of flow time). The same RTL (aes) costs **5.3×** more on
  sky130hd than on nangate45, almost all in routing. So the platform is a first-order feature.
- Peak memory stayed below 3 GB, so memory is not the binding constraint on this machine; time is.

**Run-to-run noise (3 repeats of an identical configuration)**

| Design | Whole-flow CV (outer wall) | Per-stage wall-time CV (stages > 0.5 s) | Per-stage peak-memory CV |
|---|---|---|---|
| gcd nangate45 | 1.7% | 2.0–5.9% | 0.1–2.1% |
| aes nangate45 | 0.7% | 0.7–4.7% | 0.1–3.0% |

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
