# 07 — Feasibility Analysis

Machine assumption: 4 vCPU / 15 GB RAM / no GPU (this container). Runtime estimates for
EDA runs are **unmeasured guesses**, to be replaced with measurements in Phase 1.

| Module | Local (pure Python) | Needs open-source EDA | Significant compute | Needs proprietary | Data realistically obtainable | Quantitatively evaluable | Known limitations | Verdict |
|---|---|---|---|---|---|---|---|---|
| **1. Runtime & resource intelligence** | Models, conformal, features | OpenROAD/ORFS + Yosys | Yes: hundreds of flow runs (hours to days of CPU) | No | Yes, D1 | Yes (MAE, coverage, underestimation rate) | One machine type; small and medium designs only; runtime noise | **Go (core)** |
| **2. Log intelligence** | Parser, classifier, anomaly | Same flows (fault injection) | Moderate (failed runs are often fast) | No | Yes, D2 | Yes (macro-F1, evidence precision, AUROC) | Injected ≠ real-world failures | **Go (core)** |
| **3. RTL intelligence** | AST features (pyslang) | Yosys stat/proc/fsm; Verilator lint | Low | No | Yes | Partly (feature correctness via unit tests on hand-counted designs) | FSM/logic-depth extraction is approximate | **Go** |
| **4. PPA prediction** | Models | Yosys+ABC with Liberty (area); OpenSTA (delay) | Low-moderate | No | Yes (from D1 synthesis stage) | Yes (MAE/R², leave-design-out) | Not competitive with GNN SOTA; open PDK only; power excluded (needs activity) | **Go as baseline** |
| **5. Verification intelligence** | Ranker, APFD | Icarus/Verilator simulation | Moderate | No | Simulated mutation histories only | Yes (APFD/APFDc) | Simulated histories ≠ real project histories | **Go (later, smaller scope)** |
| **6. Physical-design risk** | Classifiers | OpenROAD metrics (D1) | Included in D1 | No | Design-level metrics only | Yes (AUROC/PR-AUC for DRC>0, WNS<0) | **No spatial congestion maps** unless we dump per-tile data; won't claim it | **Go (design-level only)** |
| **7. Decision engine** | Yes | — | Low | No | Derived | Partly (rule tests; offline "regret" on held-out runs) | Recommendations are heuristics on top of models | **Go** |
| **8. Copilot** | Retrieval, tool-calls | — | Low | LLM API (paid) or local model | Our DB | Partly (citation precision on a gold set) | Needs a key; risk of hallucination, mitigated by structure | **Go (last)** |

## Compute budget sketch (to be measured)

| Design class | Example | Guess per full ORFS run on Nangate45 |
|---|---|---|
| Tiny | gcd | ~1–3 min |
| Small | aes, uart-class, generated blocks | ~5–15 min |
| Medium | ibex, jpeg | ~15–60 min |

At an average of 10 min/run with 2 parallel runs (to keep peak memory and runtime contention
measurable), 800 runs ≈ 67 hours of wall time. That is **feasible but must be planned**:
staged sweeps, a resumable runner, and an early pilot (~50 runs) to measure the real cost.

**Important methodological constraint:** parallel runs contend for CPU and memory, which
distorts runtime labels. The runner must record concurrency, and the main dataset should
use a **fixed** concurrency level.

## What cannot be achieved, and will not be claimed

- Industrial-node (≤7 nm commercial) results; sign-off-quality timing or power.
- Real customer regression histories or real farm-log distributions.
- Power prediction without switching activity (vectorless at best). Excluded unless a
  sound method emerges.
- Spatial congestion heatmap prediction (unless Phase 7 adds per-tile dumps; optional).
- Claims of runtime savings in production. We only report **offline, simulated**
  scheduling benefits.
