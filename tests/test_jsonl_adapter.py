"""Loads the hand-written fixture and checks it maps into Trace/Step cleanly.

Run `pytest` for the assertions, or run this file directly
(`python tests/test_jsonl_adapter.py`) to pretty-print the parsed traces and
eyeball the schema.
"""

from pathlib import Path

from eval_harness.adapters import from_jsonl
from eval_harness.models import Step, Trace

FIXTURE = Path(__file__).parent / "fixtures" / "traces.jsonl"


def test_loads_all_traces():
    traces = from_jsonl(str(FIXTURE))
    assert len(traces) == 4
    assert all(isinstance(t, Trace) for t in traces)


def test_steps_parse_into_step_objects():
    traces = from_jsonl(str(FIXTURE))
    first = traces[0]
    assert all(isinstance(s, Step) for s in first.steps)
    # step order is preserved — basis for trajectory eval later
    assert [s.name for s in first.steps] == ["retrieval:rfp_fetch", "rfp_extraction"]


def test_source_is_tagged_jsonl():
    traces = from_jsonl(str(FIXTURE))
    assert all(t.metadata["source"] == "jsonl" for t in traces)


def test_version_tag_present():
    # version_tag is required for regression detection downstream.
    traces = from_jsonl(str(FIXTURE))
    assert all(t.metadata.get("version_tag") == "v1.2.0" for t in traces)


def test_optional_latency_preserved():
    traces = from_jsonl(str(FIXTURE))
    step = traces[0].steps[0]
    assert step.latency_ms == 320.5


def _pretty_print():
    import json
    from dataclasses import asdict

    traces = from_jsonl(str(FIXTURE))
    print(f"Loaded {len(traces)} traces from {FIXTURE}\n")
    for t in traces:
        print(json.dumps(asdict(t), indent=2))
        print("-" * 60)


if __name__ == "__main__":
    _pretty_print()
