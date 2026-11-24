# TODO — Actionable Backlog

Each item is specific and independently checkable. IDs are stable.

## Phase 0 — research debt (can run in parallel with Phase 1)

- [ ] **P0-R1** Read the full texts of R13 (EDALearn), R14/R15 (EDA-schema), R40 (METRICS2.1), R45 (IICPilot), R46 (FPGA emulation ML). Record for each: whether per-stage runtime/memory labels exist, their split strategy and their reported metrics.
- [ ] **P0-R2** Systematic search of DAC, ICCAD, MLCAD, ISPD and DATE 2020–2026 for "runtime prediction", "conformal", "uncertainty", "calibration", "out-of-distribution" + EDA. Update `research/03` G1/G4 accordingly.
- [ ] **P0-R3** Search for RTL-simulation regression prioritization with APFD (G5).
- [ ] **P0-R4** Confirm licenses: ORFS designs we plan to use, EPFL benchmarks, IWLS'05, EDALearn, EDA-schema, CircuitNet.
- [ ] **P0-R5** Fill in the "authors: see URL" entries in `research/08`.
- [ ] **P0-D1** Decide on a repository LICENSE (your choice; MIT or Apache-2.0 are common for portfolio code).

## Phase 1 — Foundation & toolchain (after approval)

- [ ] **P1-01** `pyproject.toml` (Python ≥3.11), `src/siliconai/` package, ruff + pytest config, `.gitignore`, `.env.example`.
- [ ] **P1-02** GitHub Actions: lint + unit tests on push.
- [ ] **P1-03** OpenROAD route trial (ADR-010): (a) prebuilt binaries, (b) ORFS source build with a 2 h cap, (c) Docker if a daemon is available, (d) fallback to your machine. Record the outcome in DECISIONS.
- [ ] **P1-04** Install yosys/iverilog/verilator via apt; record versions.
- [ ] **P1-05** `eda/runner.py`: safe subprocess wrapper (no shell, timeout, prlimit, `/usr/bin/time -v` parsing for peak RSS, log capture). Unit tests with a fake tool.
- [ ] **P1-06** `data/registry.py`: SQLite schema from ARCHITECTURE §4, plus pydantic models. Tests.
- [ ] **P1-07** METRICS2.1 JSON parser. Tests against a real ORFS metrics file.
- [ ] **P1-08** Run ORFS `gcd` on Nangate45 end to end through the runner; store all stages in the registry.
- [ ] **P1-09** Pilot: ~20 runs (gcd, aes, one medium design × few configs), including 3 repeats each of 3 configs. Measure cost per run and the noise floor. Update the `research/07` budget with real numbers.
- [ ] **P1-10** `config.py` + structured logging.
- [ ] **P1-11** Start `interview_prep/project_explanation.md` from the real Phase 1 work.

## Phase 2 — Data engine + Runtime intelligence (preview)

- [ ] P2-01 Sweep spec (YAML) + resumable sweep runner with fixed concurrency.
- [ ] P2-02 Parameterized RTL generators (adder, multiplier, FIFO, FSM, MAC array), tagged `generated`.
- [ ] P2-03 D1 v1 dataset build with horizon-tagged features + leakage tests.
- [ ] P2-04 `docs/experiments.md` protocols for E1–E4, written **before** training.
- [ ] P2-05 Baselines, Ridge/RF/XGBoost; GroupKFold evaluation; bootstrap CIs.
- [ ] P2-06 `uncertainty/conformal.py` (split, CQR, Mondrian) + coverage property tests.
- [ ] P2-07 Progressive (per-horizon) models; error and width vs. horizon.
- [ ] P2-08 OOD score + abstention; risk–coverage curves.
- [ ] P2-09 Minimal Streamlit page: run browser + prediction with interval.
