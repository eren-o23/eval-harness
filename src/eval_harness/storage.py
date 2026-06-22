"""SQLite storage for evaluation results.

Deliberately minimal — a single `results` table, tagged with a version label.
This is local result storage, not a database product. The `diff` and `report`
commands (later steps) read from the same table.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from eval_harness.evaluators.base import EvalResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS results (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    version_tag    TEXT NOT NULL,
    trace_id       TEXT NOT NULL,
    evaluator_name TEXT NOT NULL,
    score          REAL,            -- nullable: only llm_judge produces a score
    passed         INTEGER,         -- 1 / 0 / NULL (NULL = no pass/fail cutoff)
    detail         TEXT,
    reasoning      TEXT,
    created_at     TEXT NOT NULL    -- ISO-8601 UTC, one timestamp per run
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def save_results(
    conn: sqlite3.Connection, version_tag: str, results: list[EvalResult]
) -> int:
    """Persist results under `version_tag`. Returns the number of rows written."""
    created_at = datetime.now(timezone.utc).isoformat()
    rows = [
        (
            version_tag,
            r.trace_id,
            r.evaluator,
            r.score,
            None if r.passed is None else int(r.passed),
            r.detail,
            r.reasoning,
            created_at,
        )
        for r in results
    ]
    conn.executemany(
        "INSERT INTO results "
        "(version_tag, trace_id, evaluator_name, score, passed, detail, reasoning, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    return len(rows)


def fetch_results(conn: sqlite3.Connection, version_tag: str) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM results WHERE version_tag = ? ORDER BY id", (version_tag,)
    )
    return cur.fetchall()
