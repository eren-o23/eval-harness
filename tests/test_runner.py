"""Runner orchestration + summary formatting (no model calls).

Uses threshold evaluators only so the runner can be exercised deterministically;
the llm_judge path through the runner is covered by the real end-to-end CLI run.
"""

from pathlib import Path

from eval_harness.adapters import from_jsonl
from eval_harness.evaluators.threshold import ThresholdEvaluator
from eval_harness.runner import format_summary, run_evaluations

FIXTURE = Path(__file__).parent / "fixtures" / "traces.jsonl"


def _traces():
    return from_jsonl(str(FIXTURE))


def test_runs_all_evaluators_over_all_traces():
    evs = [ThresholdEvaluator(name="lat", target="metadata.total_latency_ms", max=4000)]
    results, skipped = run_evaluations(_traces(), evs)
    assert len(results) == 4  # one per trace
    assert skipped == []
    assert sum(1 for r in results if r.passed is False) == 1  # trace-004


def test_skips_traces_missing_the_target():
    # output.extracted_fields is absent on trace-003 only.
    evs = [ThresholdEvaluator(name="acc", target="output.extracted_fields", equals=None)]
    results, skipped = run_evaluations(_traces(), evs)
    assert len(results) == 3
    assert skipped == [("acc", "trace-003")]


def test_summary_table_reports_counts():
    evs = [ThresholdEvaluator(name="lat", target="metadata.total_latency_ms", max=4000)]
    results, skipped = run_evaluations(_traces(), evs)
    table = format_summary(evs, results, skipped)
    assert "evaluator" in table and "avg_score" in table
    lat_line = next(ln for ln in table.splitlines() if ln.startswith("lat"))
    # passed=3, failed=1, threshold has no score -> "-"
    assert "3" in lat_line and "1" in lat_line and "-" in lat_line
