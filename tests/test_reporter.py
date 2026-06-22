"""Tests for the report command — no API calls; DB state built via save_results."""

from __future__ import annotations

import json

import pytest

from eval_harness import storage
from eval_harness.evaluators.base import EvalResult
from eval_harness.reporter import ReportError, render


def _seed(conn):
    storage.save_results(
        conn,
        "v1",
        [
            EvalResult(
                evaluator="rfp_accuracy",
                trace_id="t1",
                passed=True,
                score=5.0,
                reasoning="all fields captured",
            ),
            EvalResult(
                evaluator="rfp_accuracy",
                trace_id="t2",
                passed=False,
                score=2.0,
                reasoning="missing deadline",
            ),
            EvalResult(evaluator="latency", trace_id="t1", passed=True),
            EvalResult(evaluator="latency", trace_id="t2", passed=False),
        ],
    )


def test_markdown_contains_names_scores_and_counts(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    _seed(conn)

    md = render(conn, "v1", "md")

    assert "# Eval Report — v1" in md
    assert "rfp_accuracy" in md and "latency" in md
    # summary row: rfp_accuracy has 1 passed, 1 failed, avg 3.50
    assert "| rfp_accuracy | 1 | 1 | 0 | 3.50 |" in md
    # per-trace breakdown carries score and judge reasoning
    assert "score 5" in md
    assert "reasoning: all fields captured" in md


def test_json_is_valid_and_structured(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    _seed(conn)

    data = json.loads(render(conn, "v1", "json"))

    assert data["version"] == "v1"
    names = {s["evaluator"] for s in data["summary"]}
    assert names == {"rfp_accuracy", "latency"}
    rfp = next(s for s in data["summary"] if s["evaluator"] == "rfp_accuracy")
    assert rfp == {"evaluator": "rfp_accuracy", "passed": 1, "failed": 1, "n_a": 0, "avg_score": 3.5}
    assert len(data["results"]) == 4


def test_missing_version_fails_loudly(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    _seed(conn)

    with pytest.raises(ReportError):
        render(conn, "does-not-exist", "md")
