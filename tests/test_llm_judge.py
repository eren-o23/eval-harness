"""LLM-judge evaluator tests.

No network, no API keys, no SDKs. Each test injects a fake `complete` callable
(signature: (model, system, user) -> str) via the evaluate() seam, so we test
target resolution, prompt construction, response parsing, and threshold logic in
isolation from any real provider.
"""

from pathlib import Path

import pytest

from eval_harness.adapters import from_jsonl
from eval_harness.evaluators.llm_judge import LLMJudgeEvaluator

FIXTURE = Path(__file__).parent / "fixtures" / "traces.jsonl"


def _trace(tid="trace-001"):
    traces = from_jsonl(str(FIXTURE))
    return next(t for t in traces if t.id == tid)


def _judge(**kw):
    defaults = dict(
        name="accuracy",
        target="output.extracted_fields",
        rubric="Score the extraction.",
        model="anthropic/claude-sonnet-4-6",
    )
    defaults.update(kw)
    return LLMJudgeEvaluator(**defaults)


def _fixed(response):
    """A fake completion that ignores its inputs and returns `response`."""
    return lambda model, system, user: response


# --- happy path -------------------------------------------------------------

def test_parses_score_and_reasoning():
    ev = _judge()
    result = ev.evaluate(
        _trace(),
        complete=_fixed('{"score": 5, "reasoning": "all fields correct"}'),
    )
    assert result.score == 5.0
    assert result.reasoning == "all fields correct"
    assert result.evaluator == "accuracy"
    assert result.trace_id == "trace-001"


def test_no_threshold_leaves_passed_none():
    result = _judge().evaluate(_trace(), complete=_fixed('{"score": 3}'))
    assert result.score == 3.0
    assert result.passed is None


def test_threshold_pass_and_fail():
    above = _judge(threshold=4).evaluate(_trace(), complete=_fixed('{"score": 4}'))
    below = _judge(threshold=4).evaluate(_trace(), complete=_fixed('{"score": 3}'))
    assert above.passed is True
    assert below.passed is False


def test_json_wrapped_in_prose_is_extracted():
    raw = 'Here is my assessment:\n{"score": 2, "reasoning": "missing deadline"}\nDone.'
    result = _judge().evaluate(_trace(), complete=_fixed(raw))
    assert result.score == 2.0
    assert result.reasoning == "missing deadline"


# --- the target value actually reaches the prompt ---------------------------

def test_resolved_target_is_sent_to_model():
    captured = {}

    def spy(model, system, user):
        captured["model"] = model
        captured["user"] = user
        return '{"score": 5}'

    _judge().evaluate(_trace(), complete=spy)
    assert captured["model"] == "anthropic/claude-sonnet-4-6"
    # output.extracted_fields for trace-001 includes this funding amount.
    assert "500000" in captured["user"]
    assert "Score the extraction." in captured["user"]


# --- malformed responses raise loudly ---------------------------------------

def test_non_json_raises():
    with pytest.raises(ValueError, match="not JSON"):
        _judge().evaluate(_trace(), complete=_fixed("totally not json"))


def test_missing_score_raises():
    with pytest.raises(ValueError, match="missing 'score'"):
        _judge().evaluate(_trace(), complete=_fixed('{"reasoning": "no score here"}'))


def test_out_of_range_score_raises():
    with pytest.raises(ValueError, match="outside 1-5"):
        _judge().evaluate(_trace(), complete=_fixed('{"score": 7}'))


def test_boolean_score_rejected():
    # JSON `true` parses to Python bool, which is an int subclass — reject it.
    with pytest.raises(ValueError, match="not numeric"):
        _judge().evaluate(_trace(), complete=_fixed('{"score": true}'))
