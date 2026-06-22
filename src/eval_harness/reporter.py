"""Standalone report for a single stored run (the `report` command).

Reads results for one version tag from SQLite and renders them as either
markdown (default, human-readable) or JSON (structured, for piping/saving).
Both formats carry the same data: a per-evaluator summary plus a per-trace
breakdown with scores and judge reasoning where present.

Note: only actual results are persisted, so the summary reports `n/a`
(stored results with no pass/fail cutoff), not run-time skips (which `run`
returns separately and does not store).
"""

from __future__ import annotations

import json
from statistics import mean

from eval_harness import storage


class ReportError(Exception):
    """Raised when a report cannot be produced (e.g. the version tag is absent)."""


def _ordered_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def build_report(conn, version: str) -> dict:
    """Build the structured report data shared by both output formats."""
    rows = storage.fetch_results(conn, version)
    if not rows:
        raise ReportError(f"no results stored for version {version!r}")

    by_eval: dict[str, list] = {}
    for r in rows:
        by_eval.setdefault(r["evaluator_name"], []).append(r)

    summary = []
    for name in _ordered_unique([r["evaluator_name"] for r in rows]):
        rs = by_eval[name]
        scores = [r["score"] for r in rs if r["score"] is not None]
        summary.append(
            {
                "evaluator": name,
                "passed": sum(1 for r in rs if r["passed"] == 1),
                "failed": sum(1 for r in rs if r["passed"] == 0),
                "n_a": sum(1 for r in rs if r["passed"] is None),
                "avg_score": mean(scores) if scores else None,
            }
        )

    results = [
        {
            "trace_id": r["trace_id"],
            "evaluator": r["evaluator_name"],
            "score": r["score"],
            "passed": None if r["passed"] is None else bool(r["passed"]),
            "detail": r["detail"],
            "reasoning": r["reasoning"],
        }
        for r in rows
    ]

    return {"version": version, "summary": summary, "results": results}


def to_json(data: dict) -> str:
    return json.dumps(data, indent=2)


def to_markdown(data: dict) -> str:
    out = [f"# Eval Report — {data['version']}", "", "## Summary", ""]

    header = ["evaluator", "passed", "failed", "n/a", "avg_score"]
    out.append("| " + " | ".join(header) + " |")
    out.append("| " + " | ".join("---" for _ in header) + " |")
    for s in data["summary"]:
        avg = "-" if s["avg_score"] is None else f"{s['avg_score']:.2f}"
        out.append(
            "| "
            + " | ".join(
                [s["evaluator"], str(s["passed"]), str(s["failed"]), str(s["n_a"]), avg]
            )
            + " |"
        )

    out += ["", "## Per-trace results", ""]
    for trace_id in _ordered_unique([r["trace_id"] for r in data["results"]]):
        out.append(f"### {trace_id}")
        for r in data["results"]:
            if r["trace_id"] != trace_id:
                continue
            status = {True: "PASS", False: "FAIL", None: "n/a"}[r["passed"]]
            line = f"- **{r['evaluator']}**: {status}"
            if r["score"] is not None:
                line += f" — score {r['score']:g}"
            out.append(line)
            if r["reasoning"]:
                out.append(f"  - reasoning: {r['reasoning']}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render(conn, version: str, fmt: str) -> str:
    data = build_report(conn, version)
    return to_json(data) if fmt == "json" else to_markdown(data)
