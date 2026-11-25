# Results on dataset D1 v2 (E1b)

Every number here comes from [`experiments/e1b_3f601a94fdbaf60d.json`](../experiments/e1b_3f601a94fdbaf60d.json),
produced by `scripts/run_experiments.py --only e1b --seen data/d1/d1_v1.parquet` on the frozen
dataset `data/d1/d1_v2.parquet` (content hash `3f601a94fdbaf60d`, frozen in git `f765795`, seed 0).
The protocol was committed in `8feed44`, before any D1 v2 run was collected
([`experiments.md`](experiments.md) §10). There were no deviations from it.

**Summary: H1b is not supported.**
- **Primary result:** on the 179 rows that are new since D1 v1, the residual hybrid has the lowest error of the three models on both
  primary endpoints. Its advantage over B1 is −0.135 ln on both. But both 95% CIs include 0, because only 9 design groups have new rows and the groups
  disagree.
- **Secondary result:** the D1 v1 finding "B1 beats HGB" did not repeat on the new rows. The point
  estimates now favour HGB, also with CIs that include 0.
- **What limits the evidence:** the number of design groups, not the number of runs.

## 1. Dataset

| | |
|---|---|
| New runs collected | 186 (`sweeps/d1_v2.yaml`, chunks v2c00–v2c05, 7.7 h of flow time), same host type, one at a time, same `openroad/orfs@sha256:620c13d9…` image |
| Outcome of the new runs | 179 `success`, 3 `failed`, 4 `timeout` (1,800 s cap) |
| D1 v2 | 354 successful runs: 139 designs, 18 design groups, 5 platforms. The 175 D1 v1 rows are included with identical labels. |
| New rows (scored by E1b) | 179: 175 generated (`gen_*`) + 4 ORFS (ethmac and mock-alu on asap7, both groups new) |
| Stopping rule | `d1_v2.yaml` complete (186/186 runs with a final status) at chunk 5. Frozen before any model was fitted to a new row. |

**Failures and timeouts.** All of them are genuine flow outcomes. Each one is kept in the registry and excluded from regression,
as the §0 rules require:
- `sai_fsm` (small) on ihp-sg13g2 at 60% utilization: the core is too narrow for the TopMetal1 power straps (PDN-0185).
- `tage_update` on asap7, both configs, including ORFS's default: the post-CTS equivalence check
  (`LEC_CHECK`, kepler-formal) cannot load the SRAM macros that `AUTO_MEMORIES` generates. ORFS disables LEC for
  cva6 for this reason, but not for tage_update in the pinned image.
- `chi_async_bridge` on asap7 (both configs) and `sai_fsm_i3_o8_s3_s128` on sky130hd (both configs) reach the cap in detailed
  route.

As a result, tage_update and chi_async_bridge contribute no rows. The planned new ORFS designs reduce to
ethmac and mock-alu on asap7.

**The platform × size gap is filled.** Rows by synthesized standard-cell count:

| Platform | D1 v1: < 1k / 1k–5k / > 5k | D1 v2: < 1k / 1k–5k / > 5k |
|---|---|---|
| nangate45 | 43 / 27 / 24 | 43 / 27 / 26 |
| asap7 | 16 / **0** / 10 | 34 / 18 / 22 |
| gf180 | 9 / **0** / 10 | 33 / 18 / 12 |
| ihp-sg13g2 | 18 / **0** / 7 | 37 / 16 / 15 |
| sky130hd | 7 / **0** / 4 | 31 / 17 / 5 |

## 2. E1b / H1b: does the residual hybrid beat B1 on new data? **Not supported.**

- **Setup:** leave-one-design-group-out (LOGO) over all 354 rows at horizon `h_synth`. Each prediction comes from a model
  trained on the other groups, old and new rows alike. Only the 179 new rows are scored.
- **Uncertainty:** paired group bootstrap with 2,000 replicates over the 9 design groups that have new rows.
- **Error measure:** MAE of ln(seconds). An MAE of 0.54 means a typical prediction is off by a factor of about e^0.54 ≈ 1.7.

| Target | B1 | HGB | Hybrid | ΔMAE hybrid − B1 [95% CI] | Supported? |
|---|---|---|---|---|---|
| **route wall** | 0.673 | 0.575 | **0.537** | −0.135 [−0.312, +0.062] | no |
| **total wall** | 0.565 | 0.439 | **0.430** | −0.135 [−0.311, +0.054] | no |

Other point metrics on the new rows (route / total):

| | B1 | HGB | Hybrid |
|---|---|---|---|
| MdAPE | 74% / 63% | 44% / 30% | 39% / 28% |
| R² (ln) | 0.49 / 0.46 | 0.50 / 0.51 | 0.54 / 0.55 |
| Underestimate rate (< 80% of actual) | 25% / 22% | 30% / 22% | 30% / 27% |

**Why the CI is wide: the groups disagree.** MAE on new rows, per held-out design group:

| Group (new rows) | route: B1 / HGB / hybrid | total: B1 / HGB / hybrid |
|---|---|---|
| gen_addtree (29) | 0.796 / 0.347 / **0.330** | 0.709 / 0.330 / **0.277** |
| gen_mac (29) | 0.780 / 0.427 / **0.416** | 0.699 / 0.307 / **0.306** |
| gen_mult (24) | 0.526 / **0.358** / 0.372 | 0.452 / 0.267 / **0.239** |
| gen_fifo (24) | 0.439 / 0.346 / **0.308** | 0.394 / **0.233** / 0.306 |
| gen_crc (24) | 0.620 / 0.605 / **0.581** | 0.445 / **0.426** / 0.459 |
| gen_fsm (21) | 0.966 / 1.016 / **0.939** | 0.797 / 0.807 / **0.764** |
| gen_alu (24) | **0.612** / 0.998 / 0.949 | **0.464** / 0.740 / 0.781 |
| ethmac (2) | 0.703 / 1.168 / **0.450** | 0.617 / 1.111 / **0.237** |
| mock_alu (2) | **0.161** / 0.722 / 0.434 | **0.135** / 0.480 / 0.350 |

The hybrid's average gain comes mostly from two families: addtree and mac, where B1 is off by a factor of about 2.2.
On gen_alu the hybrid is clearly worse than B1. With 9 groups, resampling them moves the mean
difference across 0.

## 3. Secondary endpoints (reported, not judged)

1. **HGB − B1 on the new rows** (does better coverage remove HGB's deficit?):
   - route −0.098 [−0.287, +0.122];
   - total −0.126 [−0.283, +0.060].
   - On D1 v1, B1 was better by +0.189 and +0.148. The sign has flipped in the point estimates, but neither
     direction is established. This fits the D1 v1 explanation (trees need platform × size coverage), but it
     does not prove it. B1 itself is also much worse on these rows (route 0.673) than in E1 (0.397), so part of the
     change is the new rows being harder for B1, not only HGB getting better.
2. **All 354 rows:**

   | Target | B1 | HGB | Hybrid |
   |---|---|---|---|
   | route | 0.589 | 0.536 | 0.453 |
   | total | 0.502 | 0.416 | 0.351 |

   These include the D1 v1 rows that suggested the hybrid, so they are not evidence for it.
3. **By origin:**
   - Generated rows: n = 175. Route: B1 0.678, HGB 0.567, hybrid 0.539. Total: B1 0.570, HGB 0.431, hybrid 0.433.
   - ORFS rows: n = 4, in 2 groups. Too few for any conclusion.
   - **By platform:** on route, the hybrid ≤ B1 on every platform. Leaving out nangate45's 2 new rows, route MAE ranges from 0.332 on asap7 to 0.786 on sky130hd. ihp-sg13g2 and sky130hd remain the hardest.
4. **Conformal intervals on the new rows** (E3 method ii, group-OOF, nominal 90%):

   | Target | Point model | Coverage [95% CI] | Mean width (ln) |
   |---|---|---|---|
   | route | HGB | 87.7% [75.9, 97.1] | 2.28 |
   | route | hybrid | 82.1% [68.0, 93.8] | 2.04 |
   | total | HGB | 87.7% [75.7, 97.3] | 1.83 |
   | total | hybrid | 82.7% [68.6, 93.8] | 1.63 |

   - Group-aware calibration still lands near the nominal 90% on new groups. Every CI contains 90%, but every point estimate is below it.
   - The hybrid gives intervals about 10% narrower, but it covers about 5 points less. That is no free gain.
   - In E3 on D1 v1, group-OOF HGB covered 94.3% (route) and 92.0% (total).
5. **E2 repeated with the hybrid:** route MAE at `h_place` minus at `h_synth`, on the new rows, is
   −0.008 [−0.097, +0.084]. Seeing the placed design does not help the hybrid either, the same as HGB in E2.

## 4. What this means

1. **Two pre-registered tests, two "not supported" results, and point estimates that moved.**
   - On D1 v1, B1 beat HGB.
   - On new rows with platform × size coverage, HGB and the hybrid beat B1 in point estimate.
   - Neither ordering is significant at 9–16 design groups.
   - The honest statement is: *no runtime model has been shown to beat a two-term log-linear baseline on unseen
     design groups*.
2. **More groups, not more runs.**
   - E1b scored 179 rows, but the effective sample size is 9 groups, and the per-group results disagree in sign.
   - Adding configs of the same families will not narrow these CIs.
   - Adding new design families will, especially real ORFS designs on several platforms. D1 v2 has 11
     real-design groups: the 9 from D1 v1 plus ethmac and mock-alu, the latter two on asap7 only.
3. **The transferable results stand:**
   - Group-aware conformal calibration stays close to nominal on new data. Naive calibration did not, in E3.
   - The "physically sensible baseline first" discipline caught a would-be false claim twice.
4. **Product implication.**
   - The runtime predictor ships B1 as the reference prediction, with group-OOF intervals.
   - The hybrid is the best point model in both evaluations and can be offered next to B1, labelled experimental.
   - No accuracy claim is made beyond the numbers above.

## 5. Threats to validity

- 175 of 179 scored rows are generated RTL. The test is mostly about unseen *generated families* on new
  platforms. Every generated family also has D1 v1 rows on nangate45, and those are held out with it under LOGO.
- 9 scored groups. The two ORFS groups contribute 2 rows each.
- One machine type and one tool image. Absolute times don't transfer.
- The hybrid was proposed after seeing D1 v1. E1b controls for that by scoring only new rows, but the
  model family and its grid were still chosen with D1 v1 in view.
