"""SQLite storage round-trip tests."""

from eval_harness import storage
from eval_harness.evaluators.base import EvalResult


def _conn():
    return storage.connect(":memory:")


def test_save_and_fetch_roundtrip():
    conn = _conn()
    results = [
        EvalResult(evaluator="lat", trace_id="t1", passed=True, value=1630.0, detail="ok"),
        EvalResult(
            evaluator="acc", trace_id="t1", passed=True, score=5.0,
            reasoning="all fields correct", detail="score 5",
        ),
        EvalResult(evaluator="acc", trace_id="t2", passed=None, score=3.0, reasoning="meh"),
    ]
    n = storage.save_results(conn, "v1", results)
    assert n == 3

    rows = storage.fetch_results(conn, "v1")
    assert len(rows) == 3
    assert {r["evaluator_name"] for r in rows} == {"lat", "acc"}

    # passed stored as 1/0/NULL
    acc_t2 = next(r for r in rows if r["evaluator_name"] == "acc" and r["trace_id"] == "t2")
    assert acc_t2["passed"] is None
    assert acc_t2["score"] == 3.0
    assert acc_t2["reasoning"] == "meh"

    lat = next(r for r in rows if r["evaluator_name"] == "lat")
    assert lat["passed"] == 1
    assert lat["score"] is None  # threshold produces no score


def test_version_tagging_isolates_runs():
    conn = _conn()
    storage.save_results(conn, "v1", [EvalResult("lat", "t1", passed=True)])
    storage.save_results(conn, "v2", [EvalResult("lat", "t1", passed=False)])
    assert len(storage.fetch_results(conn, "v1")) == 1
    assert storage.fetch_results(conn, "v1")[0]["passed"] == 1
    assert storage.fetch_results(conn, "v2")[0]["passed"] == 0


def test_every_row_carries_a_timestamp():
    conn = _conn()
    storage.save_results(conn, "v1", [EvalResult("lat", "t1", passed=True)])
    assert storage.fetch_results(conn, "v1")[0]["created_at"]
