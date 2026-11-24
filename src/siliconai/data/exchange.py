"""Export / import the run registry as JSON Lines (TODO P2-12).

The SQLite registry lives in an ephemeral workspace. After each sweep chunk it is exported to
deterministic, sorted JSONL files that are committed to git, and a fresh container restores
the registry from them. Imported rows pass through the same pydantic models as live data.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from siliconai.data.registry import Registry
from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord

FILES = ("designs.jsonl", "runs.jsonl", "steps.jsonl")
_MAX_FILE_BYTES = 256 * 1024 * 1024


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def export_jsonl(registry: Registry, out_dir: Path) -> dict[str, int]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    designs = [dict(r) for r in registry.designs()]
    runs = []
    for r in sorted(registry.runs(), key=lambda r: r["run_id"]):
        row = dict(r)
        row["config"] = json.loads(row.pop("config_json"))
        row["host"] = json.loads(row.pop("host_json"))
        runs.append(row)
    steps = []
    for r in registry.all_steps():
        row = dict(r)
        row["metrics"] = json.loads(row.pop("metrics_json"))
        steps.append(row)
    for name, rows in zip(FILES, (designs, runs, steps), strict=True):
        _write_jsonl(out_dir / name, rows)
    return {"designs": len(designs), "runs": len(runs), "steps": len(steps)}


def _read_jsonl(path: Path) -> list[dict]:
    if path.stat().st_size > _MAX_FILE_BYTES:
        raise ValueError(f"{path.name} too large")
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def import_jsonl(registry: Registry, src_dir: Path) -> dict[str, int]:
    """Load exported JSONL into ``registry`` (insert-or-replace). Validates every row."""
    src_dir = Path(src_dir)
    designs = [DesignRecord(**row) for row in _read_jsonl(src_dir / "designs.jsonl")]
    steps_by_run: dict[str, list[StepRecord]] = defaultdict(list)
    for row in _read_jsonl(src_dir / "steps.jsonl"):
        steps_by_run[row["run_id"]].append(StepRecord(**row))
    runs = []
    for row in _read_jsonl(src_dir / "runs.jsonl"):
        stored_hash = row.pop("config_hash")
        run = RunRecord(**row)
        if run.config_hash != stored_hash:
            raise ValueError(f"config_hash mismatch for {run.run_id}: data corrupted?")
        runs.append(run)
    for d in designs:
        registry.upsert_design(d)
    for run in runs:
        registry.record_run(run, steps_by_run.pop(run.run_id, []))
    if steps_by_run:
        raise ValueError(f"steps without a run: {sorted(steps_by_run)[:5]}")
    return {"designs": len(designs), "runs": len(runs)}
