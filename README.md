# SiliconAI

**AI-Powered Semiconductor Design Intelligence & EDA Optimization Platform**

> **Project status: Phase 0 — research & strategy.** There is no platform code yet.
> This README describes the plan, not implemented features. Nothing below should be read
> as a result.

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

## Proposed research contribution (pending review)

*Uncertainty-aware, cross-stage prediction of open-flow cost and risk, evaluated on unseen
designs*, plus a **fault-injected, labelled corpus of open-EDA failure logs**. See
[`research/04_novelty_analysis.md`](research/04_novelty_analysis.md) for the hypotheses
(H1–H5) and for what would falsify them. We do not claim this is "first": a systematic
literature check is still in progress.

## Repository map (current)

| File | Contents |
|---|---|
| [`PLAN.md`](PLAN.md) | Master plan: vision, strategy, roadmap, risks |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Proposed architecture, data model, security model |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decision records |
| [`PROGRESS.md`](PROGRESS.md) / [`TODO.md`](TODO.md) | Progress log and backlog |
| [`research/`](research/) | Literature review, existing solutions, gaps, novelty, datasets, toolchain, feasibility, references |

## Principles

Real tool outputs over synthetic labels · baselines and group-aware splits ·
calibrated uncertainty · evidence-linked diagnostics · honest limitations.

## License

To be decided (see `TODO.md` P0-D1).
