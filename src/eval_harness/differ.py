"""Compare two stored eval runs and report regressions (the `diff` command).

Reads results for two version tags from SQLite and, per evaluator, computes the
score delta, pass-rate delta, and the specific traces that regressed — a trace
whose score dropped or whose pass/fail flipped from pass to fail. Traces present
in only one version are reported as added/removed rather than silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from eval_harness import storage


class DiffError(Exception):
    """Raised when a diff cannot be computed (e.g. a version tag is absent)."""


@dataclass
class TraceDelta:
    evaluator: str
    trace_id: str
    score_a: float | None
    score_b: float | None
    passed_a: bool | None
    passed_b: bool | None
    status: str  # regressed | improved | unchanged | added | removed


@dataclass
class EvaluatorDiff:
    name: str
    score_delta: float | None  # mean(score_b) - mean(score_a); None if either side has no scores
    pass_rate_delta: float | None  # fraction in [-1, 1]; None if either side has no pass/fail
    regressions: list[TraceDelta]  # sorted by score drop, largest first
    added: list[TraceDelta]
    removed: list[TraceDelta]


@dataclass
class Diff:
    version_a: str
    version_b: str
    evaluators: list[EvaluatorDiff]


def _to_bool(v) -> bool | None:
    return None if v is None else bool(v)


def _ordered_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _classify(sa, sb, pa, pb) -> str:
    score_dropped = sa is not None and sb is not None and sb < sa
    pass_flipped_bad = pa is True and pb is False
    if score_dropped or pass_flipped_bad:
        return "regressed"
    score_improved = sa is not None and sb is not None and sb > sa
    pass_flipped_good = pa is False and pb is True
    if score_improved or pass_flipped_good:
        return "improved"
    return "unchanged"


def compute_diff(conn, version_a: str, version_b: str) -> Diff:
    rows_a = storage.fetch_results(conn, version_a)
    rows_b = storage.fetch_results(conn, version_b)
    if not rows_a:
        raise DiffError(f"no results stored for version {version_a!r}")
    if not rows_b:
        raise DiffError(f"no results stored for version {version_b!r}")

    by_a: dict[str, dict] = {}
    by_b: dict[str, dict] = {}
    for r in rows_a:
        by_a.setdefault(r["evaluator_name"], {})[r["trace_id"]] = r
    for r in rows_b:
        by_b.setdefault(r["evaluator_name"], {})[r["trace_id"]] = r

    ev_names = _ordered_unique(
        [r["evaluator_name"] for r in rows_a] + [r["evaluator_name"] for r in rows_b]
    )

    evaluators: list[EvaluatorDiff] = []
    for name in ev_names:
        ta = by_a.get(name, {})
        tb = by_b.get(name, {})
        trace_ids = _ordered_unique(list(ta) + list(tb))

        deltas: list[TraceDelta] = []
        for tid in trace_ids:
            ra, rb = ta.get(tid), tb.get(tid)
            if ra is None:
                deltas.append(
                    TraceDelta(name, tid, None, rb["score"], None, _to_bool(rb["passed"]), "added")
                )
            elif rb is None:
                deltas.append(
                    TraceDelta(name, tid, ra["score"], None, _to_bool(ra["passed"]), None, "removed")
                )
            else:
                sa, sb = ra["score"], rb["score"]
                pa, pb = _to_bool(ra["passed"]), _to_bool(rb["passed"])
                deltas.append(TraceDelta(name, tid, sa, sb, pa, pb, _classify(sa, sb, pa, pb)))

        regressions = [d for d in deltas if d.status == "regressed"]
        regressions.sort(key=_score_drop, reverse=True)
        added = [d for d in deltas if d.status == "added"]
        removed = [d for d in deltas if d.status == "removed"]

        scores_a = [r["score"] for r in ta.values() if r["score"] is not None]
        scores_b = [r["score"] for r in tb.values() if r["score"] is not None]
        score_delta = mean(scores_b) - mean(scores_a) if scores_a and scores_b else None

        pass_a = [bool(r["passed"]) for r in ta.values() if r["passed"] is not None]
        pass_b = [bool(r["passed"]) for r in tb.values() if r["passed"] is not None]
        rate_a = sum(pass_a) / len(pass_a) if pass_a else None
        rate_b = sum(pass_b) / len(pass_b) if pass_b else None
        pass_rate_delta = rate_b - rate_a if rate_a is not None and rate_b is not None else None

        evaluators.append(
            EvaluatorDiff(name, score_delta, pass_rate_delta, regressions, added, removed)
        )

    return Diff(version_a, version_b, evaluators)


def _score_drop(d: TraceDelta) -> float:
    if d.score_a is not None and d.score_b is not None:
        return d.score_a - d.score_b
    return 0.0


# --- formatting ---------------------------------------------------------------


def _fmt_score(v: float | None) -> str:
    return "-" if v is None else f"{v:g}"


def _fmt_delta(v: float | None) -> str:
    return "-" if v is None else f"{v:+.2f}"


def _fmt_rate_delta(v: float | None) -> str:
    return "-" if v is None else f"{v * 100:+.0f}%"


def format_diff(diff: Diff) -> str:
    headers = ["evaluator", "score_delta", "pass_rate_delta", "regressions"]
    rows = [headers]
    for ed in diff.evaluators:
        rows.append(
            [
                ed.name,
                _fmt_delta(ed.score_delta),
                _fmt_rate_delta(ed.pass_rate_delta),
                str(len(ed.regressions)),
            ]
        )

    out = [f"Diff {diff.version_a} -> {diff.version_b}", "", _render_table(rows), ""]

    out.append("Regressions:")
    reg = [d for ed in diff.evaluators for d in ed.regressions]
    if reg:
        for d in reg:
            out.append(f"  {_fmt_regression(d)}")
    else:
        out.append("  (none)")

    out.append("")
    out.append("Added/removed traces:")
    moved = [
        (d, "+", diff.version_b) for ed in diff.evaluators for d in ed.added
    ] + [(d, "-", diff.version_a) for ed in diff.evaluators for d in ed.removed]
    if moved:
        for d, sign, only_in in moved:
            out.append(f"  {sign} {d.evaluator} / {d.trace_id} (only in {only_in})")
    else:
        out.append("  (none)")

    return "\n".join(out)


def _fmt_regression(d: TraceDelta) -> str:
    parts = [f"{d.evaluator} / {d.trace_id}:"]
    if d.score_a is not None or d.score_b is not None:
        parts.append(f"score {_fmt_score(d.score_a)} -> {_fmt_score(d.score_b)}")
    if d.passed_a is True and d.passed_b is False:
        parts.append("(pass -> fail)")
    return " ".join(parts)


def _render_table(rows: list[list[str]]) -> str:
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    out = []
    for idx, row in enumerate(rows):
        out.append("  ".join("{:<{}}".format(row[i], widths[i]) for i in range(len(widths))))
        if idx == 0:
            out.append("  ".join("-" * widths[i] for i in range(len(widths))))
    return "\n".join(out)
