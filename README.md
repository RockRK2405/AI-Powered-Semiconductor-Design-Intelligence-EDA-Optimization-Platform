# SiliconAI

**AI-Powered Semiconductor Design Intelligence & EDA Optimization Platform**

> **Project status: Phase 2 in progress (data engine + runtime intelligence).** Phase 1 delivered
> a hardened EDA runner, a digest-pinned ORFS Docker wrapper, log/metric parsers, a SQLite run
> registry and a measured pilot ([`data/pilot_phase1/`](data/pilot_phase1/)). Phase 2 has added a
> resumable sweep engine, RTL generators, a leakage-safe dataset builder, conformal prediction and
> pre-registered experiments ([`docs/experiments.md`](docs/experiments.md)). Dataset D1 is being
> collected. **No model results are reported yet.**

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
| [`src/siliconai/`](src/siliconai/) | Package: `eda/` (runner, ORFS wrapper, parsers), `data/` (registry, JSONL exchange, dataset), `sweep/`, `rtlgen/`, `uncertainty/`, `runtime_intelligence/`, `cli.py` |
| [`tests/`](tests/) | Unit tests + EDA integration tests (marker `eda`) |
| [`sweeps/`](sweeps/) | Sweep specs for dataset D1 |
| [`docs/experiments.md`](docs/experiments.md) | Pre-registered protocols for E1–E4 |
| [`scripts/`](scripts/) | Pilot, probe, chunk runner, dataset freeze, experiment runner |
| [`data/pilot_phase1/`](data/pilot_phase1/) | Measured pilot results (CSV + report), regenerable with `scripts/pilot_report.py` |
| [`interview_prep/`](interview_prep/) | Explanations grounded in what is actually built |

## Principles

Real tool outputs over synthetic labels · baselines and group-aware splits ·
calibrated uncertainty · evidence-linked diagnostics · honest limitations.

## License

MIT. See [`LICENSE`](LICENSE). ORFS designs and PDKs used in experiments keep their own licenses
(tracked per design, TODO P0-R4).
