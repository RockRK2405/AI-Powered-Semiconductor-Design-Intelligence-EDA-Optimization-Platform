# TODO — Actionable Backlog

Each item is specific and independently checkable. IDs are stable.

## Phase 0 — research debt (can run in parallel with Phase 1)

- [ ] **P0-R1** Read the full texts of R13 (EDALearn), R14/R15 (EDA-schema), R40 (METRICS2.1), R45 (IICPilot), R46 (FPGA emulation ML). Record for each: whether per-stage runtime/memory labels exist, their split strategy and their reported metrics.
- [ ] **P0-R2** Systematic search of DAC, ICCAD, MLCAD, ISPD and DATE 2020–2026 for "runtime prediction", "conformal", "uncertainty", "calibration", "out-of-distribution" + EDA. Update `research/03` G1/G4 accordingly.
- [ ] **P0-R3** Search for RTL-simulation regression prioritization with APFD (G5).
- [ ] **P0-R4** Confirm licenses: ORFS designs we plan to use, EPFL benchmarks, IWLS'05, EDALearn, EDA-schema, CircuitNet.
- [ ] **P0-R5** Fill in the "authors: see URL" entries in `research/08`.
- [x] **P0-D1** Decide on a repository LICENSE (your choice; MIT or Apache-2.0 are common for portfolio code).

## Phase 1 — Foundation & toolchain (after approval)

- [x] **P1-01** `pyproject.toml` (Python ≥3.11), `src/siliconai/` package, ruff + pytest config, `.gitignore`, `.env.example`.
- [x] **P1-02** GitHub Actions: lint + unit tests on push.
- [x] **P1-03** OpenROAD route trial (ADR-010): (a) prebuilt binaries, (b) ORFS source build with a 2 h cap, (c) Docker if a daemon is available, (d) fallback to your machine. Record the outcome in DECISIONS.
- [x] **P1-04** Install yosys/iverilog/verilator via apt; record versions.
- [x] **P1-05** `eda/runner.py`: safe subprocess wrapper (no shell, timeout, prlimit, `/usr/bin/time -v` parsing for peak RSS, log capture). Unit tests with a fake tool.
- [x] **P1-06** `data/registry.py`: SQLite schema from ARCHITECTURE §4, plus pydantic models. Tests.
- [x] **P1-07** METRICS2.1 JSON parser. Tests against a real ORFS metrics file.
- [x] **P1-08** Run ORFS `gcd` on Nangate45 end to end through the runner; store all stages in the registry.
- [x] **P1-09** Pilot: ~20 runs (gcd, aes, one medium design × few configs), including 3 repeats each of 3 configs. Measure cost per run and the noise floor. Update the `research/07` budget with real numbers. *(Done: 16 runs. Only 2 of the 3 repeated configs succeeded; see PROGRESS → Phase 1.)*
- [x] **P1-10** `config.py` + structured logging.
- [x] **P1-11** Start `interview_prep/project_explanation.md` from the real Phase 1 work.

## Phase 2 — Data engine + Runtime intelligence (complete; follow-ups P2-16, P2-18…21 open)

- [x] P2-01 Sweep spec (YAML) + resumable sweep runner with fixed concurrency.
- [x] P2-02 Parameterized RTL generators (adder, multiplier, FIFO, FSM, MAC array), tagged `generated`.
- [x] P2-03 D1 v1 dataset build with horizon-tagged features + leakage tests.
- [x] P2-04 `docs/experiments.md` protocols for E1–E4, written **before** training.
- [x] P2-05 Baselines, Ridge/RF/HGB; LOGO evaluation with inner GroupKFold; group-bootstrap CIs (E1).
- [x] P2-06 `uncertainty/conformal.py` (split, CQR, Mondrian) + coverage property tests.
- [x] P2-07 Progressive (per-horizon) models; error vs. horizon (E2). *(Interval width vs. horizon not reported; folded into P2-19.)*
- [x] P2-08 OOD score + abstention at 80%/90% coverage (E4). *(Full risk–coverage curves and the widest-interval comparison: P2-20.)*
- [x] P2-09 Minimal Streamlit page: run browser + prediction with interval.
- [x] P2-10 Sweep preflight: reject floorplan overrides (CORE_UTILIZATION, CORE_ASPECT_RATIO) on designs whose config fixes the floorplan (`FLOORPLAN_DEF`/`DIE_AREA`/`CORE_AREA`); found in the pilot.
- [x] P2-11 Prune large ORFS artifacts (`objects/`, `results/`) after metrics are parsed; keep logs, reports, JSON (≈175 MB/run otherwise).
- [x] P2-12 Chunked sweep execution (≤ 2 h per chunk) with a registry export after each chunk, so that an ephemeral container loses nothing.
- [x] P2-13 Dataset build excludes `failed` config-error runs from runtime training sets and tags them for the log corpus.
- [x] P2-14 Collect D1 v1: `sweeps/d1_core.yaml` complete (186 runs, chunks c01–c07). *(`d1_ext` deliberately not collected: E1 showed the gap is platform × size coverage, which `d1_ext` does not fill; see P2-18.)*
- [x] P2-15 Freeze D1 v1 (hash `ee0aebdd56278380`) and run E1–E4; results, including negative ones, in `docs/results_d1_v1.md`.
- [x] P2-16 Generated designs on asap7, gf180, ihp-sg13g2 and sky130hd: platform default PDN, clock period scaled by each platform's gcd period (asap7 in ps); 8/8 validation runs succeeded (v2c00).
- [x] P2-17 Data-integrity fixes found in chunk c04 (ADR-015): nested LEC timing no longer double-counted; leftover `.tmp` logs handled; clean run directories before every run; `siliconai reparse`; build refuses runs whose step times exceed wall time. Registry and Phase 1 report corrected and logged.
- [ ] P2-18 *(in progress: `sweeps/d1_v2.yaml`, 186 runs, chunks v2c00…)* D1 v2 sweep: mid-size (1k–5k cells) and large designs on asap7, gf180, ihp-sg13g2 and sky130hd; fewer gcd configs; more design groups. Depends on P2-16.
- [ ] P2-19 *(pre-registered as E1b, `docs/experiments.md` §10; code ready; runs after the D1 v2 freeze)* Pre-register and run, on D1 v2: residual hybrid (B1 + HGB on residuals) vs B1 vs HGB; interval width vs. horizon; E2 repeated with the better model.
- [ ] P2-20 E4 follow-ups: an OOD score based on platform × size support; risk–coverage curves; comparison with abstaining on the widest CQR/Mondrian intervals.
- [ ] P2-21 Dashboard: show the B1 prediction next to HGB, since B1 is the better point model on D1 v1.
