# 06 — Toolchain Research and Justification

Environment facts were checked in this container on 2026-11-24: Linux, Python 3.13.18,
4 vCPUs, 15 GB RAM, about 60 GB free disk. The Docker CLI is present, but **the daemon is not
running**. No EDA tools are pre-installed. Ubuntu apt candidates: **yosys 0.33,
iverilog 12.0, verilator 5.020**. **opensta: no apt package.** The user's own machine
has not been checked.

Rule: a tool is adopted only when a phase needs it.

| Tool | Purpose in SiliconAI | Needed from | Availability here | Decision | Justification |
|---|---|---|---|---|---|
| **Python 3.11–3.13** | Everything | Phase 1 | ✅ 3.13 | Adopt | Ecosystem. Pin `>=3.11`. |
| **NumPy / Pandas** | Data handling | Phase 1 | pip | Adopt | Standard. |
| **PyArrow / Parquet** | Versioned datasets on disk | Phase 2 | pip | Adopt | Columnar, typed, compact; better than CSV for reproducibility. |
| **SQLite** | Run registry, metadata, predictions | Phase 1 | stdlib | Adopt | Zero-ops. PostgreSQL only if multi-user/concurrent writes are needed (ADR-004). |
| **pydantic** | Schema validation of configs and ingested records | Phase 1 | pip | Adopt | Treats inputs as untrusted. |
| **scikit-learn** | Baselines, linear models, RF, GBM, pipelines, GroupKFold, IsolationForest | Phase 2 | pip (1.9.1 wheel for cp313 confirmed) | Adopt | Core. |
| **XGBoost or LightGBM** | Strong tabular GBM; quantile objectives | Phase 2 | pip | Adopt one (XGBoost default) | Tabular SOTA for small *n*. Choice benchmarked in Phase 2. |
| **Conformal prediction** | Calibrated intervals | Phase 2 | implement by hand (~100 lines); optionally MAPIE | Hand-implement first | Learning value; few dependencies; easy to unit-test the coverage guarantee. |
| **SHAP** | Explainability for tree models | Phase 2/5 | pip | Adopt when needed | TreeSHAP is exact for trees. Check Python 3.13 wheel at install time. |
| **Yosys** | Synthesis, RTL structural stats, FSM detection | Phase 2/4 | apt 0.33 (ORFS bundles its own) | Adopt | Open-flow standard. |
| **ABC** | Technology mapping (inside Yosys) | Phase 4/5 | with Yosys | Adopt | Via Yosys. |
| **OpenROAD + ORFS** | Floorplan → place → CTS → route; METRICS2.1 | Phase 2 | ❌ not installed; options below | **Adopt — critical path** | Only open full RTL-to-GDS flow with standard metrics. |
| **OpenSTA** | Static timing analysis | Phase 5 | bundled inside OpenROAD | Use via OpenROAD | Avoid a separate build. |
| **Icarus Verilog** | Simulation for testbenches (Module 5) | Phase 6 | apt 12.0 | Adopt | Simple, fast for small designs. |
| **Verilator** | Lint (RTL validation on upload); fast simulation | Phase 4/6 | apt 5.020 | Adopt | Lint is a cheap RTL sanity gate. |
| **pyslang** | SystemVerilog AST features | Phase 4 | pip | Adopt (preferred over Pyverilog) | Actively maintained, full SV support. Pyverilog is Verilog-only and needs iverilog. |
| **logparser / Drain** | Log template mining | Phase 3 | pip / vendored | Adopt (or reimplement Drain, ~200 lines) | Proven parser (R50). |
| **FastAPI** | Service API | Phase 10 | pip | Adopt later | Typed, OpenAPI docs. Not needed before UI integration. |
| **Streamlit** | Dashboard | Phase 2 (minimal), Phase 10 | pip | Adopt | Fastest path to a usable UI in Python. |
| **MLflow** | Experiment tracking | Phase 2 | pip | **Defer**; start with JSON run records + git SHA (ADR-006) | Avoids a server for a single-user project. Revisit when there are more than about 50 experiments. |
| **PostgreSQL** | Multi-user DB | Phase 10+ | — | Defer | See SQLite. |
| **PyTorch / PyG** | GNNs | — | — | **Not planned** | No GPU; tabular GBM is adequate for our *n*. Only revisit for an explicit GNN extension. |
| **FAISS** | Vector search | Phase 9 | pip | Defer; sklearn NearestNeighbors may suffice | Corpus will be small. |
| **LLM API** | Copilot explanation layer | Phase 9 | needs key | Defer | Last phase. Key handled via env and secret store. |
| **Docker / Compose** | Reproducible toolchain, deployment | Phase 1 (if daemon is available) / Phase 11 | CLI only; daemon down | Investigate in Phase 1 | ORFS publishes Docker images; this is the easiest route to OpenROAD. |
| **GitHub Actions** | CI: lint, tests | Phase 1 | — | Adopt | Run unit tests on synthetic fixtures. No EDA tools in CI at first. |
| **pytest, ruff, mypy (light)** | Quality | Phase 1 | pip | Adopt | — |

## Routes to OpenROAD (decision needed in Phase 1)

| Option | Pros | Cons |
|---|---|---|
| A. ORFS Docker image | Official, reproducible, pins all tools | Needs a working Docker daemon (not available in this container) |
| B. Build ORFS from source (`build_openroad.sh --local`) | No Docker | Long build (~1 h on 4 cores, estimate), many deps |
| C. Prebuilt OpenROAD binaries / packages (if published for our Ubuntu) | Fast | Must verify availability and version |
| D. OpenLane 2 (pip `openlane` 2.3.10 exists) + Nix or Docker | Polished flow | Still needs Nix/Docker for tools |
| E. Run data generation on **your own machine** (Linux/WSL2 with Docker) | Most realistic | Depends on your hardware and time |

**Recommendation:** try B/C in this cloud container first in Phase 1, with a 2-hour cap. The
runtime dataset must come from **one consistent machine**. So whichever machine generates
D1 must be the same one for the whole dataset, and its spec is recorded.
