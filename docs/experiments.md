# Experiment protocols E1–E4 (pre-registered)

**Written 2026-11-24, before dataset D1 v1 exists and before any model is trained** (TODO P2-04).
Any change after the first E1 run is listed in the change log at the bottom with a reason. This
document fixes primary endpoints, splits, baselines and success criteria in advance, so the
results cannot be tuned to look good.

Hypotheses are defined in [`research/04_novelty_analysis.md`](../research/04_novelty_analysis.md).

## 0. Dataset D1 v1 — inclusion rules

| Rule | Why |
|---|---|
| One ORFS image digest (`openroad/orfs@sha256:620c13d9…`) | Tool version is a confounder (ADR-010) |
| One host fingerprint (CPU model, 4 logical CPUs) | Runtime is machine-specific |
| `concurrency = 1` | Contention distorts runtime labels (Phase 1 pilot) |
| Regression targets: runs with `status = success` only | A failed run has no downstream stages |
| `aborted` runs excluded everywhere | Caused by our infrastructure, not the design |
| `failed` / `timeout` runs kept for outcome-risk work (Phase 7) and the log corpus (H5) | |

Before E1 runs, the dataset is **frozen**: the Parquet file is content-hashed, and every experiment
record stores that hash. Adding runs creates D1 v2; results are never silently mixed.

## 1. Targets, horizons and leakage

- **Stages** *s* ∈ {synth, floorplan, place, cts, route, finish}.
- **Targets** per stage: `ln(wall_s)` and `ln(peak_rss_mb)`; also total flow `ln(Σ wall_s)`.
  Wall time is the sum over the stage's ORFS steps; peak memory is the max (ADR-011).
- **Horizon** *h*: the last stage whose outputs are visible. A model at horizon *h* predicts only
  stages after *h*.
  - `h0` (pre-run): platform, flow-config knobs, design origin. No design-size information (RTL
    features arrive in Phase 4). This is deliberately weak and serves as a floor.
  - `h_synth`: + all synthesis METRICS2.1 values and synthesis wall/memory. **Primary horizon**:
    after cheap synthesis, predict the expensive physical-design cost.
  - `h_floorplan`, `h_place`, `h_cts`, `h_route`: each adds that stage's metrics and measurements.
- **Leakage rules (enforced by tests):** a feature is tagged with the stage that produces it,
  and a model at horizon *h* may only use features tagged ≤ *h*. Run ids, timestamps,
  `repeat_index`, `exit_code` and `status` are never features.

## 2. Splits

- **Primary: leave-one-group-out (LOGO)** over `design_group`. The same RTL on any platform, and
  every member of a generated family, share one group. So the test design's RTL lineage is never
  seen in training.
- **Contrast (E3 only):** random 5-fold over rows. This leaks design identity and is expected to
  look optimistic.
- Repeated runs of the same config always stay in the same group, so repeats can't leak.

## 3. Models

- **Baselines**
  - **B0:** the training median of the target, per platform.
  - **B1:** log-linear `ln(y) ~ a + b·ln(synth cell count) + platform` (from `h_synth` onward).
- **Candidates:** Ridge (standardized features), RandomForest, and scikit-learn
  HistGradientBoosting (GBM).
  - Hyperparameters come from a small fixed grid.
  - They are selected by inner LOGO on the training groups only.
- Seeds are fixed and recorded. Each run writes `experiments/<id>.json` with the params, dataset
  hash, git SHA, seed and metrics (ADR-006).

## 4. E1 — H1: learned models vs baselines on unseen designs

- **Primary endpoints (fixed now):** MAE of `ln(wall)` at horizon `h_synth` for (a) **route** and
  (b) **total-flow** wall time, under LOGO.
- **Secondary endpoints:** the same for every other stage and for peak memory; MdAPE on the original
  scale; R²; underestimation rate (prediction below actual by more than 20%).
- **Uncertainty:** a paired, group-level bootstrap (resample design groups; 2,000 replicates) of
  ΔMAE = MAE(best candidate) − MAE(best baseline).
- **H1 is supported** only if the 95% CI of ΔMAE lies entirely below 0 for **both** primary
  endpoints. Otherwise H1 is reported as not supported.
- **Noise floor:** Phase 1 measured per-stage CV ≤ 6%, which is about 0.06 on the ln scale. An MAE well
  below 0.06 would be implausible and triggers a leakage audit before it is reported.

## 5. E2 — H2: does each observed stage help downstream predictions?

- For each target stage, report MAE and the 90% interval width (from E3's best method) at every
  admissible horizon, under LOGO.
- **H2 is supported** if, for route and finish targets, MAE at `h_place` is lower than at
  `h_synth`, with a group-bootstrap 95% CI of the difference below 0.

## 6. E3 — H3: conformal coverage on unseen designs

- **Nominal coverage:** 90%, on the ln scale, for the primary endpoints (route and total, at
  `h_synth`).
- **Methods**
  - **(i) Naive split-conformal:** the calibration set is a random 25% of the training rows.
  - **(ii) Group-aware conformal:** calibration residuals come from out-of-group predictions,
    using inner LOGO on the training groups (CV+ style).
  - **(iii) CQR:** GBM quantile regression at 5% and 95%, conformalized as in (ii).
  - **(iv) Mondrian by platform:** method (ii) applied per platform.
- **Report:** empirical coverage (group-bootstrap CI) and mean width, under random splits and under LOGO.
- **H3 is supported** if (i) reaches ≥ 88% coverage under random splits but stays below 85% under LOGO,
  **and** some method among (ii)–(iv) reaches ≥ 88% under LOGO. Both directions are reported
  whatever happens.

## 7. E4 — H4: abstention on out-of-distribution inputs

- **OOD score:** mean distance to the 5 nearest training rows in the standardized feature space
  of the `h_synth` model, computed on training groups only.
- **Large error:** |ln(pred/actual)| > ln 1.5 (off by more than 50%).
- **Comparison:** the large-error rate at 80% and 90% coverage when abstaining on the highest OOD
  scores, versus random abstention (mean of 1,000 random draws) and versus abstaining on the widest
  conformal intervals.
- **H4 is supported** if OOD abstention gives a lower large-error rate than random abstention at
  both coverages, with a group-bootstrap CI that excludes 0.

## 8. Threats to validity, acknowledged up front

- **One machine type** (a shared cloud VM, 4 vCPU). Absolute runtimes don't transfer to other
  machines; relative conclusions may.
- **Few design groups** (about 15–20): CIs will be wide. A null result can mean too little data
  rather than no effect.
- **Generated designs are synthetic RTL.** They are tagged, and results are also reported for ORFS
  designs only.
- **Light interactive work** (editing, unit tests) shared the VM during collection. Phase 1 noise
  measurements cover this regime, but it is uncontrolled.

## 9. Exploratory analyses (not pre-registered)

Analyses chosen after seeing a result live in `scripts/exploratory_*.py`, write
`experiments/exploratory_*.json` with `"exploratory": true`, and are reported in a separate,
labelled section. They can motivate a new pre-registered experiment on new data, never a claim.

Results on D1 v1: [`results_d1_v1.md`](results_d1_v1.md).

## 10. E1b — H1b: does the residual hybrid beat the baseline on *new* data? (D1 v2)

**Written 2026-11-25, after the D1 v1 results and before any D1 v2 run was collected.** *Status: run on frozen D1 v2 (`3f601a94fdbaf60d`) with no deviations; H1b not supported. See [`results_d1_v2.md`](results_d1_v2.md).* The
hybrid was found in an exploratory analysis of D1 v1 (§9, `docs/results_d1_v1.md` §6). So it is
judged only on rows that did not exist when it was proposed.

- **Hypothesis H1b.** On unseen design groups, at horizon `h_synth`, the residual hybrid (B1, then
  HGB on B1's residuals) predicts route and total-flow wall time more accurately than B1.
- **Data: D1 v2** = every D1 v1 run plus the runs from `sweeps/gen_validate_v2.yaml` and
  `sweeps/d1_v2.yaml`.
  - The §0 inclusion rules apply: same image, host CPU model, 4 CPUs and concurrency 1.
  - Purpose of the new runs: generated designs on asap7, gf180, ihp-sg13g2 and sky130hd (clock periods
    scaled per platform, see `rtlgen/orfs_design.py`), larger generated sizes, and bundled ORFS designs
    not in D1 v1. No new gcd runs.
- **Stopping rule.** D1 v2 is frozen when `d1_v2.yaml` is complete or after 5 collection chunks,
  whichever comes first. No model is fitted to any new row before the freeze.
- **Split.** LOGO over `design_group`, exactly as in E1. Training uses every row of the other
  groups, old and new.
- **Scored rows (primary).** Only **new rows**: runs absent from `d1_v1.parquet`. Rows from D1 v1
  shaped the hypothesis, so they are not used to judge it.
- **Models.**
  - B1, unchanged.
  - HGB as in E1.
  - **Hybrid:** B1 fitted on the training rows, then HGB fitted to B1's residuals. HGB hyperparameters
    are chosen from the E1 grid by inner GroupKFold(5) on the training groups.
  - Seed 0.
- **Primary endpoints.** MAE of ln(wall) for route and total flow, on the new rows.
- **Uncertainty.** Paired group bootstrap (2,000 replicates) of ΔMAE = MAE(hybrid) − MAE(B1), resampling
  the design groups that have new rows.
- **H1b is supported** only if the 95% CI of ΔMAE lies entirely below 0 for **both** endpoints.
- **Secondary (reported, not judged):**
  1. HGB − B1 on the new rows: does better platform × size coverage remove HGB's deficit?
  2. All three models on all D1 v2 rows.
  3. Results split by origin (ORFS vs generated) and by platform.
  4. Group-OOF conformal (E3 method ii, 90%) with the hybrid as point model, against HGB as point model:
     coverage and mean width on the new rows.
  5. E2 repeated with the hybrid: route MAE at `h_place` minus at `h_synth`, on the new rows.
- **Threats.**
  - The new generated rows belong to existing groups (`gen_*`), so the unseen-*group* test for them
    is about a family the model has never seen on any platform, as in E1.
  - New bundled ORFS designs are few. Their per-group results will be reported individually.

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-11-24 | Initial version | — |
| 2026-11-24 (before any data or result) | §3: hyperparameters are selected by inner **GroupKFold(5)** on the training groups instead of inner LOGO | Compute: inner LOGO costs about 16× more fits per outer fold on a 4-vCPU VM; GroupKFold is still group-aware |
| 2026-11-24 (before any data or result) | §4: the primary comparison is **HGB (the pre-declared main model, ADR-005) vs the better of B0/B1**. Ridge and RF are reported as secondary | Choosing the best of three candidates after seeing test errors would bias the comparison toward H1 |
| 2026-11-24 (before any data or result) | §6: E3 uses HGB with fixed hyperparameters (learning_rate 0.1, max_leaf_nodes 15, min_samples_leaf 5) and CQR uses the same settings with quantile loss | Keeps E3's nested group-OOF calibration affordable; E3 is about calibration, not accuracy |
| 2026-11-25 (first E1 attempt crashed before producing any number) | HGB models drop feature columns that are entirely missing in the training rows (`DropAllMissing`) | scikit-learn 1.9.1's HGB crashes while binning an all-NaN column, which happens when a LOGO fold's training groups never report some metric. The column carries no information, so the model is unchanged in substance |
| 2026-11-25 (after E4 ran) | E4's secondary comparison against "abstaining on the widest conformal intervals" was not implemented | Group-OOF intervals have constant width, so the comparison is degenerate for method (ii); it was not part of the H4 criterion. Reported as a deviation; TODO P2-20 |
