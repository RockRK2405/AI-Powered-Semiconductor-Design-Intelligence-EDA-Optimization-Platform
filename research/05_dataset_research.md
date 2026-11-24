# 05 — Dataset and Benchmark Research

Licenses marked **TBC** have not been confirmed from the source repository. Confirming them
is task P0-R4 in `TODO.md`. We will not redistribute any data whose license is unconfirmed.

## 1. External datasets

| Dataset | Source | License | Access | Format | Features / labels | Limitations | Use in SiliconAI |
|---|---|---|---|---|---|---|---|
| **CircuitNet (N28, N14) / 2.0** (R10, R11) | github.com/circuitnet/CircuitNet | TBC | Download per docs | Per-tile feature maps (numpy) | Congestion, DRC (N28), IR drop (vectorless), net delay/timing | Closed node (N28) → not reproducible (per R13); image tasks need GPU; runtime labels not confirmed | Optional, Phase 7 reference only |
| **OpenABC-D** (R12) | github.com/NYU-MLDA/OpenABC; Zenodo (18.6 GB) | TBC | Zenodo / NYU archive | AIG graphs (PyTorch Geometric) | Post-synthesis node count, delay per synthesis recipe | Synthesis-only; 1.4 TB full release | Optional; recipe→QoR sanity check |
| **EDALearn** (R13) | github.com/panjingyu/EDALearn | TBC | GitHub | TBC | Multi-stage: placement, routing, timing, power, IR | Need to inspect for per-stage runtime/memory | **High priority to inspect**; could augment G1/G2 data |
| **EDA-schema** (R14) / **V2** (R15) | github.com/drexel-ice/EDA-schema | TBC | GitHub | Property graphs + Python library | QoR across stages; parameter sweeps (V2: clock, util, aspect ratio over 4 PDKs) | V2 is a 2026 preprint | **High priority to inspect**: closest in spirit to our sweeps |
| **EPFL combinational benchmarks** (R16) | github.com/lsils/benchmarks | TBC (Zenodo record: open access) | GitHub | Verilog, BLIF, AIGER | Logic only (no labels) | Combinational only; MtM circuits huge | RTL diversity for synthesis-level data |
| **IWLS 2005 benchmarks** | (used by R14) | TBC | TBC | Verilog | No labels | Old designs | Candidate design pool |
| **ORFS designs** (T03) | `flow/designs/src/*` in ORFS | Per-design (check each folder) | Bundled with ORFS | Verilog/SV + configs | No labels until we run them; ready-made configs per platform | Varied sizes (gcd ~250 cells … large SoCs) | **Primary design pool** |
| **VerilogEval / RTLLM** (R58, R59) | GitHub | TBC | GitHub | Spec + reference RTL + testbench | Functional tests | Small designs | Source of small RTL designs **with testbenches** for G5 |
| **EDA Corpus** (R17) | github.com/OpenROAD-Assistant/EDA-Corpus | TBC | GitHub | Q&A / script pairs | — | Doc-oriented | Optional copilot evaluation |
| **Loghub** (R51) | github.com/logpai/loghub | TBC | GitHub | Raw logs + templates | Template ground truth | Not EDA | Parser sanity check only |

## 2. Data we will generate (primary strategy)

All generated data is **real tool output**. The only synthetic elements are design
*sources* from parameterized generators and *injected faults*, and both are recorded
explicitly in every row.

### D1 — Flow-run dataset (Modules 1, 4, 6, 7)

- **Unit:** one (design, platform, config, repeat) flow run. Each run produces one row
  per stage.
- **Design pool:** ORFS small and medium designs (e.g., gcd, aes, ibex, jpeg, uart-class,
  riscv32i; exact list after checking what completes in reasonable time here), plus
  **parameterized RTL generators** (adders, multipliers, FIFOs, FSMs, MAC arrays
  at different widths and depths). Generator output is tagged `design_origin=generated`.
- **Platforms:** Nangate45 and SKY130HD first (fast, permissive). ASAP7 is optional.
- **Sweep variables:** clock period, core utilization, place density, aspect ratio,
  synthesis options (e.g., ABC script / flatten), `NUM_CORES`/threads.
- **Recorded per stage:** wall time, CPU time, peak RSS (via `/usr/bin/time -v` or
  psutil), exit status, METRICS2.1 JSON fields (cell count, area, utilization, WNS/TNS,
  wirelength, DRC count), tool versions, git SHAs, host fingerprint.
- **Target size, first iteration:** about 20–40 designs × 10–30 configs, giving about 400–1,000
  runs (×5–7 stages). This is compute-bound; see `07`.
- **Noise floor:** 10% of configs repeated 3× to measure runtime variance.

### D2 — Fault-injected log corpus (Module 2)

- Injectors per class: `syntax_error`, `elaboration_error` (undefined module),
  `missing_file`, `bad_sdc`, `timing_infeasible` (impossible clock), `over_utilization`,
  `routing_congestion` (high density), `oom` (cgroup/ulimit), `timeout`, plus `success`.
- Each injection is recorded (class, variant, parameters). Logs are stored raw plus
  parsed into Drain templates.
- Split design-held-out **and** variant-held-out.

### D3 — RTL features (Module 3)

- Yosys-derived: `stat` (cells by type, wires, memories), post-`proc` and post-`opt` counts,
  FSM extraction (`fsm_detect`), flattened hierarchy depth.
- AST-derived (pyslang/Pyverilog): operators, widths, always blocks, parameters, LOC.
- Validation: cross-check counts between the AST and Yosys on hand-checked toy designs.

### D4 — Simulated regression history (Module 5)

- Designs with self-checking testbenches. Mutants are generated with simple RTL mutation
  operators (operator swap, constant flip, condition negation).
- Each "commit" = a set of mutants. We run all tests and log pass/fail and runtime.
- Clearly labelled `history_origin=simulated_mutation`.

## 3. Data quality checks (applied to every dataset)

- Schema validation (pydantic) at ingestion; missing values reported per column.
- Duplicate / near-duplicate design detection: hash of normalized RTL and of the Yosys stat
  vector. Duplicates share a `design_group` for splitting.
- Leakage audit: features must be timestamped "available at stage *h*". Unit tests
  enforce that a horizon-*h* model never sees stage > *h* columns.
- Every dataset is versioned by content hash and stored with a manifest.
