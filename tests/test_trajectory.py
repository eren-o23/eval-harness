"""Tests for the trajectory evaluator and its config validation."""

from __future__ import annotations

import pytest

from eval_harness.adapters import from_jsonl
from eval_harness.config import ConfigError, load_config
from eval_harness.evaluators.trajectory import TrajectoryEvaluator

FIXTURE = "tests/fixtures/traces.jsonl"


def _trace(trace_id):
    return next(t for t in from_jsonl(FIXTURE) if t.id == trace_id)


def test_full_sequence_present_passes():
    # trace-004 steps: retrieval:rfp_fetch -> rfp_extraction -> draft_loi
    trace = _trace("trace-004")
    ev = TrajectoryEvaluator(name="order", expected_sequence=["retrieval:rfp_fetch", "draft_loi"])
    result = ev.evaluate(trace)
    assert result.passed is True


def test_missing_step_fails_and_detail_names_it():
    trace = _trace("trace-004")
    ev = TrajectoryEvaluator(name="order", expected_sequence=["rfp_extraction", "grant_search"])
    result = ev.evaluate(trace)
    assert result.passed is False
    assert "grant_search" in result.detail  # detail names the missing step


def test_out_of_order_fails():
    # steps are rfp_extraction THEN draft_loi; expecting the reverse must fail
    trace = _trace("trace-004")
    ev = TrajectoryEvaluator(name="order", expected_sequence=["draft_loi", "rfp_extraction"])
    result = ev.evaluate(trace)
    assert result.passed is False
    assert "rfp_extraction" in result.detail


def test_empty_expected_sequence_fails_config_validation(tmp_path):
    cfg = tmp_path / "evals.yaml"
    cfg.write_text(
        "evaluators:\n"
        "  - name: order\n"
        "    type: trajectory\n"
        "    expected_sequence: []\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="non-empty"):
        load_config(str(cfg))


def test_non_string_expected_sequence_fails_config_validation(tmp_path):
    cfg = tmp_path / "evals.yaml"
    cfg.write_text(
        "evaluators:\n"
        "  - name: order\n"
        "    type: trajectory\n"
        "    expected_sequence: [1, 2, 3]\n",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="list of strings"):
        load_config(str(cfg))
