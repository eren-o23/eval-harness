"""Tests for the diff command — no API calls; DB state built via save_results."""

from __future__ import annotations

import pytest

from eval_harness import storage
from eval_harness.differ import DiffError, compute_diff
from eval_harness.evaluators.base import EvalResult


def _result(trace_id, score, passed, name="rfp_accuracy"):
    return EvalResult(evaluator=name, trace_id=trace_id, passed=passed, score=score)


def test_regressions_flagged_largest_drop_first(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    storage.save_results(
        conn,
        "v1",
        [_result("t1", 5.0, True), _result("t2", 5.0, True), _result("t3", 5.0, True)],
    )
    storage.save_results(
        conn,
        "v2",
        # t1 drops 3, t2 drops 1, t3 unchanged
        [_result("t1", 2.0, False), _result("t2", 4.0, True), _result("t3", 5.0, True)],
    )

    diff = compute_diff(conn, "v1", "v2")
    ed = diff.evaluators[0]

    assert [d.trace_id for d in ed.regressions] == ["t1", "t2"]  # largest drop first
    assert (ed.regressions[0].score_a, ed.regressions[0].score_b) == (5.0, 2.0)
    assert ed.regressions[0].passed_a is True and ed.regressions[0].passed_b is False


def test_missing_version_fails_loudly(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    storage.save_results(conn, "v1", [_result("t1", 5.0, True)])

    with pytest.raises(DiffError):
        compute_diff(conn, "v1", "does-not-exist")
    with pytest.raises(DiffError):
        compute_diff(conn, "does-not-exist", "v1")


def test_trace_removed_in_b(tmp_path):
    conn = storage.connect(str(tmp_path / "r.sqlite"))
    storage.save_results(conn, "v1", [_result("t1", 5.0, True), _result("t2", 4.0, True)])
    storage.save_results(conn, "v2", [_result("t1", 5.0, True)])

    diff = compute_diff(conn, "v1", "v2")
    ed = diff.evaluators[0]

    assert [d.trace_id for d in ed.removed] == ["t2"]
    assert ed.removed[0].status == "removed"
    assert not ed.regressions  # a removed trace is not a regression
