# 04 — Novelty Analysis

**Ground rule:** SiliconAI is *not* novel merely because it combines ML, NLP, EDA and a
dashboard. We claim a contribution only for a **specific, measurable question** that
our experiments answer, and only once the literature check in `08` is complete.

## 1. Scoring the five candidate directions

Scores are 1 (poor) to 5 (strong). "Originality" reflects the first-pass literature
search only.

| # | Direction | Originality | Feasibility | Engineering value | Evaluation difficulty (5 = easy) | Data availability | Student suitability | Interview value | **Total** |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Cross-stage EDA intelligence (G2) | 3 | 5 | 4 | 5 | 4 (own runs) | 5 | 5 | **31** |
| 2 | Joint prediction + diagnostics | 2 | 3 | 4 | 2 | 3 | 3 | 4 | 21 |
| 3 | Uncertainty-aware recommendations (G4) | 4 | 5 | 4 | 4 | 4 | 4 | 5 | **30** |
| 4 | Evidence-grounded copilot (G6) | 2 | 3 | 4 | 2 | 3 | 3 | 4 | 21 |
| 5 | Resource-aware workflow optimization (G1) | 3 | 4 | 5 | 4 | 4 | 4 | 5 | **29** |
| — | Fault-injected EDA log corpus (G3) | 3 | 4 | 4 | 4 | 4 | 5 | 4 | 28 |
| — | RTL→PPA prediction | 1 | 4 | 3 | 4 | 3 | 4 | 3 | 22 |
| — | Spatial congestion prediction | 1 | 2 | 3 | 3 | 3 (CircuitNet) | 2 | 3 | 17 |

Why the lower-ranked ones lose:
- **Direction 2 (joint)** is hard to evaluate. "Better decision support" needs user studies
  or a proxy we would have to invent. Joint value falls out of the integration anyway,
  without being a research claim.
- **Direction 4 (copilot)** is mostly engineering. Doc copilots for OpenROAD already exist
  (R56). It remains a *feature*, not the contribution.
- **RTL→PPA and congestion maps** are mature fields with GNN/CNN SOTA (R20–R36).

## 2. Recommended contribution (needs your approval)

> **Primary:** *Uncertainty-aware, cross-stage prediction of open-source RTL-to-GDS flow
> cost (per-stage runtime and peak memory) and outcome risk, evaluated on unseen designs.*
>
> This combines Directions 1, 3 and 5 (gaps G1 + G2 + G4) into **one experimental
> question family** on **one dataset we generate ourselves**.

**Supporting contribution:** a fault-injected, labelled open-EDA log corpus with an
evidence-linked classical diagnosis baseline (G3).

**Platform features (not claimed as research):** RTL feature extraction / PPA baseline,
verification prioritization (G5), decision engine, copilot (G6), dashboard.

### Testable hypotheses

| ID | Hypothesis | Metric | Falsified if |
|---|---|---|---|
| H1 | Learned models predict per-stage runtime and peak memory on **unseen designs** better than simple baselines (per-stage mean; log-linear on cell count). | Leave-design-out MAE on log-runtime, MAPE, R²; underestimation rate | GBM is not better than the log-linear baseline beyond noise (paired bootstrap CI includes 0) |
| H2 | Each additional observed stage reduces error and interval width for downstream targets. | Error and interval width vs. horizon *h* | No significant reduction after the synthesis horizon |
| H3 | Split-conformal intervals that reach nominal coverage under random splits **under-cover** under leave-design-out; a group-aware or OOD-gated variant restores coverage with acceptable width. | Empirical coverage (± CI), mean width, risk–coverage curve | Either no under-coverage appears (still a valid, reportable result) or no variant restores it |
| H4 | Abstaining on the top-*k*% OOD predictions reduces large-error rate more than random abstention. | Selective risk at fixed coverage | No improvement over random abstention |
| H5 | (Supporting) Template + classifier diagnosis beats a keyword baseline on held-out designs and fault variants, and highlights a root-cause line in the top-3. | Macro-F1; top-3 evidence precision | Keyword baseline within CI |

Note: negative results for H2–H4 are **still publishable-quality findings** for a portfolio.
The experiment is the contribution, not a particular outcome.

## 3. Why this is defensible in an interview

- **Narrow and measurable:** each claim is a number with a baseline and a CI.
- **Reproducible:** anyone can regenerate the dataset from our scripts and open PDKs.
- **Uses real tools:** labels come from Yosys/OpenROAD runs, not formulas.
- **Honest about scope:** "small designs, open PDKs, one machine type" is stated up front.
- **Shows maturity:** group-aware splits, leakage analysis and calibration are what senior
  ML/EDA interviewers probe.

## 4. Threats to the novelty claim

1. **Hidden prior work.** A paper on ML runtime prediction for OpenROAD or OpenLane may exist
   and simply not have surfaced in the search. *Mitigation:* systematic proceedings search (TODO P0-R2).
   If found, we reposition as a replication + UQ extension.
2. **Too few unique designs** (~15–30) → wide CIs. *Mitigation:* parameterized RTL
   generators to add structural diversity, *clearly labelled as generated RTL with real tool
   labels*; report CIs.
3. **Single-machine runtimes** don't transfer to other hardware. *Mitigation:* say so;
   normalize by a calibration benchmark; treat cross-machine transfer as future work.
4. **Runtime noise.** Repeated runs vary. *Mitigation:* run a subset ≥3 times to estimate the
   noise floor. No model can beat it, and we report it.
