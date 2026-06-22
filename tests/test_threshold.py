"""Threshold evaluator + config loader tests.

These are deterministic and make no model calls. The key assertion the spec
calls out: trace-004 (total_latency_ms = 8830) must FAIL a max: 4000 threshold.
"""

from pathlib import Path

import pytest

from eval_harness.adapters import from_jsonl
from eval_harness.config import ConfigError, load_config
from eval_harness.evaluators.threshold import ThresholdEvaluator

FIXTURE = Path(__file__).parent / "fixtures" / "traces.jsonl"
EXAMPLE_CONFIG = Path(__file__).parents[1] / "examples" / "evals.yaml"


def _traces():
    return from_jsonl(str(FIXTURE))


def _by_id(traces, tid):
    return next(t for t in traces if t.id == tid)


# --- threshold: max ---------------------------------------------------------

def test_slow_trace_fails_max_latency():
    ev = ThresholdEvaluator(name="lat", target="metadata.total_latency_ms", max=4000)
    slow = _by_id(_traces(), "trace-004")  # 8830 ms
    result = ev.evaluate(slow)
    assert result.passed is False
    assert result.value == 8830.0
    assert "8830" in result.detail and "4000" in result.detail


def test_fast_trace_passes_max_latency():
    ev = ThresholdEvaluator(name="lat", target="metadata.total_latency_ms", max=4000)
    fast = _by_id(_traces(), "trace-002")  # 1630 ms
    assert ev.evaluate(fast).passed is True


def test_max_latency_across_fixture():
    ev = ThresholdEvaluator(name="lat", target="metadata.total_latency_ms", max=4000)
    results = {t.id: ev.evaluate(t).passed for t in _traces()}
    # Only trace-004 is over 4000 ms.
    assert results == {
        "trace-001": True,
        "trace-002": True,
        "trace-003": True,
        "trace-004": False,
    }


# --- threshold: min / equals ------------------------------------------------

def test_min_threshold():
    ev = ThresholdEvaluator(name="cost", target="metadata.total_cost_usd", min=0.01)
    assert ev.evaluate(_by_id(_traces(), "trace-004")).passed is True  # 0.0152
    assert ev.evaluate(_by_id(_traces(), "trace-002")).passed is False  # 0.0019


def test_equals_threshold():
    ev = ThresholdEvaluator(name="tag", target="metadata.version_tag", equals="v1.2.0")
    assert all(ev.evaluate(t).passed for t in _traces())


# --- config loader ----------------------------------------------------------

def test_loads_example_config():
    evaluators = load_config(str(EXAMPLE_CONFIG), traces=_traces())
    assert [e.name for e in evaluators] == [
        "rfp_extraction_accuracy",
        "extraction_latency",
    ]
    assert evaluators[0].type == "llm_judge"
    assert evaluators[0].model == "anthropic/claude-sonnet-4-6"
    assert evaluators[1].type == "threshold"
    assert evaluators[1].max == 4000


def test_unknown_type_rejected(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("evaluators:\n  - name: x\n    type: bleu\n    target: output.x\n")
    with pytest.raises(ConfigError, match="unknown type"):
        load_config(str(cfg))


def test_unresolvable_target_rejected(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "evaluators:\n  - name: x\n    type: threshold\n"
        "    target: output.nope_does_not_exist\n    max: 1\n"
    )
    with pytest.raises(ConfigError, match="does not resolve"):
        load_config(str(cfg), traces=_traces())


def test_threshold_requires_exactly_one_bound(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "evaluators:\n  - name: x\n    type: threshold\n"
        "    target: metadata.total_latency_ms\n    max: 1\n    min: 0\n"
    )
    with pytest.raises(ConfigError, match="exactly one"):
        load_config(str(cfg))


def test_llm_judge_requires_provider_qualified_model(tmp_path):
    cfg = tmp_path / "bad.yaml"
    cfg.write_text(
        "evaluators:\n  - name: x\n    type: llm_judge\n"
        "    target: output.extracted_fields\n    rubric: score it\n"
        "    model: claude-sonnet-4-6\n"  # missing provider/ prefix
    )
    with pytest.raises(ConfigError, match="provider/model-name"):
        load_config(str(cfg))
