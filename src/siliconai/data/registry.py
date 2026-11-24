"""SQLite run registry: the single source of truth for designs, runs and per-step data.

ADR-004: SQLite for metadata (zero-ops, single user); analytic datasets are exported to
Parquet from here in Phase 2. All SQL uses parameter binding -- never string formatting.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path

from siliconai.data.schemas import DesignRecord, RunRecord, StepRecord

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS designs (
    design_id    TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    platform     TEXT NOT NULL,
    origin       TEXT NOT NULL,
    source       TEXT NOT NULL,
    design_group TEXT NOT NULL,
    license      TEXT
);
CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    design_id      TEXT NOT NULL REFERENCES designs(design_id),
    config_json    TEXT NOT NULL,
    config_hash    TEXT NOT NULL,
    tool_image     TEXT,
    host_json      TEXT NOT NULL,
    concurrency    INTEGER NOT NULL,
    repeat_index   INTEGER NOT NULL,
    injected_fault TEXT,
    status         TEXT NOT NULL,
    exit_code      INTEGER,
    wall_s         REAL,
    started_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS steps (
    run_id       TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    step         TEXT NOT NULL,
    stage        TEXT NOT NULL,
    wall_s       REAL,
    cpu_user_s   REAL,
    cpu_sys_s    REAL,
    peak_rss_mb  REAL,
    metrics_json TEXT NOT NULL,
    log_path     TEXT,
    PRIMARY KEY (run_id, step)
);
CREATE INDEX IF NOT EXISTS idx_runs_design ON runs(design_id);
CREATE INDEX IF NOT EXISTS idx_steps_stage ON steps(stage);
"""


class Registry:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> Registry:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # -- writes -------------------------------------------------------------------------
    def upsert_design(self, d: DesignRecord) -> None:
        with self.transaction() as c:
            c.execute(
                "INSERT INTO designs(design_id, name, platform, origin, source, design_group, "
                "license) VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(design_id) DO UPDATE SET name=excluded.name, "
                "platform=excluded.platform, origin=excluded.origin, source=excluded.source, "
                "design_group=excluded.design_group, license=excluded.license",
                (d.design_id, d.name, d.platform, d.origin, d.source, d.design_group, d.license),
            )

    def record_run(self, run: RunRecord, steps: Iterable[StepRecord] = ()) -> None:
        """Insert or replace a run and all its steps atomically."""
        steps = list(steps)
        for s in steps:
            if s.run_id != run.run_id:
                raise ValueError(f"step {s.step} belongs to {s.run_id}, not {run.run_id}")
        with self.transaction() as c:
            c.execute("DELETE FROM steps WHERE run_id = ?", (run.run_id,))
            c.execute(
                "INSERT OR REPLACE INTO runs(run_id, design_id, config_json, config_hash, "
                "tool_image, host_json, concurrency, repeat_index, injected_fault, status, "
                "exit_code, wall_s, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run.run_id,
                    run.design_id,
                    json.dumps(run.config, sort_keys=True),
                    run.config_hash,
                    run.tool_image,
                    json.dumps(run.host, sort_keys=True),
                    run.concurrency,
                    run.repeat_index,
                    run.injected_fault,
                    run.status,
                    run.exit_code,
                    run.wall_s,
                    run.started_at.isoformat(),
                ),
            )
            c.executemany(
                "INSERT INTO steps(run_id, step, stage, wall_s, cpu_user_s, cpu_sys_s, "
                "peak_rss_mb, metrics_json, log_path) VALUES (?,?,?,?,?,?,?,?,?)",
                [
                    (
                        s.run_id,
                        s.step,
                        s.stage,
                        s.wall_s,
                        s.cpu_user_s,
                        s.cpu_sys_s,
                        s.peak_rss_mb,
                        json.dumps(s.metrics, sort_keys=True),
                        s.log_path,
                    )
                    for s in steps
                ],
            )

    # -- reads --------------------------------------------------------------------------
    def runs(self, design_id: str | None = None) -> list[sqlite3.Row]:
        if design_id is None:
            return list(self._conn.execute("SELECT * FROM runs ORDER BY started_at"))
        return list(
            self._conn.execute(
                "SELECT * FROM runs WHERE design_id = ? ORDER BY started_at", (design_id,)
            )
        )

    def steps(self, run_id: str) -> list[sqlite3.Row]:
        return list(self._conn.execute("SELECT * FROM steps WHERE run_id = ?", (run_id,)))

    def stage_summary(self) -> list[sqlite3.Row]:
        """Per run and stage: summed wall/CPU time and max peak memory."""
        return list(
            self._conn.execute(
                "SELECT r.run_id, r.design_id, r.config_hash, r.repeat_index, s.stage, "
                "SUM(s.wall_s) AS wall_s, SUM(s.cpu_user_s + s.cpu_sys_s) AS cpu_s, "
                "MAX(s.peak_rss_mb) AS peak_rss_mb "
                "FROM runs r JOIN steps s ON s.run_id = r.run_id "
                "WHERE s.wall_s IS NOT NULL GROUP BY r.run_id, s.stage "
                "ORDER BY r.run_id, s.stage"
            )
        )
