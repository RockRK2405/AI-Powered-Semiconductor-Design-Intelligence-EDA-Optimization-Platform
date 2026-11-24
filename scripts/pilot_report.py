"""Summarise the Phase 1 pilot from the run registry (TODO P1-09).

Reports, from recorded data only:
  1. cost per design (total flow wall time, per-stage wall time, peak memory);
  2. run-to-run noise: coefficient of variation (CV = std/mean) of wall time and peak
     memory per stage, across repeats of an identical configuration.

Usage: SILICONAI_HOME=workspace/phase1 python scripts/pilot_report.py \
           [--markdown out.md] [--export-dir data/pilot_phase1]

--export-dir writes runs.csv and stage_summary.csv so that the numbers quoted in PROGRESS.md
can be regenerated from committed data (the run workspace itself is not committed).
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

from siliconai.config import Settings
from siliconai.data.registry import Registry
from siliconai.eda.orfs_parse import STAGE_ORDER

STAGES = (*STAGE_ORDER, "other")


def _cv(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = statistics.fmean(values)
    return statistics.stdev(values) / mean if mean > 0 else None


def build_report(reg: Registry) -> str:
    runs = {r["run_id"]: r for r in reg.runs()}
    per_run: dict[str, dict[str, tuple[float, float]]] = defaultdict(dict)
    for row in reg.stage_summary():
        per_run[row["run_id"]][row["stage"]] = (row["wall_s"], row["peak_rss_mb"] or 0.0)

    lines = ["## 1. Cost per run (sequential, concurrency 1)", ""]
    header = "| run | status | total wall s | " + " | ".join(STAGES) + " | peak MB |"
    lines += [header, "|" + "---|" * (len(STAGES) + 4)]
    for run_id, run in sorted(runs.items()):
        stages = per_run.get(run_id, {})
        total = sum(w for w, _ in stages.values())
        peak = max((m for _, m in stages.values()), default=0.0)
        cells = " | ".join(f"{stages[s][0]:.1f}" if s in stages else "–" for s in STAGES)
        lines.append(f"| {run_id} | {run['status']} | {total:.1f} | {cells} | {peak:.0f} |")

    # group identical configurations (design + config hash) across repeat indices
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for run_id, run in runs.items():
        if run["status"] == "success":
            groups[(run["design_id"], run["config_hash"])].append(run_id)

    lines += ["", "## 2. Run-to-run noise (identical config, ≥2 successful repeats)", ""]
    lines += ["| design | config | n | stage | mean wall s | CV wall | mean peak MB | CV peak |"]
    lines += ["|---|---|---|---|---|---|---|---|"]
    for (design, cfg), ids in sorted(groups.items()):
        if len(ids) < 2:
            continue
        for stage in STAGES:
            walls = [per_run[i][stage][0] for i in ids if stage in per_run[i]]
            peaks = [per_run[i][stage][1] for i in ids if stage in per_run[i]]
            if len(walls) < 2:
                continue
            cvw, cvp = _cv(walls), _cv(peaks)
            lines.append(
                f"| {design} | {cfg[:8]} | {len(walls)} | {stage} | "
                f"{statistics.fmean(walls):.2f} | {cvw:.1%} | "
                f"{statistics.fmean(peaks):.0f} | {cvp:.1%} |"
            )
    return "\n".join(lines) + "\n"


RUN_COLUMNS = (
    "run_id",
    "design_id",
    "config_hash",
    "config_json",
    "tool_image",
    "host_json",
    "concurrency",
    "repeat_index",
    "injected_fault",
    "status",
    "exit_code",
    "wall_s",
    "started_at",
)


def export_csv(reg: Registry, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "runs.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(RUN_COLUMNS)
        for run in sorted(reg.runs(), key=lambda r: r["run_id"]):
            writer.writerow([run[c] for c in RUN_COLUMNS])
    rows = sorted(reg.stage_summary(), key=lambda r: (r["run_id"], r["stage"]))
    with (out_dir / "stage_summary.csv").open("w", newline="") as fh:
        writer = csv.writer(fh)
        cols = list(rows[0].keys()) if rows else []
        writer.writerow(cols)
        for row in rows:
            writer.writerow([row[c] for c in cols])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown", type=Path, default=None)
    parser.add_argument("--export-dir", type=Path, default=None)
    args = parser.parse_args()
    with Registry(Settings.from_env().db_path) as reg:
        report = build_report(reg)
        if args.export_dir:
            export_csv(reg, args.export_dir)
    print(report)
    if args.markdown:
        args.markdown.write_text(report)


if __name__ == "__main__":
    main()
