# SiliconAI

**AI-Powered Semiconductor Design Intelligence & EDA Optimization Platform**

> **Project status: Phase 1 complete (foundation, toolchain, pilot).** Implemented: a hardened
> runner for EDA tools, an OpenROAD-flow-scripts (ORFS) wrapper running in a pinned Docker
> image, parsers for ORFS per-step timing/memory and METRICS2.1 metrics, a SQLite run registry,
> and a 16-run measured pilot ([`data/pilot_phase1/`](data/pilot_phase1/)). **No ML models exist
> yet.** Everything else below is planned work.

## What this project is

SiliconAI is a planned intelligence layer on top of an **open-source RTL-to-GDS flow**
(Yosys, OpenROAD/OpenSTA, Icarus/Verilator). It aims to:

- predict **per-stage runtime and peak memory** of EDA runs *before* they run, with
  **calibrated uncertainty** and the option to abstain;
- predict outcome risk (timing failure, DRC violations, run failure);
- diagnose failed runs from their logs, linking each diagnosis to the log lines that
  support it;
- extract RTL features and provide a reproducible PPA baseline;
- prioritize verification regression tests;
- combine all of this into evidence-grounded recommendations and, eventually, a copilot.

## Research contribution (approved direction; results pending)

*Uncertainty-aware, cross-stage prediction of open-flow cost and risk, evaluated on unseen
designs*, plus a **fault-injected, labelled corpus of open-EDA failure logs**. See
[`research/04_novelty_analysis.md`](research/04_novelty_analysis.md) for the hypotheses
(H1–H5) and for what would falsify them. We do not claim this is "first": a systematic
literature check is still in progress.

## Quickstart (Phase 1)

Requirements: Linux, Python ≥ 3.11, Docker with a running daemon, GNU `time`.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
docker pull openroad/orfs@sha256:620c13d94b80290ccaa6d6d7fbaef9632bdb06ba7e6aedb88da845159b840c09
siliconai doctor                     # check toolchain
siliconai orfs-run --design-config ./designs/nangate45/gcd/config.mk   # ~1 min
siliconai runs                       # per-stage wall time / CPU / peak memory
pytest -q                            # unit + (if image present) end-to-end tests
```

Set `SILICONAI_ORFS_IMAGE` to the digest above to reproduce our tool versions exactly
(see `.env.example`).

## Repository map (current)

| File | Contents |
|---|---|
| [`PLAN.md`](PLAN.md) | Master plan: vision, strategy, roadmap, risks |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Proposed architecture, data model, security model |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decision records |
| [`PROGRESS.md`](PROGRESS.md) / [`TODO.md`](TODO.md) | Progress log and backlog |
| [`research/`](research/) | Literature review, existing solutions, gaps, novelty, datasets, toolchain, feasibility, references |
| [`src/siliconai/`](src/siliconai/) | Package: `eda/` (runner, ORFS wrapper, parsers), `data/` (schemas, registry), `cli.py` |
| [`tests/`](tests/) | Unit tests + EDA integration tests (marker `eda`) |
| [`scripts/`](scripts/) | Pilot run script and report |
| [`data/pilot_phase1/`](data/pilot_phase1/) | Measured pilot results (CSV + report), regenerable with `scripts/pilot_report.py` |
| [`interview_prep/`](interview_prep/) | Explanations grounded in what is actually built |

## Principles

Real tool outputs over synthetic labels · baselines and group-aware splits ·
calibrated uncertainty · evidence-linked diagnostics · honest limitations.

## License

To be decided (see `TODO.md` P0-D1).
