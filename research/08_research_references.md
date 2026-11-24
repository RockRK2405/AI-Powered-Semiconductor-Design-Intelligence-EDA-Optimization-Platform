# 08 — Consolidated Research References

**Status:** Phase 0, first pass (2026-11-24).
**How this list was built:** targeted web searches. Every entry below was found
by a search, with a link to a primary or official source. **I have not read the full
text of these papers.** Facts marked *(abstract-level)* come from abstracts, official
pages or search snippets. They are not a reading of the full paper. Results "reported by
the authors" are their claims; we have not reproduced them.

Where an author list could not be confirmed from the sources I saw, it is
written as *"authors: see DOI/URL"* instead of being guessed.

Legend: **[P]** peer-reviewed · **[pre]** arXiv preprint / not confirmed peer-reviewed ·
**[doc]** official tool documentation / repository · **[tr]** technical report / thesis

---

## A. Surveys and position papers

| ID | Citation | Type | Link |
|---|---|---|---|
| R01 | G. Huang et al., "Machine Learning for Electronic Design Automation: A Survey," *ACM TODAES* 26(5):40, 2021. DOI 10.1145/3451179 | [P] | https://arxiv.org/abs/2102.03357 |
| R02 | "Towards Machine Learning for Placement and Routing in Chip Design: a Methodological Overview," arXiv 2202.13564 (authors: see URL) | [pre] | https://arxiv.org/abs/2202.13564 |
| R03 | "The Dawn of AI-Native EDA: Opportunities and Challenges of Large Circuit Models," arXiv 2403.07257 (authors: see URL) | [pre] | https://arxiv.org/abs/2403.07257 |
| R04 | "Large Language Models for EDA: Future or Mirage?" *ACM* (DOI 10.1145/3736167) (authors: see DOI) | [P] | https://dl.acm.org/doi/10.1145/3736167 |
| R05 | "The Dawn of Agentic EDA: A Survey of Autonomous Digital Chip Design," arXiv 2512.23189 (authors: see URL) | [pre] | https://arxiv.org/abs/2512.23189 |
| R06 | "Towards the Imagenets of ML4EDA," ICCAD 2023 (arXiv 2310.10560) (authors: see URL) | [P] | https://arxiv.org/abs/2310.10560 |

## B. Datasets and benchmark infrastructure for ML-for-EDA

| ID | Citation | Type | Link |
|---|---|---|---|
| R10 | CircuitNet: "An Open-Source Dataset for Machine Learning Applications in EDA," *Science China Information Sciences* (DOI 10.1007/s11432-022-3571-8); extended in *IEEE TCAD* (DOI 10.1109/TCAD.2023.3287970) (authors: see DOI) | [P] | https://github.com/circuitnet/CircuitNet · https://arxiv.org/abs/2208.01040 |
| R11 | CircuitNet 2.0, ICLR 2024 (authors: see URL) | [P] | https://circuitnet.github.io/ |
| R12 | A. B. Chowdhury, B. Tan, R. Karri, S. Garg, "OpenABC-D: A Large-Scale Dataset for Machine Learning Guided Integrated Circuit Synthesis," arXiv 2110.11292 | [pre] | https://arxiv.org/abs/2110.11292 · https://github.com/NYU-MLDA/OpenABC |
| R13 | J. Pan et al., "EDALearn: A Comprehensive RTL-to-Signoff EDA Benchmark for Democratized and Reproducible ML for EDA Research," ICCAD 2024 (arXiv 2312.01674) | [P] | https://arxiv.org/abs/2312.01674 · https://github.com/panjingyu/EDALearn |
| R14 | "EDA-schema: A Graph Datamodel Schema and Open Dataset for Digital Design Automation," GLSVLSI 2024 (Drexel; authors: see URL) | [P] | https://github.com/drexel-ice/EDA-schema |
| R15 | "EDA-Schema-V2: A Multimodal Schema, Open Datasets, and Benchmarks for ML in Digital Physical Design," arXiv 2605.06952 (2026) | [pre] | https://arxiv.org/abs/2605.06952 |
| R16 | The EPFL Combinational Benchmark Suite (EPFL LSI) | [doc] | https://www.epfl.ch/labs/lsi/page-102566-en-html/benchmarks/ · https://github.com/lsils/benchmarks |
| R17 | EDA Corpus (OpenROAD-Assistant): a dataset of OpenROAD Q&A and script pairs | [doc] | https://github.com/OpenROAD-Assistant/EDA-Corpus |

## C. RTL-level / pre-synthesis PPA prediction

| ID | Citation | Type | Link |
|---|---|---|---|
| R20 | C. Xu, C. Kjellqvist, L. W. Wills, "SNS's not a Synthesizer: A Deep-Learning-Based Synthesis Predictor," ISCA 2022, pp. 847–859. DOI 10.1145/3470496.3527444 | [P] | https://users.cs.duke.edu/~lkw34/papers/xu-sns-isca2022.pdf · https://github.com/Entropy-xcy/sns (archived) |
| R21 | "SNS v2: Fast, Robust, and Transferable Prediction for Hardware Logic Synthesis," MICRO 2023 (authors: see URL) | [P] | https://users.cs.duke.edu/~lkw34/papers/xu-snsv2-micro2023.pdf |
| R22 | W. Fang, Y. Lu, S. Liu, Q. Zhang, C. Xu, L. W. Wills, H. Zhang, Z. Xie, "MasterRTL: A Pre-Synthesis PPA Estimation Framework for Any RTL Design," ICCAD 2023. DOI 10.1109/ICCAD57390.2023.10323951 | [P] | https://arxiv.org/abs/2311.08441 |
| R23 | "Transferable Presynthesis PPA Estimation for RTL Designs with Data Augmentation Techniques," *IEEE TCAD* 2025 (MasterRTL extension; authors: see URL) | [P] | https://users.cs.duke.edu/~lkw34/papers/fang-presynthesis-tcad2024.pdf |
| R24 | "Machine Learning Framework for Early Power, Performance, and Area Estimation of RTL," arXiv 2502.16203 | [pre] | https://arxiv.org/abs/2502.16203 |
| R25 | "Predicting Post-Route Quality of Results Estimates for HLS Designs using Machine Learning," arXiv 2205.12397 | [pre] | https://arxiv.org/abs/2205.12397 |

## D. Physical design prediction (timing, congestion, routability)

| ID | Citation | Type | Link |
|---|---|---|---|
| R30 | Z. Xie et al., "RouteNet: Routability Prediction for Mixed-Size Designs Using Convolutional Neural Network," ICCAD 2018, 80:1–80:8. DOI 10.1145/3240765.3240843 | [P] | https://research.nvidia.com/publication/2018-11_routenet-routability-prediction-mixed-size-designs-using-convolutional-neural |
| R31 | Z. Guo, M. Liu, J. Gu, S. Zhang, D. Z. Pan, Y. Lin, "A Timing Engine Inspired Graph Neural Network Model for Pre-Routing Slack Prediction," DAC 2022. DOI 10.1145/3489517.3530597 | [P] | https://github.com/TTTiko/TimingPredict |
| R32 | "PreRoutGNN for Timing Prediction with Order Preserving Partition," AAAI 2024 (arXiv 2403.00012) | [P] | https://arxiv.org/abs/2403.00012 |
| R33 | "E2ESlack: An End-to-End Graph-Based Framework for Pre-Routing Slack Prediction," arXiv 2501.07564 | [pre] | https://arxiv.org/abs/2501.07564 |
| R34 | "PROS" (FCN-based global-routing congestion prediction), ICCAD 2020. DOI 10.1145/3400302.3415662 | [P] | https://dl.acm.org/doi/abs/10.1145/3400302.3415662 |
| R35 | "Painting on Placement: Forecasting Routing Congestion using Conditional GANs," arXiv 1904.07077 | [pre] | https://arxiv.org/abs/1904.07077 |
| R36 | "On Robustness and Generalization of ML-Based Congestion Predictors to Valid and Imperceptible Perturbations," arXiv 2403.00103 | [pre] | https://arxiv.org/abs/2403.00103 |

## E. Flow tuning, design-space exploration, runtime / resource prediction

| ID | Citation | Type | Link |
|---|---|---|---|
| R40 | J. Jung, A. B. Kahng, S. Kim, R. Varadarajan, "METRICS2.1 and Flow Tuning in the IEEE CEDA Robust Design Flow and OpenROAD," ICCAD 2021 (special session) | [P] | https://vlsicad.ucsd.edu/Publications/Conferences/388/c388.pdf |
| R41 | "IEEE CEDA DATC: Expanding Research Foundations for IC Physical Design and ML-Enabled EDA" / RDF-2021, ICCAD 2021 special session (UCSD) | [P] | https://vlsicad.ucsd.edu/Publications/Conferences/386/c386.pdf |
| R42 | OpenROAD-flow-scripts AutoTuner documentation | [doc] | https://openroad-flow-scripts.readthedocs.io/en/latest/user/InstructionsForAutoTuner.html |
| R43 | "ORFS-agent: Tool-Using Agents for Chip Design Optimization," arXiv 2506.08332 | [pre] | https://arxiv.org/abs/2506.08332 |
| R44 | "BOiLS: Bayesian Optimisation for Logic Synthesis," DATE 2022 (arXiv 2111.06178) (Huawei Noah's Ark Lab; authors: see URL) | [P] | https://arxiv.org/abs/2111.06178 · https://github.com/huawei-noah/HEBO |
| R45 | Z. Jiang, Q. Zhang, C. Liu, L. Cheng, H. Li, X. Li, "IICPilot: An Intelligent Integrated Circuit Backend Design Framework Using Open EDA," arXiv 2407.12576 | [pre] | https://arxiv.org/abs/2407.12576 |
| R46 | "Improving FPGA-Based Logic Emulation Systems through Machine Learning," *ACM TODAES* (Georgia Tech; predicts P&R QoR, runtime, memory for Vivado) | [P] | https://gtcad.gatech.edu/www/papers/3399595.pdf |
| R47 | "Helping HPC Users Specify Job Memory Requirements via Machine Learning," arXiv 1611.02905 | [pre] | https://arxiv.org/abs/1611.02905 |
| R48 | "Leakage-Safe and Scheduler-Aware Machine Learning for Grid Job Runtime Prediction," arXiv 2609.13701 (2026) | [pre] | https://arxiv.org/abs/2609.13701 |

## F. Logs, failure diagnosis, LLMs for EDA

| ID | Citation | Type | Link |
|---|---|---|---|
| R50 | P. He, J. Zhu, Z. Zheng, M. R. Lyu, "Drain: An Online Log Parsing Approach with Fixed Depth Tree," IEEE ICWS 2017, pp. 33–40 | [P] | https://pinjiahe.github.io/files/pdf/research/ICWS17.pdf · https://github.com/logpai/logparser |
| R51 | "A Large-Scale Evaluation for Log Parsing Techniques: How Far Are We?" (Loghub-2.0), arXiv 2308.10828 | [P/pre] | https://arxiv.org/abs/2308.10828 |
| R52 | "LLM-aided explanations of EDA synthesis errors," arXiv 2404.07235 (Vivado/Quartus synthesis logs) | [pre] | https://arxiv.org/abs/2404.07235 |
| R53 | R. Kanagal, "LLM-Powered EDA Log Analysis for Effective Design Debugging," UC Berkeley EECS-2025-48 | [tr] | https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/EECS-2025-48.pdf |
| R54 | "EDA-Debugger: An LLM-based Framework for Automated EDA Runtime Issue Resolution," ISQED (year: see URL) | [P] | https://www.isqed.org/English/Proceedings/pdf/2A-1-008.pdf |
| R55 | "ChipNeMo: Domain-Adapted LLMs for Chip Design," arXiv 2311.00176 (NVIDIA; authors: see URL) | [pre] | https://arxiv.org/abs/2311.00176 |
| R56 | "ORAssistant: A Custom RAG-based Conversational Assistant for OpenROAD" | [pre] | https://www.researchgate.net/publication/384699242 |
| R57 | Wu, Sharma, Rovinski, Chhabria, "OpenROAD Agent: An Intelligent Self-Correcting Script Generator for OpenROAD," ICLAD 2025 | [P] | https://ieeexplore.ieee.org/abstract/document/11106006/ |
| R58 | "VerilogEval: Evaluating Large Language Models for Verilog Code Generation," arXiv 2309.07544; N. Pinckney et al., "Revisiting VerilogEval," *ACM TODAES* 2025 | [P] | https://arxiv.org/abs/2309.07544 |
| R59 | "RTLLM: An Open-Source Benchmark for Design RTL Generation with Large Language Model," arXiv 2308.05345 | [pre] | https://arxiv.org/abs/2308.05345 |

## G. Verification intelligence and test prioritization

| ID | Citation | Type | Link |
|---|---|---|---|
| R60 | "Optimizing Design Verification using Machine Learning: Doing better than Random," arXiv 1909.13168 / DVCon (author list differs across versions — see URL) | [P/pre] | https://arxiv.org/abs/1909.13168 |
| R61 | "Optimising Design Verification Using Machine Learning: An Open Source Solution," arXiv 2012.02453 | [pre] | https://arxiv.org/abs/2012.02453 |
| R62 | N. Masamba, K. Eder, T. Blackmore, "Supervised Learning for Coverage-Directed Test Selection in Simulation-Based Verification," arXiv 2205.08524 | [pre] | https://arxiv.org/abs/2205.08524 |
| R63 | N. Masamba, K. Eder, T. Blackmore, "Hybrid Intelligent Testing in Simulation-Based Verification," AITest 2022 (arXiv 2205.09552) | [P] | https://arxiv.org/abs/2205.09552 |
| R64 | B. Busjaeger, T. Xie, "Learning for Test Prioritization: An Industrial Case Study," FSE 2016 (industry track) | [P] | https://taoxie.cs.illinois.edu/publications/fse16industry-learning.pdf |
| R65 | "Test Case Selection and Prioritization Using Machine Learning: A Systematic Literature Review," arXiv 2106.13891 | [P/pre] | https://arxiv.org/abs/2106.13891 |
| R66 | "Revisiting Machine Learning based Test Case Prioritization for Continuous Integration," arXiv 2311.13413 | [pre] | https://arxiv.org/abs/2311.13413 |

## H. Uncertainty quantification

| ID | Citation | Type | Link |
|---|---|---|---|
| R70 | Conformalized quantile regression with on-chip monitors for Vmin prediction (DATE 2024; DAC 2024 follow-up) (authors: see URL) | [P] | https://par.nsf.gov/biblio/10521449 · https://par.nsf.gov/biblio/10521454 |
| R71 | "Theoretical Foundations of Conformal Prediction," arXiv 2411.11824 (textbook-style reference) | [pre] | https://arxiv.org/abs/2411.11824 |

## I. Tools (official)

| ID | Tool | Link |
|---|---|---|
| T01 | Yosys Open SYnthesis Suite | https://github.com/YosysHQ/yosys |
| T02 | OpenROAD | https://github.com/The-OpenROAD-Project/OpenROAD |
| T03 | OpenROAD-flow-scripts (ORFS), BSD-3 scripts; PDK licenses per platform | https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts · https://openroad-flow-scripts.readthedocs.io/ |
| T04 | OpenSTA | https://github.com/The-OpenROAD-Project/OpenSTA |
| T05 | Verilator | https://github.com/verilator/verilator |
| T06 | Icarus Verilog | https://github.com/steveicarus/iverilog |
| T07 | pyslang (SystemVerilog parser, Python bindings of slang) | https://sv-lang.com/pyslang · https://pypi.org/project/pyslang/ |
| T08 | Pyverilog (Verilog AST/dataflow toolkit, Apache-2.0) | https://github.com/PyHDI/Pyverilog |
| T09 | logparser (Drain and others) | https://github.com/logpai/logparser |

---

## Verification backlog (research still owed)

These are known holes in the first-pass review. They are tracked in `TODO.md` (P0-R*).

1. Read full texts of R13, R14/R15, R40, R45, R46 (the runtime/flow-data papers most relevant to our primary contribution).
2. Systematic proceedings search (DAC, ICCAD, MLCAD, ISPD 2020–2026) for: "runtime prediction", "conformal", "uncertainty", "calibration", "out-of-distribution". *The first pass found none for EDA runtime or PPA, but web search cannot prove absence.*
3. Search for hardware-specific (RTL simulation) regression test prioritization with APFD; first pass found mostly software-CI literature.
4. Confirm the licenses of: EPFL benchmarks, IWLS'05, each ORFS design we use, CircuitNet, EDALearn.
5. Confirm the full author lists marked "see URL/DOI".
