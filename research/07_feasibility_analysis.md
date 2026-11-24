# 07 — Feasibility Analysis

Machine assumption: 4 vCPU / 15 GB RAM / no GPU (this container). The compute budget below was
**measured in the Phase 1 pilot** (2026-11-24); the original guesses are kept for comparison.

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

## Compute budget (measured in the Phase 1 pilot)

Source: `data/pilot_phase1/`, 16 runs, concurrency 1, this container.

| Design class | Example (platform) | Phase 0 guess | **Measured flow wall time** | Peak memory |
|---|---|---|---|---|
| Tiny | gcd (nangate45 / sky130hd) | 1–3 min | **~33 s / 31 s** | 0.45–0.56 GB |
| Small | aes (nangate45) | 5–15 min | **~5.0 min** | 0.9 GB |
| Medium | ibex (nangate45) | 15–60 min | **~5.0 min** | 1.0 GB |
| Medium | jpeg (nangate45) | 15–60 min | **~14.3 min** | 1.9 GB |
| Small RTL, slower PDK | aes (sky130hd) | — | **~26.3 min** (93% routing) | 2.9 GB |

Run-to-run noise: whole-flow CV 0.7–1.7%; per-stage wall-time CV ≤ 6% (stages > 0.5 s).

**What this implies for Phase 2 (D1 v1)**

- Running sequentially (the noise-safe choice), one day holds about 280 aes/ibex-class runs or
  about 2,000 gcd-class runs. A first D1 of roughly 150–250 runs (ORFS designs plus small generated
  designs, about 10–15 configurations each) costs about **10–20 h** of wall time. That is feasible, but
  only as a staged, resumable sweep.
- Parallel runs are rejected for the main dataset: they would distort the labels by more than the
  measured noise floor. 2 GB peak memory would allow 2–3 parallel runs, but not cleanly.
- sky130hd routing is 5× slower than nangate45 for the same RTL. Big sky130hd designs should be
  sampled sparingly.
- Disk: ≈ 175 MB of artifacts per run, so pruning after parsing is mandatory (P2-11).
- This cloud container: ≤ 2 h per background command and an ephemeral disk, so sweeps run in
  chunks and the registry is committed after each chunk. A persistent Linux/WSL machine removes
  both limits; mixing machines within one dataset is not allowed.

**Methodological constraint (unchanged):** contention distorts runtime labels. The runner records
concurrency, and the main dataset uses a fixed concurrency of 1.

## What cannot be achieved, and will not be claimed

- Industrial-node (≤7 nm commercial) results; sign-off-quality timing or power.
- Real customer regression histories or real farm-log distributions.
- Power prediction without switching activity (vectorless at best). Excluded unless a
  sound method emerges.
- Spatial congestion heatmap prediction (unless Phase 7 adds per-tile dumps; optional).
- Claims of runtime savings in production. We only report **offline, simulated**
  scheduling benefits.
