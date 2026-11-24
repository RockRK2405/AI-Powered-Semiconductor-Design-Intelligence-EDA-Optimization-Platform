# 02 — Existing Solutions and How SiliconAI Differs

Reference IDs → `08_research_references.md`. Commercial information is limited to
what is public. Vendor marketing claims are **not** treated as evidence.

## 1. Academic and open-source systems

| System | What it does | What it does not do | Strengths | Limitations (for our purposes) |
|---|---|---|---|---|
| **OpenROAD + ORFS** (T02, T03) | Open RTL-to-GDS flow (Yosys → floorplan → place → CTS → route → finish) on GF180, SKY130, Nangate45, ASAP7. Emits METRICS2.1 JSON. | No predictive analytics; no log diagnosis. | De facto open flow; reproducible; permissive licenses for scripts (BSD-3). | Heavy toolchain; we must still check that it runs in our environment. |
| **AutoTuner** (R40, R42) | Ray-based flow hyperparameter tuning recording PPA per trial. | Does not predict runtime or failures before running; optimizes QoR. | Integrated with ORFS. | Every trial is a real flow run, so it is costly. |
| **ORFS-agent** (R43) | LLM agent iteratively tuning ORFS parameters. | No calibrated predictions; no failure taxonomy. | Shows LLM tool-use viability. | Preprint; costs LLM calls. |
| **IICPilot** (R45) | LLM multi-agent backend automation; DSE; container resource allocation; exception handling. | Public evaluation of its runtime predictor not confirmed. | Closest to "intelligence layer over open EDA". | Preprint; LLM-centric; methodology of the runtime component unclear from abstract. |
| **CircuitNet 1/2** (R10, R11) | Large datasets for congestion, DRC, IR drop and timing; training scripts. | No runtime labels confirmed; N28 is a closed node, so not reproducible (per R13). | Scale. | Image-based tasks; GPU-oriented. |
| **OpenABC-D** (R12) | 870k AIGs from 1,500 ABC synthesis runs on 29 designs. | Synthesis-only. | Large; open. | 1.4 TB full release (18.6 GB Zenodo subset). |
| **EDALearn** (R13) | Reproducible synthesis-to-signoff benchmark on open flows. | Runtime/memory labels **not confirmed** (TODO). | Reproducible end-to-end; multiple stages. | Need to inspect repo and license. |
| **EDA-schema / V2** (R14, R15) | Graph data model; IWLS'05 on SKY130 (V1); 4 PDKs, sweeps over clock/util/aspect (V2). | Unknown for runtime labels. | Parameter sweeps match our data strategy. | V2 is a 2026 preprint. |
| **MasterRTL / SNS** (R20–R23) | RTL→PPA with SOG / path GNNs. | Flow cost, logs and verification are out of scope. | State of the art accuracy. | GNN complexity; SNS code archived. |
| **logparser / Drain** (R50) | Generic log template mining. | No EDA taxonomy, labels or diagnosis. | Mature, open source. | Domain-agnostic. |
| **EDA-Debugger** (R54), Berkeley log work (R53), R52 | LLM-based EDA log explanation and diagnosis. | No public labelled corpus or classical baselines confirmed. | Practical framing. | Evaluation is mostly qualitative or expert-judged (to be confirmed). |
| **ORAssistant / OpenROAD Agent** (R56, R57) | RAG doc-QA; script generation with self-correction. | Not grounded in a user's run history. | Open source; OpenROAD-specific. | Doc-centric. |
| **ChipNeMo** (R55) | Domain-adapted LLM; chatbot, script generation, bug summarization. | Not open; NVIDIA-internal data. | Shows value of domain adaptation + RAG. | Not reproducible by us. |
| **ML-for-DV** (R60–R63) | RL / supervised test steering and selection for coverage. | Regression-failure prioritization with APFD on public RTL not found. | Industrial evidence (R62). | Proprietary data. |

## 2. Commercial landscape (public information only)

Major EDA vendors advertise ML-driven flow optimization, verification analytics and
LLM assistants. R46's source also notes that Vivado 2021.2 uses ML internally. **We have
not reviewed vendor materials in this pass**, and we will not cite marketing numbers.
The relevant facts for us:
- Commercial ML features exist **inside** proprietary tools and are not reproducible or inspectable.
- Their training data (customer runs) is unavailable to academia. This is the core reason
  open datasets (R10–R15) exist.

## 3. Student and GitHub projects

Searches surface many OpenLane/Sky130 tutorial repositories and small "ML congestion
predictor" repositories. These typically:
- train on one dataset (usually CircuitNet) with a random split (design-level leakage risk);
- report a single R²/accuracy with no baseline or uncertainty;
- have no end-to-end data generation.

**[Our analysis]** Beating this on *rigour*, not on model complexity, is
achievable and is what interviewers probe: group splits, baselines, calibration and
honest limitations.

## 4. Where SiliconAI differentiates (proposed, not yet demonstrated)

1. **Own reproducible data engine.** Every label comes from a scripted, versioned open-flow
   run with recorded tool versions, parameters, wall time, peak RSS and logs.
2. **Flow-cost prediction as a first-class target.** Per-stage runtime and memory, not only QoR.
3. **Cross-stage progressive prediction.** Predictions are refined as each stage completes,
   and we measure how much each stage's information helps.
4. **Calibrated uncertainty with abstention**, evaluated under unseen-design shift.
5. **Fault-injected, labelled open-EDA log corpus** with classical, measurable diagnosis
   that links back to log lines.
6. **Evidence-grounded copilot** over our own database (last phase).

None of these is claimed as "first". `04_novelty_analysis.md` ranks them and states what
evidence would make each one defensible.
