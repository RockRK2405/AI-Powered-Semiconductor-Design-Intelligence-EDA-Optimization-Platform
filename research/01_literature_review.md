# 01 — Literature Review: AI/ML for EDA (first pass)

**Scope:** what published work already does in each area SiliconAI touches, and what
that means for us. Reference IDs (R##) point to `08_research_references.md`.

**Honesty note:** this review is built from abstracts, official pages and search
summaries, not full-text reading. Numbers attributed to papers are *the authors'
reported results*, which we have not reproduced. Analysis paragraphs marked **[Our analysis]**
are my interpretation, not findings from the papers.

---

## 1. The big picture

The 2021 TODAES survey (R01) organizes ML-for-EDA into four types of use:
1. **Decision-making inside traditional algorithms** (for example, choosing heuristics),
2. **Performance prediction** (predicting a tool's outcome without running it),
3. **Black-box optimization** (tuning flow parameters),
4. **Automated design** (generating designs or solutions).

Since 2023, a fifth stream has grown quickly: **LLMs for EDA**. It covers script
generation, RTL generation, assistants, log/bug analysis and agentic flows (R03, R04, R05, R55–R59).

**[Our analysis]** Almost every SiliconAI module is a *performance prediction*
or *diagnosis* problem. The literature has strong precedent for predicting **quality of
results** (area, delay, congestion, slack). It has much less public work on predicting the
**cost of running the flow** (runtime, memory) and on **diagnosing flow failures from logs**.

## 2. Pre-synthesis / RTL-level PPA prediction (Module 3–4)

| Work | What it does *(abstract-level)* | Notes for us |
|---|---|---|
| SNS (R20), ISCA 2022 | Converts designs into graphs and predicts area, power and timing by predicting **circuit-path** characteristics, then aggregating them. Authors report 2–3 orders of magnitude speedup over synthesis. | Deep learning, path-based. Code archived. |
| SNS v2 (R21), MICRO 2023 | Two-level hierarchical GNN for larger designs; focuses on transferability. | Shows that **transfer to unseen designs** is the hard part. |
| MasterRTL (R22), ICCAD 2023 | Converts HDL into a bit-level **Simple Operator Graph (SOG)**; separate models for timing, power and area; evaluated on **90 designs**. | The strongest published reference for RTL→PPA. TCAD extension (R23) adds cross-node transfer. |
| R24 (2025 preprint) | Reuses the SOG idea; reports validation on 147 designs. | Confirms SOG is becoming a standard representation. |
| HLS QoR (R25) | Predicts post-route timing and resources from HLS behavioural code. | Same idea one abstraction level higher. |

**[Our analysis]**
- RTL→PPA prediction is a **crowded, well-resourced area** with GNN-based state of the art.
  A student project will **not** beat MasterRTL/SNS on their own benchmarks, and should
  not claim novelty here.
- The useful role for SiliconAI is a **reproducible, explainable baseline**: tabular features
  from Yosys `stat` plus AST features, with gradient-boosted trees and group-aware evaluation.
  It also produces **features that feed the cross-stage models** (see §4).
- Label quality matters: our area and timing labels must come from real tools (Yosys/ABC +
  a Liberty file, OpenSTA/OpenROAD), not formulas.

## 3. Physical-design prediction: congestion, routability, timing (Module 6)

| Work | What it does *(abstract-level)* |
|---|---|
| RouteNet (R30), ICCAD 2018 | FCN-based CNN; predicts overall routability without global routing, or DRC hotspot locations; uses features like RUDY. |
| PROS (R34), ICCAD 2020 | FCN predicting global-routing congestion from placement; designed to run inside a commercial tool. |
| Painting on Placement (R35) | Treats congestion forecasting as image-to-image translation (cGAN). |
| Timing-engine GNN (R31), DAC 2022 | GNN that propagates like an STA engine to predict pre-routing arrival time and slack. |
| PreRoutGNN (R32), E2ESlack (R33) | Follow-ups addressing error accumulation on long paths and end-to-end slack. |
| Robustness study (R36) | Shows ML congestion predictors can change a lot under perturbations that do not change real routing. Argues for evaluation beyond train/test metrics. |

**[Our analysis]**
- Spatial congestion prediction is **image/graph learning on per-tile data**. It needs
  placement-level data dumps and usually a GPU. CircuitNet (R10/R11) already provides
  such data.
- **Design-level risk** classification ("will this run have DRC violations or negative
  slack at this utilization and clock?") is much more feasible for us. It uses
  tabular metrics that OpenROAD reports (METRICS2.1, R40).
- R36 is directly relevant to our uncertainty theme: point predictors in EDA can be
  confidently wrong.

## 4. Flow metrics, flow tuning and runtime/resource prediction (Module 1)

| Work | What it does *(abstract-level)* |
|---|---|
| METRICS2.1 + AutoTuner (R40), ICCAD 2021 | Standard hierarchical JSON for RTL-to-GDS metrics (per stage: flow, design, timing). AutoTuner uses derivative-free optimization to tune ORFS flow parameters. |
| DATC RDF-2021 (R41) | Robust open design flow infrastructure built around OpenROAD. |
| ORFS AutoTuner docs (R42) | Ray-based tuning and sweeps over ORFS parameters; METRICS2.1 records each trial. |
| ORFS-agent (R43), 2025 preprint | LLM-driven parameter search on ORFS; reports beating Bayesian optimization with fewer flow runs. |
| BOiLS (R44), DATE 2022 | Bayesian optimization of ABC synthesis sequences on EPFL benchmarks. |
| EDALearn (R13), ICCAD 2024 | Open, reproducible synthesis-to-signoff benchmark covering placement, routing, timing, power and IR drop. Criticizes CircuitNet for a closed technology node and OpenABC-D for being synthesis-only. |
| EDA-schema (R14), GLSVLSI 2024 | Graph schema and dataset: 20 IWLS'05 designs × 49 runs on SKY130 with OpenROAD (counts from a DAC'24 BoF slide). |
| EDA-Schema-V2 (R15), 2026 preprint | Multimodal, multi-stage extension across 4 open PDKs; reports 7,776 instances from 18 circuits with sweeps over clock, utilization and aspect ratio. Notes that METRICS2.1 reports only aggregate data. |
| IICPilot (R45), 2024 preprint | LLM multi-agent backend framework on OpenROAD/iEDA. A search summary says its container agent forecasts EDA task runtimes from RTL size and machine configuration to pick cheap machines. **Not verified in the full text.** |
| FPGA logic-emulation ML (R46), TODAES | Predicts Vivado P&R QoR, **runtime and memory** to choose mapping parameters. |
| HPC job prediction (R47, R48) | A mature literature on predicting batch-job runtime and memory. R48 stresses **leakage-safe** features: only use information available at submission time. |

**[Our analysis] — this is the most important finding of Phase 0**
- QoR prediction and flow tuning on OpenROAD are well studied. **Predicting the runtime
  and peak memory of each open-flow stage** appears only as a side component (R45, R46).
  The first pass found **no dedicated, openly reproducible study** of it with
  design-grouped evaluation. This is a *search result, not proof of absence* (see
  verification backlog in `08`).
- The HPC literature (R47, R48) gives us a ready methodological frame: features available
  **before** a stage starts, leakage-safe splits, and asymmetric costs of under-prediction.
- Open datasets (EDALearn, EDA-schema) focus on QoR labels. Whether they record **per-stage
  wall time and peak memory** is not confirmed. If they don't, we must **generate our own runs**
  anyway. We need to do that for the logs too (§5).

## 5. Log parsing and failure diagnosis (Module 2)

| Work | What it does *(abstract-level)* |
|---|---|
| Drain (R50), ICWS 2017 | Fixed-depth parse tree for online log template extraction. The authors report the best accuracy on 4 of 5 datasets. |
| Loghub-2.0 evaluation (R51) | Large-scale re-evaluation; Drain remains among the strongest, but accuracy drops on harder data. |
| LLM-aided explanations of synthesis errors (R52) | Extracts error messages from Vivado/Quartus synthesis logs with regex, then uses an LLM to explain them. |
| Berkeley report (R53), 2025 | GPT-4o for synthesis log analysis; notes that earlier approaches only catch explicitly marked error lines, one error at a time. |
| EDA-Debugger (R54), ISQED | Multi-agent LLM with RAG over EDA knowledge; diagnoses OpenROAD/OpenLane log issues. |
| ChipNeMo (R55) | Domain-adapted LLMs; one of its three tasks is bug summarization and analysis. |

**[Our analysis]**
- General log parsing (Drain) is solved well enough to *reuse*. The EDA-specific gap is
  **labelled data**. I found no public, labelled corpus of open-EDA-tool failure logs
  with a failure-category taxonomy.
- Recent EDA log work is **LLM-first**. A **classical, measurable pipeline**
  (template mining → features → classifier → anomaly score → evidence lines) with an
  LLM only as an optional explanation layer is easier to evaluate and fits our
  "evidence over generated text" principle.
- We can create labels **by construction**: deliberately inject known faults into flow
  runs (missing file, syntax error, impossible clock, over-utilization, bad SDC, memory
  limit) and record the injected cause as ground truth. This is clean, reproducible and
  honest. It is still a *controlled* distribution, not industrial reality, and we must say so.

## 6. Verification and regression intelligence (Module 5)

| Work | What it does *(abstract-level)* |
|---|---|
| DV with ML "better than random" (R60, R61) | Reinforcement-learning-steered constrained-random stimulus improves functional coverage over random on a cache controller and RISC-V Ariane. |
| Coverage-directed test selection (R62, R63) | Supervised learning on coverage feedback selects or prioritizes generated tests likely to increase coverage; evaluated on an industrial design (Infineon). |
| Software TCP (R64–R66) | ML test-case prioritization in CI, measured with **APFD**; industrial case study at Salesforce. SLR (R65) maps the field. |

**[Our analysis]**
- Hardware verification ML focuses on **coverage closure**. Prioritizing **regression
  runs by failure likelihood**, the software-CI framing, has little *public* hardware
  literature (first-pass finding).
- The data problem is serious: real regression histories are proprietary. A defensible
  student approach is **mutation-based history generation**. Take open designs that
  have testbenches, inject RTL mutants (simulating bugs and changes), run the test suite
  with Icarus/Verilator, and log pass/fail and runtime per test per "commit". The data
  must be clearly labelled *simulated history*.
- Evaluation metric: **APFD** (and APFDc, cost-aware) against baselines (random,
  historical failure rate, shortest-first). This is standard and interview-defensible.

## 7. LLMs, RAG and copilots (Module 8)

- ChipNeMo (R55): domain adaptation (tokenizer, continued pretraining, alignment) plus RAG.
  The authors report that their 70B model beats GPT-4 on an engineering-assistant chatbot and on
  EDA script generation.
- OpenROAD ecosystem: ORAssistant (RAG over OpenROAD docs, R56), OpenROAD Agent
  (self-correcting script generation, R57), EDA Corpus (R17).
- RTL generation benchmarks: VerilogEval (R58), RTLLM (R59).

**[Our analysis]** Doc-QA copilots for OpenROAD **already exist** (R56). A SiliconAI copilot
is only worth building if it is grounded in **this project's own run data**: metrics DB,
predictions with uncertainty, and log evidence lines. Every claim must be traceable to a
stored row or log line. The copilot is the **last** phase and depends on everything else.

## 8. Uncertainty quantification in EDA ML

- Conformalized quantile regression has been applied to **post-silicon Vmin
  prediction** with coverage guarantees (R70, DATE/DAC 2024).
- The first pass found **no** applications of conformal prediction to **EDA runtime, PPA, or
  physical-design prediction**. This needs a systematic proceedings search before we claim it.
- R36 shows that EDA point predictors can be confidently wrong under shift. This is the motivation
  for calibrated intervals and abstention.

**[Our analysis]** Split-conformal and conformalized quantile regression are cheap, model-agnostic
and simple to explain in an interview. They come with a finite-sample coverage guarantee under
exchangeability. The interesting research question for us is **whether coverage holds under
design shift**: leave-design-out evaluation breaks exchangeability. How to restore it is
a legitimate, testable question (for example, group-conditional / Mondrian conformal, or
out-of-distribution scores that trigger abstention).

## 9. Summary of implications

| Area | Literature maturity | SiliconAI's role |
|---|---|---|
| RTL→PPA | High (GNN SOTA) | Reproducible tabular baseline; source of cross-stage features |
| Congestion/timing maps | High (CNN/GNN, needs placement dumps) | Design-level risk classification only |
| Flow tuning | High (AutoTuner, BO, agents) | Consumer, not competitor |
| **Stage runtime/memory prediction (open flow)** | **Low, publicly** | **Primary contribution candidate** |
| **Labelled open-EDA failure logs** | **Low** | **Secondary contribution candidate** |
| Regression prioritization for RTL tests | Low-medium (coverage closure is high) | Third-tier module with simulated history |
| **UQ/conformal for EDA predictions** | **Very low (one adjacent example)** | **Cross-cutting methodological contribution** |
| Doc-QA copilots | Medium (ORAssistant etc.) | Evidence-grounded over our own data only |
