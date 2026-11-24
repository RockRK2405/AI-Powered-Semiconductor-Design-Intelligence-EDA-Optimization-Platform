# Project Explanation (living document; only describes what actually exists)

## 30-second version (as of Phase 1, complete)

> SiliconAI is an ML layer on top of the open-source OpenROAD chip-design flow. Its goal is to
> predict how long each stage of a chip-implementation run will take and how much memory
> it will need *before* running it, with calibrated uncertainty, and to diagnose failed
> runs from their logs. So far I have built the data engine. It runs real RTL-to-GDS flows
> in a pinned Docker image, validates every input, and records per-step wall time, CPU time,
> peak memory and METRICS2.1 quality metrics into a SQLite registry. It has 52 tests,
> including end-to-end runs of the real flow.

## Why the project exists (research-backed)

- Published ML-for-EDA mostly predicts *quality of results* (area, timing, congestion). Examples
  are SNS (ISCA'22), MasterRTL (ICCAD'23), RouteNet (ICCAD'18) and timing GNNs (DAC'22).
- Predicting the *cost of running the flow* (runtime and memory per stage) on open tools, with
  design-held-out evaluation and calibrated uncertainty, showed up only as side components
  in my literature search (IICPilot; an FPGA/Vivado study). See `research/03_research_gap.md`.
- I state this as a search finding, not as "nobody has done it". A systematic proceedings search is
  still on my backlog.

## Phase 1 — what I built and why

| Piece | What it does | Design decision I can defend |
|---|---|---|
| `eda/runner.py` | Runs any tool safely | argv lists only (no shell injection); allowlisted env (secrets never reach tools); timeout kills the **process group**; GNU time for per-command peak RSS. Each property has a test. |
| `eda/orfs.py` | Runs an ORFS design in Docker | Pinned image digest = tool version of record. Allowlisted flow variables and regex-validated values (blocks `$(shell …)` make injection). `--network none`. Inner `timeout` plus `docker kill` backstop, because killing the Docker CLI doesn't stop the container. |
| `eda/orfs_parse.py` | Parses ORFS logs and metrics | Uses ORFS's **in-container** timing lines. GNU time around `docker run` would measure the Docker CLI (~32 MB), not OpenROAD (ADR-011). Treats files as untrusted: size caps, drops NaN/inf. |
| `data/registry.py` | SQLite run registry | Atomic run+steps writes; foreign keys; parameterized SQL. Deterministic run IDs make sweeps resumable. |
| `data/schemas.py` | pydantic records | `extra="forbid"`, ID regexes, non-negative times: bad data stops at the boundary. |

## Numbers I can quote (from my own runs; see PROGRESS.md)

All from the 16-run pilot on a 4-vCPU cloud VM (`data/pilot_phase1/`). **Quote only these.**
- Full RTL→GDS flow time: gcd ~33 s, aes ~5 min, ibex ~5 min, jpeg ~14 min (Nangate45).
- Same aes RTL on sky130hd: ~26 min, **5.3×** Nangate45, and 93% of it is routing. Platform is a
  first-order feature.
- Routing is 55–93% of flow time; peak memory stays below 3 GB, so time, not memory, is the budget.
- Noise floor over 3 identical repeats: whole-flow CV 0.7–1.7%, per stage ≤ 6%. So I don't
  claim per-stage errors below ~5%.
- 6 of 16 pilot runs failed: utilization overrides conflict with designs that fix their floorplan
  (`FLOORPLAN_DEF`). That became a preflight check for Phase 2, and a source of real failure logs.

## Likely questions

- *Why not just use CircuitNet?* It has no confirmed runtime/memory labels, its N28 node is
  closed (not reproducible), and its tasks are image-based congestion maps (needs a GPU).
- *Why Docker?* One digest pins Yosys, OpenROAD and KLayout. The same dataset can be regenerated on
  any Linux machine. Caveat: runtimes are still machine-specific, so the host fingerprint is recorded.
- *How do you avoid measuring noise?* Fixed concurrency (one run at a time in the pilot), repeated
  runs to measure the noise floor, and no claimed error smaller than that floor.
