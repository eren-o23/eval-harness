"""Run evaluators over traces and format a stdout summary."""

from __future__ import annotations

from statistics import mean

from eval_harness.dotpath import PathResolutionError
from eval_harness.evaluators.base import EvalResult


def run_evaluations(traces, evaluators) -> tuple[list[EvalResult], list[tuple[str, str]]]:
    """Evaluate every evaluator against every trace.

    Returns (results, skipped). A trace is skipped for an evaluator when its
    target dot-path doesn't resolve on that trace (heterogeneous trace sets are
    expected — see config validation). Skipping happens before any model call.
    """
    results: list[EvalResult] = []
    skipped: list[tuple[str, str]] = []
    for ev in evaluators:
        for trace in traces:
            try:
                results.append(ev.evaluate(trace))
            except PathResolutionError:
                skipped.append((ev.name, trace.id))
    return results, skipped


def format_summary(evaluators, results, skipped) -> str:
    by_eval: dict[str, list[EvalResult]] = {}
    for r in results:
        by_eval.setdefault(r.evaluator, []).append(r)

    skip_counts: dict[str, int] = {}
    for name, _trace_id in skipped:
        skip_counts[name] = skip_counts.get(name, 0) + 1

    headers = ["evaluator", "type", "passed", "failed", "n/a", "avg_score", "skipped"]
    rows = [headers]
    for ev in evaluators:
        rs = by_eval.get(ev.name, [])
        scores = [r.score for r in rs if r.score is not None]
        rows.append(
            [
                ev.name,
                ev.type,
                str(sum(1 for r in rs if r.passed is True)),
                str(sum(1 for r in rs if r.passed is False)),
                str(sum(1 for r in rs if r.passed is None)),
                f"{mean(scores):.2f}" if scores else "-",
                str(skip_counts.get(ev.name, 0)),
            ]
        )
    return _render_table(rows)


def _render_table(rows: list[list[str]]) -> str:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    line = "  ".join("{:<{}}".format(rows[0][i], widths[i]) for i in range(len(widths)))
    sep = "  ".join("-" * widths[i] for i in range(len(widths)))
    out = [line, sep]
    for row in rows[1:]:
        out.append("  ".join("{:<{}}".format(row[i], widths[i]) for i in range(len(widths))))
    return "\n".join(out)
