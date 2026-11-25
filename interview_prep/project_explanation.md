# Project Explanation (living document; only describes what actually exists)

## 30-second version (as of Phase 3)

> SiliconAI is an ML layer on top of the open-source OpenROAD chip-design flow. It predicts how
> long each stage of a chip-implementation run will take, with calibrated uncertainty, and it is
> evaluated on designs the model has never seen. I built the data engine and collected 186 real RTL-to-GDS runs:
> 175 successful, 16 design groups, 5 process platforms. Then I ran four experiments whose success
> criteria I wrote down before collecting any data. The honest headline is mixed:
> - A two-term log-linear baseline beat gradient boosting at predicting runtime on unseen designs.
>   I traced the cause to a gap in the data: no mid-size designs outside one platform.
> - Naive conformal intervals collapse from 91–93% (random splits) to 53–57% coverage on unseen designs, and
>   group-aware calibration restores 92–94%.
> - I pre-registered a fix: a residual hybrid, tested only on 179 new runs collected afterwards. It had the lowest
>   error, but the CI included zero (9 design groups), so I report it as not supported. What limits the
>   evidence is the number of design families, not the number of runs.
>
> Phase 3 was log diagnosis. I wrote fault injectors for 8 failure classes and collected 333 real
> ORFS runs on 13 designs. Then I tested a template-mining classifier against keyword rules I had
> written from a single development design. The rules won clearly: macro-F1 0.97 vs 0.87 on unseen designs,
> and 0.52 for the classifier on unseen fault variants. A post-hoc look showed the model had learned
> *which stage a run reached*, not what went wrong. The learned part that does help is anomaly detection
> (AUROC 0.81), so the product design is rules first, with learned novelty scoring for what the rules can't name.

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

## Phase 3 — what I built and what I found

| Piece | Design decision I can defend |
|---|---|
| Fault injectors | Each fault is a read-only overlay design: the base config plus an injection block, and mutated RTL/SDC copies. The original design and the tool image are never touched, and the label is fixed before the run. OOM and timeout limits are scaled to each design's measured clean run |
| Dev design kept apart | Every injector was probed on gcd first. Injections that the flow silently absorbed (an impossible clock gives negative slack, not a failure) were dropped *before* collection. gcd is never in the test corpus |
| Drain in the repo | Templates are learned from training runs only, and test lines are matched, never learned. That stops a held-out design leaking into the vocabulary |
| Logs as untrusted input | Size, line and line-count caps; symlinks skipped; archives extracted with tarfile's `data` filter (path traversal tested) |

**Results I can quote (docs/results_d2.md, pre-registered E5, 295 labelled failures, 13 design groups):**
- Keyword rules (written from gcd only) reach macro-F1 **0.970** on unseen designs.
- The template classifier reaches **0.869** on unseen designs (Δ −0.102 [−0.126, −0.078]) and **0.521** on unseen fault variants (Δ −0.450).
- Top-3 evidence lines hit the root cause in 37% of runs, against 44% for "last 3 lines containing *error*". The rules' own trigger line hits 95%.
- Template novelty: failed vs clean AUROC **0.81**. Novel-class detection is weak (0.61).
- Why it lost (post hoc): number masking turned `Error 247` (killed for memory) into the same template as every `Error 2`. So the model identified OOM and timeout by how far the run got, and that breaks when the memory or time budget changes. Its evidence ranking was also filled by progress-table rows.

**Data problems I found in my own corpus:**
- On aes, copying a mutated file broke a relative `` `include ``, so 7 "syntax error" runs really failed as missing includes. I reported it, and a sensitivity check without those runs gave the same result.
- One ORFS design uses a newer synthesis frontend whose messages neither the rules nor the model had seen. The rules said "unknown"; the model confidently said "SDC error".

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

**D1 v2 round (docs/results_d1_v2.md):**
- I wrote the E1b protocol and committed it *before* collecting D1 v2, and scored only rows that did not exist when I proposed the
  hybrid. The stopping rule was 5 chunks or sweep complete, and the sweep completed in 5.
- On the new rows, MAE of ln seconds:
  - Hybrid: route 0.537, total 0.430.
  - B1: route 0.673, total 0.565.
  - HGB: route 0.575, total 0.439.
  - ΔMAE hybrid − B1 = −0.135 [−0.312, +0.062] for route, and similar for total. **Not supported.**
- Why the CI is wide: 9 groups that disagree. The hybrid wins big on addtree/mac, where B1 is off by about 2.2×, and loses on alu.
- The D1 v1 ordering (B1 beats HGB) didn't repeat either. I say "no model has been shown to beat B1", not
  "HGB is better now".
- Group-OOF intervals on the new rows cover 88% (HGB) and 82–83% (hybrid, about 10% narrower). All CIs include 90%.
- Flow failures I kept as data, not bugs: a power-grid strap error on a tiny ihp-sg13g2 core, and ORFS's own
  equivalence check failing on generated SRAMs (ORFS already disables it for cva6 for the same reason).

## Likely questions

- *Your ML model lost to regexes. Why is that a result and not a failure?* The comparison was written
  down before the data existed, and the regexes came from a separate design, so they had no unfair
  look at the test set. On injected faults each class has a near-unique message, and a
  one-line regex is the right tool for that. The useful finding is *where* learning helps: flagging
  runs that look unlike any clean run, which the rules can't do. I didn't re-tune the masking after seeing the
  result. The fix is on the backlog, to be pre-registered and tested on new data.

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
- *You ran a second experiment and it also failed. Why keep going?* Both were pre-registered, so a null
  result is information. It moved the bottleneck from "missing platform × size data" (fixed, and the
  gap is visibly filled) to "too few design families", and that tells me what to collect next.
  Without the protocol I could have reported the all-rows numbers (hybrid 0.453 vs B1 0.589), but those
  include the data that suggested the hybrid.
- *Why are your intervals so wide?* Because they're honest on unseen designs. The naive ones are about 2.5×
  narrower, and on unseen designs they're wrong almost half the time.
