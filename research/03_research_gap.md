# 03 — Research Gaps (candidate)

Each gap is a **hypothesis about the literature** drawn from a first-pass search. Gaps
G1 and G4 still need the systematic proceedings search listed in `08` (verification
backlog) before we can state them in a paper or README as established.

---

## G1 — Open, reproducible prediction of per-stage EDA *flow cost* (runtime and peak memory)

- **Supporting sources:** R40/R42 (METRICS2.1 records flow metrics, but tuning
  focuses on QoR); R45 (IICPilot mentions runtime forecasting only as a component); R46
  (runtime/memory prediction for proprietary Vivado); R47/R48 (mature HPC job-prediction
  methodology); R15 (METRICS2.1 is aggregate-only).
- **Existing approaches:** QoR prediction (R20–R33), flow tuning (R40–R44), HPC job runtime
  prediction for generic jobs (R47, R48).
- **Why it matters:** Compute and licences are major cost drivers in chip design.
  Knowing before launch that a placement run will need about 6 GB and about 40 minutes enables
  scheduling, right-sized machines and early aborts of runaway runs.
- **Our proposed approach:** generate our own ORFS runs over designs × parameter sweeps.
  Predict wall time and peak RSS for each stage from features available **before that stage starts**
  (RTL features, earlier stages' metrics, configuration, allocated CPUs).
- **Feasibility:** High for small and medium designs on 4 CPUs / 15 GB, *if OpenROAD runs
  here* (see `07`). Dataset size is bounded by compute; target 600–1,500 stage-level
  rows in the first iteration.
- **How we test it:** leave-design-out (GroupKFold) MAE/MAPE/R² against baselines
  (mean-per-stage, linear on cell count, design-history lookup). Measure underestimation rate
  separately, because under-allocation is the costly error.

## G2 — Quantified value of *cross-stage* information for prediction

- **Supporting sources:** R13 and R15 provide multi-stage data. Pre-synthesis predictors (R22)
  and pre-routing predictors (R31) each work at **one** stage boundary.
- **Gap:** I found no study that *measures*, on one consistent open dataset, how much each
  additional observed stage (RTL → synth → floorplan → place → CTS) improves prediction
  of later-stage cost and QoR, **with calibrated uncertainty** at each point.
- **Our approach:** a *progressive predictor*, one model per "knowledge horizon" *h*.
  It uses only features observable by stage *h* and predicts all later targets.
- **How we test it:** a learning curve of error and interval width against horizon *h*,
  leave-design-out. The hypothesis **H2** is that error and interval width fall
  monotonically with *h*. The marginal gain per stage is the result.
- **Feasibility:** High, because it reuses the G1 dataset. This is the cheapest, cleanest
  experiment in the project.

## G3 — Labelled corpus and measurable classical diagnosis for open-EDA failure logs

- **Supporting sources:** R50/R51 (generic parsers; no EDA labels); R52–R54 (EDA log
  diagnosis is LLM-first, and evaluation is mostly qualitative as far as the abstracts show).
- **Gap:** no public, labelled corpus of OpenROAD/Yosys failure logs with a category
  taxonomy was found.
- **Our approach:** **fault injection by construction.** We define a taxonomy (syntax,
  elaboration, missing file, constraint/SDC, timing infeasible, over-utilization/placement,
  routing congestion, resource/OOM, timeout, tool crash) and an injector for each class.
  We run the flow and store the logs with the injected class as the label. Then we train
  Drain templates → TF-IDF/template-count features → linear/GBM classifier, plus an
  anomaly detector trained only on successful runs.
- **How we test it:** macro-F1 per class, held out by **design** and by **fault
  variant**; top-k evidence-line precision (does the highlighted line contain the
  root-cause message?); anomaly AUROC. Compare against a keyword/regex baseline.
- **Limitation to state:** injected faults are cleaner than real-world failures, and some real
  failure modes (license, NFS, tool bugs) are not reproducible. That external-validity
  limit goes in every write-up.

## G4 — Calibrated, shift-aware uncertainty and abstention for EDA predictions

- **Supporting sources:** R70 (conformal applied to post-silicon Vmin, the only EDA-adjacent
  example found); R36 (EDA predictors brittle under perturbation); R71 (theory).
- **Gap:** no applications of conformal prediction to EDA runtime or PPA prediction were found.
  The key open issue is **coverage under unseen-design shift**.
- **Our approach:** split-conformal and CQR wrapped around G1/G2 models; Mondrian
  (group-conditional) variants by design-size bucket; an OOD score (for example,
  distance to training designs in feature space) that triggers **abstention**
  ("insufficient evidence — run the stage").
- **How we test it:** empirical coverage against nominal (90%) under random split compared with
  leave-design-out; interval width; selective-prediction risk–coverage curves.
- **Feasibility:** High, because it is cheap to compute. The scientific risk is small *n*
  (few unique designs): coverage estimates will be noisy, so we report confidence intervals
  on coverage.

## G5 — Failure-likelihood regression ordering for open RTL test suites

- **Supporting sources:** R62/R63 (coverage-directed selection); R64–R66 (software TCP with APFD).
- **Gap:** public studies of regression-*failure* prioritization (APFD) on RTL simulation
  were not found in the first pass.
- **Our approach:** mutation-generated histories on open designs with testbenches; features
  are test history, test–module affinity and the diff touching modules. Ranker is logistic/GBM.
- **How we test it:** APFD / APFDc against random, failure-rate and shortest-first baselines,
  on held-out "commits".
- **Feasibility:** Medium. It needs designs with meaningful test suites, and mutation realism
  is debatable.

## G6 — Evidence-grounded copilot over a project's own run database

- **Supporting sources:** R55–R57 (doc-centric or proprietary).
- **Our approach:** tool-calling over the SiliconAI DB and models. Every sentence is tagged
  OBSERVED / PREDICTED (± interval) / INFERRED / RECOMMENDED, with citations to row IDs or log lines.
- **How we test it:** a small hand-written question set with gold evidence; measure
  citation precision and unsupported-claim rate.
- **Feasibility:** Medium. It needs an LLM API key (cost) or a local model, and comes last.
