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

## 11. E5 — H5: log diagnosis on held-out designs and fault variants (D2)

**Written 2026-11-25, after the development-design probes and before any D2 run was collected.** *Status: run on frozen D2 v1 (`3d6cb327b1ed3b5d`) with no deviations. H5a and H5b are not supported: the keyword baseline is significantly better on all three primary endpoints. See [`results_d2.md`](results_d2.md).*
Code: `src/siliconai/log_intelligence/` (`faults.py`, `corpus.py`, `logs.py`, `rules.py`,
`drain.py`); data spec `sweeps/d2.yaml`.

- **Hypothesis H5** (research/04): a template + classifier diagnosis beats a keyword baseline on
  held-out designs *and* held-out fault variants (H5a), and puts a root-cause line in its top 3
  (H5b).
- **Development data, kept apart.**
  - gcd/nangate45 is the development design. It is probed with every injector (yosys and slang frontends; `data/d2/probe/`) and is never part of D2.
  - The keyword baseline and the gold root-cause patterns (`rules.py`) were written from the dev logs only and committed with this section.
- **Data: D2** = every (base, fault) pair of `sweeps/d2.yaml`:
  - 13 base designs, one per design group. 6 are bundled ORFS designs on 4 platforms and 7 are generated families on 5 platforms.
  - Each base gets 26 faults in 8 classes, plus 1 clean run.
  - The 2 slang-frontend bases skip the 9 RTL-frontend faults. In this image slang writes the same single line for all of them (dev probe 5), so no log-based method could separate them.
  - 333 planned runs, one at a time, same image and host type as D1.
  - Out-of-memory and timeout limits are scaled to each base's D1 clean run (peak RSS, wall time).
- **Stopping rule.** D2 is frozen when the plan is complete or after 6 collection chunks,
  whichever comes first. No model is fitted to any D2 run before the freeze.
- **Unit and input.** One run is one example. The input is the run's ORFS step logs in flow order,
  followed by its console log, loaded with the caps in `logs.py`. Nothing else is used: no exit
  code, no config.
- **Labels.**
  - A run whose status is `failed` or `timeout` is labelled with its *injected* class, decided before it ran.
  - **Masked** injections (the flow still succeeded) are excluded from classification; their rate is reported per (class, variant).
  - Clean runs that succeed form the `success` set, used for the anomaly endpoint. A clean run that fails is excluded and reported.
- **Classes (8):**
  - syntax_error, elaboration_error, missing_file, sdc_error;
  - floorplan_capacity (utilization/density/outline too small for cells or power grid);
  - routing_resources (too few routing layers; the dev probe shows either `GRT-0232` congestion or a detailed-router crash);
  - out_of_memory;
  - timeout.
  - The dev probe found these injections masked or misattributed, so they are not in D2: impossible clock, warning-only SDC errors, low `PLACE_DENSITY`, routing-layer adjustment, and a single routing layer (a configuration error).
- **Models.** All fixed: no tuning on D2. Seed 0.
  - **B-kw:** `rules.keyword_predict`. Ordered regex rules; `unknown` counts as wrong.
  - **M-tpl (the learned model under test):**
    - Drain (depth 4, similarity 0.5) is fitted on the training runs' lines.
    - Each run becomes a template-count vector. Test-run lines that match no learned template are ignored.
    - TF-IDF (sublinear tf, smoothed idf), then logistic regression (C = 1, balanced class weights).
  - **Secondary:**
    - M-raw: TF-IDF of masked word uni- and bigrams (min_df 2), then the same logistic regression.
    - M-svc: linear SVM (C = 1, balanced) on M-tpl's features.
- **Splits.**
  - **S-design:** leave one design group out (13 folds).
  - **S-variant:** for each (class, variant), train on all other labelled runs and test on that (class, variant). Every class has ≥ 2 variants, so every labelled run is predicted exactly once.
- **Primary endpoints.**
  - **P1:** macro-F1 over the 8 classes under S-design. Δ = F1(M-tpl) − F1(B-kw). 95% CI by group bootstrap: 2,000 replicates, resampling design groups and recomputing both macro-F1s on the pooled rows.
  - **P2:** the same under S-variant. The bootstrap still resamples design groups, because rows are clustered by design.
  - **P3 (evidence):** top-3 hit rate under S-design. A run is a hit if one of its 3 evidence lines matches `rules.GOLD[true class]`. Runs whose log contains no gold line are excluded (count reported).
    - M-tpl ranks a run's lines by the coefficient of their template for the *predicted* class (later line first on ties) and keeps 3 distinct texts.
    - The baseline B-ev is `rules.error_line_evidence`: the last 3 distinct lines containing "error".
    - Δ = hit(M-tpl) − hit(B-ev), with a group-bootstrap CI.
- **Criteria.**
  - **H5a** is supported only if the CI lower bound is > 0 for **both** P1 and P2.
  - **H5b** is supported only if the CI lower bound for P3 is > 0.
  - H5 = H5a and H5b. Each is reported separately.
- **Secondary (reported, not judged).**
  1. M-raw and M-svc against M-tpl, on both splits.
  2. Per-class F1, confusion matrices, and macro-F1 by origin (ORFS vs generated).
  3. Anomaly detection.
     - (a) The score is the share of a run's lines whose template does not occur in the clean runs of the training groups. AUROC for failed vs clean under S-design.
     - (b) Novel-class detection: for each class c and group g, train M-tpl without class c and group g, then score group g's runs by 1 − max class probability. AUROC for class-c runs (novel) against the others (known), pooled.
  4. B-kw's triggering line as an evidence list of length 1: its hit rate.
  5. The 12 natural D1 failures in `data/d2/natural/` (labels committed with this section):
     - M-tpl is trained on all labelled D2 runs, and B-kw is applied as is;
     - each run is reported individually with its prediction and top-3 evidence; for the 2 `novel` runs, the max probability.
  6. The manifestation table: outcome of every (class, variant) per base.
- **Threats.**
  - **The data:** injected faults are cleaner than real failures. One tool image, one host type, 13 design groups.
  - **The baseline is tuned on dev logs:** this favours B-kw, a deliberate strong-baseline choice.
  - **The gold patterns share an author with B-kw:** they are close to its rules. So S4 favours B-kw, which is why P3 compares against the generic error-line heuristic instead.
  - **The natural failures were read before their labels were fixed.** Some keyword-rule prefixes, GPL and IFP, come from general ORFS knowledge and were not seen in the dev logs. S5 is a sanity check, not evidence.

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-11-24 | Initial version | — |
| 2026-11-24 (before any data or result) | §3: hyperparameters are selected by inner **GroupKFold(5)** on the training groups instead of inner LOGO | Compute: inner LOGO costs about 16× more fits per outer fold on a 4-vCPU VM; GroupKFold is still group-aware |
| 2026-11-24 (before any data or result) | §4: the primary comparison is **HGB (the pre-declared main model, ADR-005) vs the better of B0/B1**. Ridge and RF are reported as secondary | Choosing the best of three candidates after seeing test errors would bias the comparison toward H1 |
| 2026-11-24 (before any data or result) | §6: E3 uses HGB with fixed hyperparameters (learning_rate 0.1, max_leaf_nodes 15, min_samples_leaf 5) and CQR uses the same settings with quantile loss | Keeps E3's nested group-OOF calibration affordable; E3 is about calibration, not accuracy |
| 2026-11-25 (first E1 attempt crashed before producing any number) | HGB models drop feature columns that are entirely missing in the training rows (`DropAllMissing`) | scikit-learn 1.9.1's HGB crashes while binning an all-NaN column, which happens when a LOGO fold's training groups never report some metric. The column carries no information, so the model is unchanged in substance |
| 2026-11-25 (after E4 ran) | E4's secondary comparison against "abstaining on the widest conformal intervals" was not implemented | Group-OOF intervals have constant width, so the comparison is degenerate for method (ii); it was not part of the H4 criterion. Reported as a deviation; TODO P2-20 |
