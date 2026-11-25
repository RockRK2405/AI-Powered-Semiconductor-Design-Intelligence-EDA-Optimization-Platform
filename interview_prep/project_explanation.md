# Project Explanation (living document; only describes what actually exists)

## 30-second version (as of Phase 2, complete)

> SiliconAI is an ML layer on top of the open-source OpenROAD chip-design flow. It predicts how
> long each stage of a chip-implementation run will take, with calibrated uncertainty, and it is
> evaluated on designs the model has never seen. I built the data engine and collected 186 real RTL-to-GDS runs:
> 175 successful, 16 design groups, 5 process platforms. Then I ran four experiments whose success
> criteria I wrote down before collecting any data. The honest headline is mixed:
> - A two-term log-linear baseline beat gradient boosting at predicting runtime on unseen designs.
>   I traced the cause to a gap in the data: no mid-size designs outside one platform.
> - Naive conformal intervals collapse from 91–93% (random splits) to 53–57% coverage on unseen designs, and
>   group-aware calibration restores 92–94%.

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

## Phase 2 — what I built and what I found

| Piece | Design decision I can defend |
|---|---|
| Resumable sweep runner | Deterministic run IDs; ≤ 2 h chunks with an export after each one, because the cloud container is ephemeral; a preflight rejects configs ORFS can't run (found in the pilot); each run's directories are cleared first, after I caught a re-run reusing an earlier attempt's outputs |
| Dataset builder | Every feature is tagged with the stage that produces it, so a model at horizon *h* can't see later stages (tested). It refuses mixed tool images or hosts, and refuses runs whose step times add up to more than the measured wall time |
| Evaluation | Leave-one-design-group-out: the same RTL on any platform, or a whole generated family, is held out together. Group-bootstrap CIs. Protocol and success criteria written **before** data |
| Conformal | Naive split, group-OOF (CV+ style), CQR, Mondrian by platform |

**Results I can quote (docs/results_d1_v1.md; all MAE on ln(seconds), LOGO):**
- **H1 not supported, and reversed:**
  - Route time: B1 (ln cells + platform) MAE 0.397 vs HGB 0.586.
  - Total flow: 0.327 vs 0.474.
  - Why: outside nangate45 the data has no designs between 1k and 5k cells, so trees can't learn
    the size trend per platform. For example, riscv32i on gf180 was predicted at 44–48 s against 222–270 s actual.
- **H3 supported:** naive conformal covers 91–93% on random splits but 53–57% on unseen designs.
  Group-OOF reaches 92–94%. Caveat: those intervals span about 3.8× either side for route time.
- **H2, H4 not supported.** Observing placement didn't significantly improve route prediction. A kNN
  OOD score didn't find the large errors.
- HGB *does* beat the baseline on peak memory for place, CTS and finish (CIs exclude 0).
- Exploratory only, not a result: B1 + HGB on its residuals reached route MAE 0.356 and total 0.257. That is
  the hypothesis for the next pre-registered round.

**Bugs I caught in my own data, and how:**
- ORFS echoes the equivalence-check timing line into the CTS log, which double-counted it. I spotted it when a run's
  step times added up to more than its wall time. Now an invariant refuses such runs.
- A stale re-run directory produced a 29 s "success" whose step logs (591 s) came from an earlier stopped probe.
- All corrections were re-parsed from the original logs and logged append-only.

## Phase 1 numbers I can quote (from my own runs; see PROGRESS.md)

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
- *Your model lost to a linear baseline. Isn't that a failure?* It's the result. I pre-registered the
  comparison, so I can't quietly swap in the winner. The analysis shows *why* (platform × size
  coverage), which tells me what data to collect next. A learned model that beat B0 but not B1
  would have been easy to over-sell.
- *Why are your intervals so wide?* Because they're honest on unseen designs. The naive ones are about 2.5×
  narrower, and on unseen designs they're wrong almost half the time.
