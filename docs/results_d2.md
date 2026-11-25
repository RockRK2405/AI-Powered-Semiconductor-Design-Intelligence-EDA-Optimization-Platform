# Results on dataset D2 v1 (E5: log diagnosis)

Every pre-registered number here comes from
[`experiments/e5_3d6cb327b1ed3b5d.json`](../experiments/e5_3d6cb327b1ed3b5d.json). It was produced by
`scripts/run_e5.py --manifest data/d2/d2_v1.manifest.json` on the frozen corpus D2 v1:
- content hash `3d6cb327b1ed3b5d`, frozen in git `50c6aca`;
- seed 0; runtime 991 s.

The protocol ([`experiments.md`](experiments.md) §11) and the keyword baseline and gold patterns (`rules.py`) were committed before any D2 run was collected. The models were committed before the freeze. There were no deviations from the protocol.

Sections 3 and 5 are **post hoc**: they were done after seeing the result, and they are labelled as such.

**Summary: H5 is not supported. Both H5a and H5b fail, and the keyword baseline is significantly better.**

| Endpoint | M-tpl (learned) | Baseline | Δ (M-tpl − baseline) [95% CI] | Criterion |
|---|---|---|---|---|
| P1 macro-F1, unseen design group (S-design) | 0.869 | B-kw 0.970 | **−0.102 [−0.126, −0.078]** | lower bound > 0: **no** |
| P2 macro-F1, unseen fault variant (S-variant) | 0.521 | B-kw 0.970 | **−0.450 [−0.479, −0.416]** | lower bound > 0: **no** |
| P3 top-3 evidence hit rate (S-design) | 0.372 | B-ev (last 3 "error" lines) 0.440 | **−0.067 [−0.093, −0.045]** | lower bound > 0: **no** |

- All three CIs lie entirely **below** zero. The learned template model is not just "not shown to be better": on this corpus it is worse than the hand-written rules and worse than the naive "grep error" heuristic.
- The model also collapses on unseen fault variants (P2). §5 shows why: it learned how far a run got, not what went wrong.
- The useful learned signal is anomaly detection: a run's share of templates never seen in clean runs separates failed from clean runs with AUROC 0.81 (S3a). The keyword rules cannot do that.

## 1. Dataset

| | |
|---|---|
| Planned and collected | 333 runs (`sweeps/d2.yaml`): 13 base designs, one per design group, × 26 faults in 8 classes, + 1 clean run each. The 2 slang-frontend bases skip the 9 RTL-frontend faults. Collected in chunks d2c01–d2c02 (3.3 h of flow time), one run at a time, same `openroad/orfs@sha256:620c13d9…` image and host type as D1 |
| Outcomes | 256 `failed`, 39 `timeout`, 38 `success` |
| Labelled (used for classification) | **295**: every faulted run that failed or timed out, labelled with its *injected* class |
| Masked (fault did not show) | 25 faulted runs succeeded; excluded from classification as pre-registered |
| Clean runs | 13 of 13 succeeded; used for the anomaly endpoint |
| Development design | gcd/nangate45; probed with every injector before D2; never in D2 |

**Class counts (labelled):**
- syntax_error 44, elaboration_error 42, missing_file 50, sdc_error 39;
- floorplan_capacity 27, routing_resources 15, out_of_memory 39, timeout 39.

**Manifestation (S6).** Every fault manifested on every base except these:

| Fault | Failed | Succeeded (masked) |
|---|---|---|
| floorplan_capacity / no_whitespace | 1 | **12** |
| routing_resources / three_layers | 6 | **7** |
| routing_resources / two_layers | 9 | **4** |
| elaboration_error / undefined_module | 10 | 1 (dynamic_node) |
| elaboration_error / undeclared_identifier | 10 | 1 (dynamic_node) |

- On the dev design, `no_whitespace` (a detailed-placement failure) and `three_layers` both failed. On the 13 bases they mostly do not. Small designs keep enough slack.
- routing_resources therefore has only 15 labelled runs, from 10 bases, and its per-class numbers are the least reliable.

## 2. Primary results (pre-registered)

**P1 and P2: classification.** B-kw (`rules.keyword_predict`) is applied unchanged on both splits; its rules were written once from the dev logs. M-tpl is refitted per fold, and its Drain templates are learned from the training runs only.

Per-class F1:

| Class | n | B-kw | M-tpl, S-design | M-tpl, S-variant |
|---|---|---|---|---|
| syntax_error | 44 | 0.900 | 0.900 | 0.646 |
| elaboration_error | 42 | 0.937 | 0.937 | 0.709 |
| missing_file | 50 | 0.925 | 0.779 | 0.389 |
| sdc_error | 39 | 1.000 | 0.918 | 0.796 |
| floorplan_capacity | 27 | 1.000 | 0.783 | 0.625 |
| routing_resources | 15 | 1.000 | 0.968 | 0.622 |
| out_of_memory | 39 | 1.000 | 0.854 | **0.121** |
| timeout | 39 | 1.000 | 0.812 | **0.257** |
| **macro** | 295 | **0.970** | **0.869** | **0.521** |

- **B-kw's 14 errors** (S2 confusion) are all on two bases. §3 shows that 7 of them come from an injector artefact.
  - aes: 7 runs predicted missing_file.
  - dynamic_node: 7 runs predicted `unknown`.
- **M-tpl, S-design.** The main confusions are:
  - missing_file → floorplan_capacity: 12 runs. The two cases inspected are the missing-PDN-script variant, which fails during floorplanning;
  - timeout → out_of_memory: 8 runs;
  - syntax_error → sdc_error or missing_file: 4 + 4 runs.
- **M-tpl, S-variant.** Held-out out-of-memory variants are mostly called timeout (21 of 39) or routing_resources (12). Held-out timeout variants are mostly called out_of_memory (23 of 39).
- **By origin (S-design):**

  | Origin | n | B-kw | M-tpl |
  |---|---|---|---|
  | generated | 169 | 1.000 | 0.890 |
  | ORFS | 126 | 0.911 | 0.821 |

**P3: evidence lines.** These are the top-3 lines a method would show an engineer. A run is a hit if one of them states the root cause (`rules.GOLD`).
- 13 runs whose logs contain no gold line are excluded (all on aes and dynamic_node; see §3). That leaves n = 282.

| Class | M-tpl hit rate | B-ev hit rate |
|---|---|---|
| syntax_error | 1.00 | 1.00 |
| elaboration_error | 0.78 | 0.73 |
| missing_file | **0.74** | 0.20 |
| sdc_error | 0.00 | 0.00 |
| floorplan_capacity | 0.00 | 0.00 |
| routing_resources | 0.00 | 0.80 |
| out_of_memory | 0.00 | 1.00 |
| timeout | 0.08 | 0.00 |
| **all** | **0.372** | **0.440** |

- Both methods fail on sdc_error and floorplan_capacity, where the root-cause line is followed by a Tcl traceback and make's `Error 1`/`Error 2` lines.
- M-tpl wins clearly only on missing_file.
- For reference (S4), B-kw's single triggering line is a gold line in **95.4%** of runs. As pre-registered, this favours B-kw, because the gold patterns and the rules share an author.

## 3. Data-quality findings (post hoc, found while checking B-kw's errors)

1. **Injector artefact on aes: 7 runs carry the wrong label.**
   - Seven RTL-mutating faults on aes (4 syntax, 3 elaboration) copy the mutated `aes_cipher_top.v` into the overlay directory. Its `` `include "timescale.v" `` then no longer resolves.
   - So all 7 runs actually failed with `Can't open include file 'timescale.v'`, a missing-include failure, before reaching the injected error. B-kw and M-tpl both call them missing_file, which is arguably the *correct* diagnosis.
   - wrong_top (which doesn't copy RTL) and missing_file/include on aes are unaffected.
   - The dev design gcd has no relative includes, so the probe did not catch this.
   - **Sensitivity** (`scripts/exploratory_e5.py`, written to `experiments/exploratory_e5_3d6cb327b1ed3b5d.json`), dropping the 7 runs: P1 = 0.887 − 0.989 = **−0.102 [−0.126, −0.078]**, n = 288. The verdict is unchanged.
2. **dynamic_node uses a third synthesis frontend.**
   - Its ORFS config sets `SYNTH_USE_SYN = 1`, so errors read `error: expected ';'`, `… is not a valid top-level module` and `[ERROR SYN-0001] Elaboration failed`. Neither the dev logs (yosys, slang) nor the rules contain these.
   - B-kw returns `unknown` on all 7 of these RTL-frontend runs.
   - This is a genuine generalisation miss for hand-written rules, the kind a learned model is supposed to catch. **M-tpl does no better.** It calls all 7 runs sdc_error, because the only lines it recognises in them are the Tcl traceback (`invoked from within`, `(procedure "sv_elaborate" line 2)`), which it learned from SDC errors. Those traceback lines are also its evidence.
   - The GOLD patterns miss these lines too, which is why 6 of the 13 P3 exclusions are on dynamic_node. The other 7 are the aes runs above.
   - The 2 masked dynamic_node elaboration faults are probably the same frontend behaving differently. Not investigated.

## 4. Secondary results (pre-registered, reported, not judged)

**S1: other models.** Macro-F1:

| Model | S-design | S-variant |
|---|---|---|
| B-kw | 0.970 | 0.970 |
| M-tpl (LogReg) | 0.869 | 0.521 |
| M-svc (linear SVM, same features) | 0.918 | 0.616 |
| M-raw (TF-IDF word n-grams) | 0.812 | 0.520 |

- On S-design, M-svc − M-tpl = +0.050 [+0.031, +0.073] and M-raw − M-tpl = −0.057 [−0.085, −0.028].
- No learned model comes within 0.05 of B-kw.

**S3: anomaly and novel-class detection.**
- (a) Template novelty, failed vs clean, S-design: **AUROC 0.811**. With only 13 clean runs this is a single number, not a CI.
- (b) Novel class, scored by 1 − max class probability with class c held out of training: **AUROC 0.614**. That is weak, so a confidently wrong prediction is the usual failure mode.

**S5: the 12 natural D1 failures** (`data/d2/natural/`). M-tpl is trained on all 295 labelled D2 runs; B-kw is applied as is. This is a sanity check only: these logs were read before their labels were fixed.

| Label | n | B-kw correct | M-tpl correct |
|---|---|---|---|
| timeout | 7 | 7 | 7 |
| floorplan_capacity | 3 | 3 | 1 (both gcd/sky130hd runs → out_of_memory) |
| novel (tage_update: ORFS's LEC cannot load its SRAMs) | 2 | B-kw says `unknown`, the right answer for a novel failure | M-tpl says timeout, max probability 0.39 |

- M-tpl's top-3 evidence for the natural timeouts is wire-length and placement-progress rows, never the `Terminated` line. B-kw's triggering line is the `Terminated` or `wait: No child processes` line every time.
- M-tpl's maximum probability on the novel runs (0.39) lies inside the range of its correct natural predictions (0.31–0.59), so a probability threshold would not have flagged them.

## 5. Why the learned model loses (exploratory, post hoc)

`scripts/exploratory_e5.py` (same output file) fits M-tpl on all 295 labelled runs (931 templates; the mean run has 1,280 lines) and lists the top-weighted templates per class. It also reports where the templates of that class's gold lines rank.

1. **Masking erased the out-of-memory signal.**
   - The OOM kill shows up in the log as make's `Error 247`. Drain's number masking turns it into `Error <*>`, the same template as every ordinary `Error 2`.
   - The OOM gold template ranks **780th of 931** for its class. The top OOM templates are the global-placement progress table (`<*> | <*> | <*> | …`), `[InitialPlace] Iter …` and `elapsed time … memory = <*> (MB)`.
   - In other words the model recognises OOM by *the stage the run reached when it was killed*.
2. **The model weights stage-reached and traceback lines above the error message.**
   - The top timeout template is `Total wire length on LAYER <*> = <*> um.`, which means the run reached routing.
   - The top floorplan_capacity and sdc_error templates are the generic Tcl traceback (`invoked from within`, `(file <*> line <*>)`, `(procedure <*> line <*>)`). These appear in many classes.
   - The gold template ranks in the top 3 for 5 of 8 classes (syntax 1, elaboration 1, missing_file 1, routing 2, timeout 3), 5th for floorplan, 12th for sdc and 780th for OOM. Classification can still work when a gold template is weighted highly.
   - **Evidence, however, breaks easily.** It keeps the 3 highest-weighted *distinct lines*. A progress-table template has dozens of distinct lines per run (every row differs), so one such template above the gold one fills all 3 slots. That explains routing (gold rank 2) at a 0.00 hit rate.
3. **The shortcut breaks on unseen variants.**
   - Out-of-memory and timeout variants differ only in how much memory or time they get, so a held-out variant stops at a different stage than the training variants. That explains OOM F1 0.12 and timeout 0.26 under S-variant.
   - For RTL-frontend classes, the variants differ in which message is printed. A held-out variant's message has no learned template at all.
4. **Every D2 class has a near-unique literal message.**
   - A one-line regex per class captures it. A bag of ~1,000 templates dilutes it among progress and traceback lines that are far more frequent.
   - So the corpus favours keyword rules by construction. That is a property of injected faults: real failures are messier (threat 1 in §11).

## 6. What this changes (proposals only; any new test needs its own pre-registration)

- **Product:** diagnosis should be **rules first**, with every prediction backed by its triggering line (95% gold hit rate on D2). Learned scoring is used only where the rules say `unknown`:
  - template novelty, AUROC 0.81, to flag that a run looks abnormal;
  - nearest past runs, to suggest what it resembles.
  - On D2 the rules failed only on an unseen frontend, where the learned classifier failed too (§3). So the fallback should *flag* a run as unfamiliar, not guess a class for it. Whether novelty scoring flags those particular runs was not measured.
- **Model fixes, each a pre-registered hypothesis for a D2 v2, not something to tune on D2 v1:**
  - mask only measurements, keeping exit codes and message IDs (`Error 247`, `GPL-0301`);
  - build features and evidence only from lines of error or warning severity, plus make/kill lines;
  - drop the stage-progress templates, or represent stage-reached explicitly as a feature;
  - rank evidence by template rarity in clean runs instead of by class coefficient.
- **Corpus fixes:**
  - put the original source directory on the include path of RTL overlays (the aes artefact);
  - add SYN-frontend bases, since ORFS is moving designs to it;
  - drop or rescale `no_whitespace` and `three_layers`, which mostly do not manifest.
- **Rules fix:** add the SYN-frontend messages to B-kw and GOLD. This is a new rules version, to be judged on new data only.

## 7. Limitations

- The corpus has 13 design groups, one tool image and one host type, and its faults are injected. Injected faults are cleaner than real failures, which favours keyword rules.
- 7 labels are wrong (§3). The sensitivity check shows the verdict does not depend on them.
- The slang frontend prints one identical line for every RTL fault, so 2 bases cover only 17 of the 26 faults.
- The keyword rules were written by the same author as the gold patterns (S4), and from a dev design on the same tool image.
- S5 has 12 runs and its labels were fixed after reading the logs.
