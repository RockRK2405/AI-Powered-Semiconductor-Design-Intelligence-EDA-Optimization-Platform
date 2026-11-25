# Results on dataset D1 v1 (E1–E4)

Every number here comes from the experiment records in [`experiments/`](../experiments/), produced
by `scripts/run_experiments.py` on the frozen dataset `data/d1/d1_v1.parquet` (content hash
`ee0aebdd56278380`, git `7cc2e90`, seed 0). The protocols and success criteria were fixed in
advance in [`experiments.md`](experiments.md). Section 6 is an **exploratory** follow-up that was not
pre-registered and is labelled as such.

**Summary: of the four pre-registered hypotheses, one is supported (H3) and three are not (H1, H2,
H4).** The most useful finding is a negative one: a two-term log-linear baseline beats gradient
boosting at predicting route and total-flow time on unseen designs. The cause is visible in the
data (§6).

## 1. Dataset

| | |
|---|---|
| Runs collected | 186 (10.4 h of flow time), one at a time, on one 4-vCPU cloud VM type |
| Used for regression | 175 successful runs: 44 designs in 16 design groups, 5 platforms |
| Not used for regression | 8 `failed` (6 aes floorplan conflicts, 2 gcd/sky130hd at high utilization), 3 `timeout` (aes on ihp-sg13g2, 1,800 s cap, detailed route) |
| Origin | 112 ORFS designs + 63 generated (`gen_*`, all on nangate45) |
| Flow time per run | 11 s to 1,634 s (median 39 s); route is 35–93% of it (median 60%) |
| Tool | `openroad/orfs@sha256:620c13d9…` for every run |

The table above counts runs. The 63 generated designs are synthetic RTL from our own generators, and they exist only on
nangate45 so far (TODO P2-16). Error is reported as MAE of ln(seconds): an MAE of 0.40 means a typical
prediction is off by a factor of about e^0.40 ≈ 1.5.

**A container restart during collection.** The last 30 runs were recorded on a different kernel
build, with the same CPU model and core count. Repeats on either side of the restart agree to within about 5% on
route time, which is inside the Phase 1 noise floor. The larger gaps seen in a few repeats were in the first
run of a platform in a chunk, where wall time ≫ CPU time in the I/O-bound steps (a cold file
cache). That inflates small designs' total time, but not route time.

## 2. E1 / H1: do learned models beat baselines on unseen designs? **Not supported.**

Leave-one-design-group-out (LOGO) at horizon `h_synth`. Pre-registered comparison: HGB against
the better of B0/B1, with a group-bootstrap 95% CI of ΔMAE = MAE(HGB) − MAE(baseline).

| Target | B0 (platform median) | B1 (log-linear) | Ridge | RF | HGB | ΔMAE HGB − B1 [95% CI] |
|---|---|---|---|---|---|---|
| **route wall** (primary) | 1.662 | **0.397** | 1.214 | 0.539 | 0.586 | +0.189 [−0.003, +0.320] |
| **total wall** (primary) | 1.487 | **0.327** | 0.730 | 0.430 | 0.474 | +0.148 [−0.043, +0.354] |
| floorplan wall | 0.983 | 0.524 | 0.767 | **0.379** | 0.437 | −0.086 [−0.235, +0.048] |
| place wall | 1.076 | 0.247 | 0.316 | **0.178** | 0.196 | −0.051 [−0.137, +0.019] |
| cts wall | 1.277 | 0.561 | 0.681 | **0.524** | 0.561 | −0.001 [−0.180, +0.197] |
| finish wall | 1.061 | 0.283 | 0.381 | **0.233** | 0.248 | −0.035 [−0.116, +0.059] |
| place peak memory | 0.182 | 0.099 | 0.082 | 0.065 | **0.056** | −0.042 [−0.056, −0.030] |
| cts peak memory | 0.144 | 0.079 | 0.080 | **0.039** | 0.053 | −0.025 [−0.048, −0.006] |
| finish peak memory | 0.523 | 0.170 | 0.247 | **0.118** | 0.121 | −0.049 [−0.099, −0.014] |
| route peak memory | 0.434 | 0.186 | 0.965 | **0.138** | 0.177 | −0.009 [−0.079, +0.045] |
| floorplan peak memory | 0.162 | 0.097 | 0.226 | 0.083 | **0.082** | −0.015 [−0.056, +0.015] |

- On both primary endpoints the **baseline B1 is better than HGB**:
  - Route: MdAPE 34% for B1 against 46% for HGB, R² 0.89 against 0.75.
  - Total flow: MdAPE 27% against 33%.
  - The CIs only just include 0 in HGB's favour, so H1 is clearly not supported.
- **Where learned models do win (secondary endpoints):** HGB beats B1, with a CI excluding 0, on
  peak memory for place, cts and finish. Memory is less sensitive to the platform × size gap
  described in §6.
- **Ridge is unstable** on this data: R² < 0 on several targets. It extrapolates badly from
  heavy-tailed metric features even after a signed-log transform.
- **No leakage alarm:** every MAE is far above the 0.06 noise floor, so the pre-registered
  leakage audit was not triggered.

## 3. E2 / H2: does observing more stages help? **Not supported.**

HGB (the pre-registered model), LOGO. MAE of ln(wall) by horizon:

| Target | h_synth | h_floorplan | h_place | h_cts | h_route | ΔMAE h_place − h_synth [95% CI] |
|---|---|---|---|---|---|---|
| route wall | 0.586 | 0.593 | 0.510 | 0.522 | — | −0.076 [−0.191, +0.074] |
| finish wall | 0.248 | 0.265 | 0.239 | 0.278 | 0.239 | −0.010 [−0.055, +0.050] |

The point estimates improve a little after placement, but the CIs include 0, and adding stages does not help
monotonically. E2 inherits HGB's weakness from E1, so this tests "does more information help
*this* model", not the best achievable model. With B1 or the hybrid of §6 the answer may differ.
That would be a new experiment, not a reinterpretation of this one.

## 4. E3 / H3: are conformal intervals valid on unseen designs? **Supported.**

Nominal coverage 90%, HGB with fixed parameters. Coverage with a group-bootstrap 95% CI, and mean
interval width on the ln scale. A width *w* means the interval spans a factor of e^w from low to high.

| Target | Method | Random 5-fold coverage | LOGO coverage [95% CI] | LOGO mean width |
|---|---|---|---|---|
| route | (i) naive split | 92.6% | **52.6%** [37.7, 70.8] | 1.06 |
| route | (ii) group-OOF | 98.3% | **94.3%** [87.7, 99.0] | 2.67 |
| route | (iii) CQR, group-OOF | 97.7% | 89.7% [85.1, 93.8] | 2.61 |
| route | (iv) Mondrian by platform | 98.9% | 90.3% [83.4, 96.4] | 2.41 |
| total | (i) naive split | 91.4% | **56.6%** [45.9, 71.5] | 0.84 |
| total | (ii) group-OOF | 97.7% | **92.0%** [78.2, 100] | 2.42 |
| total | (iii) CQR, group-OOF | 96.0% | 86.3% [79.5, 93.1] | 1.87 |
| total | (iv) Mondrian by platform | 98.9% | 88.6% [76.5, 96.6] | 2.20 |

- **The pre-registered criteria are met for both targets:**
  - Naive split conformal covers ≥ 88% under random splits.
  - It collapses to 53–57% on unseen design groups.
  - Group-aware calibration restores ≥ 88%.
- **Practical caveat:** the honest intervals are wide. A width of 2.67 is a factor of about 3.8 either
  side of the point prediction for route time. That is useful for "will this take minutes or hours",
  not for scheduling to the minute. A better point model (§6) should narrow the intervals, since the width
  is driven by out-of-group errors.
- With 16 groups the coverage CIs are wide (total, group-OOF: 78–100%).

## 5. E4 / H4: does abstaining on out-of-distribution inputs avoid large errors? **Not supported.**

A large error is one where the prediction is off by more than 50%. The OOD score is the mean distance to the 5 nearest training rows, computed
on training groups only. The predictions are E1's HGB LOGO predictions.

| Target | Large-error rate, no abstention | at 80% coverage: OOD / random | at 90% coverage: OOD / random | OOD − random, 95% CI (80% / 90%) |
|---|---|---|---|---|
| route | 57.7% | 54.3% / 57.7% | 55.7% / 57.7% | [−0.073, +0.047] / [−0.045, +0.031] |
| total | 38.3% | 38.6% / 38.3% | 36.1% / 38.2% | [−0.052, +0.050] / [−0.061, +0.037] |

The feature-space OOD score does not find the predictions that will go wrong. §6 shows why: the worst errors
are not on unusual-looking designs. They are on ordinary designs placed in a platform/size cell
with almost no training data, and a kNN distance over 51 mostly-metric features does not pick that up.

**Deviation:** the protocol also listed a comparison against "abstaining on the widest conformal
intervals". It was not implemented: group-OOF intervals have a constant width, and the
comparison was not part of the H4 support criterion. It is recorded in the change log and in
TODO P2-20.

## 6. Exploratory follow-up (NOT pre-registered)

`scripts/exploratory_e1.py` → `experiments/exploratory_e1_ee0aebdd56278380.json`. This analysis was chosen
*after* seeing E1, so it explains E1 but is not evidence for anything new.

**Why HGB loses: platform × size coverage.**

Rows in D1 v1 by platform and synthesized cell count:

| Platform | < 1k cells | 1k–5k | > 5k |
|---|---|---|---|
| nangate45 | 43 | 27 | 24 |
| asap7 | 16 | 0 | 10 |
| gf180 | 9 | 0 | 10 |
| ihp-sg13g2 | 18 | 0 | 7 |
| sky130hd | 7 | 0 | 4 |

- Outside nangate45 there are no mid-size designs and only 2–3 large design groups per platform.
- When one of them, riscv32i, is held out, HGB predicts small-design runtimes for it:
  - 44–70 s on gf180, ihp-sg13g2 and sky130hd, against 222–873 s actual;
  - total-flow MAE 1.54 for that group, from HGB with fixed parameters.
- Trees cannot share the "more cells → more time" trend across platforms when a platform's leaf
  has no large designs. B1 assumes one shared slope plus a per-platform offset, so it extrapolates.
- Range extrapolation alone is not the explanation:
  - Only two held-out groups per target have any target outside the training range: gen_crc and aes for route, gen_crc and ibex for total.
  - HGB's worst groups, riscv32i and spi, are not among them.
  - The gap is in *coverage of the platform × size space*.

**A candidate model, for future pre-registration: a residual hybrid.** It fits B1, then HGB on B1's residuals.
LOGO MAE, with HGB at fixed parameters and no inner selection:

| Target | B1 | HGB (fixed) | Hybrid |
|---|---|---|---|
| route wall | 0.397 | 0.548 | 0.356 |
| total wall | 0.327 | 0.456 | 0.257 |

This is one post-hoc model with no CI, tried after seeing the data, so it is a hypothesis to test on new data,
not a result.

## 7. What this means for the project

1. **For runtime, a physically sensible baseline is hard to beat with few design groups.** Any
   later claim of a learned improvement must be measured against B1, not against B0.
2. **The data gap is clear and fixable:** generated designs and mid-size designs on asap7, gf180,
   ihp-sg13g2 and sky130hd (TODO P2-16), more design groups, and fewer gcd configs (gcd is already 44
   of 175 rows).
3. **Conformal calibration must be group-aware.** Naive split conformal silently drops to about 55% coverage
   on unseen designs. This is the most transferable result here.
4. **Next experiment (D1 v2, to be pre-registered before collection):** hybrid vs B1 vs HGB, on
   a dataset with platform × size coverage. Plus E4 with an OOD score that looks at platform × size
   support rather than raw feature distance.

## 8. Threats to validity

- One machine type; absolute runtimes don't transfer.
- 16 design groups: every CI here is wide. "Not supported" means "not shown on this data", not
  "shown false", except for H1's primary endpoints, where the point estimate goes the other way.
- 63 of 175 rows are generated RTL, all on one platform.
- Hyperparameters for E1/E2 were chosen by inner GroupKFold(5), a pre-registered change from inner LOGO.
  E3/E4 use fixed parameters.
