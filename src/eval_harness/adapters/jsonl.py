"""JSONL adapter — the reference/test adapter.

Reads a `.jsonl` file, one JSON object per line, each matching the `Trace`
shape. Simplest possible adapter and the fallback for anyone not using
LangSmith.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval_harness.models import Trace


def from_jsonl(path: str) -> list[Trace]:
    """Load traces from a JSONL file (one Trace-shaped JSON object per line).

    Blank lines are skipped. The `source` metadata field is set to "jsonl" on
    every trace, since the adapter knows its own origin.
    """
    traces: list[Trace] = []
    with Path(path).open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e
            try:
                trace = Trace.from_dict(data)
            except KeyError as e:
                raise ValueError(
                    f"{path}:{lineno}: missing required field {e}"
                ) from e
            trace.metadata["source"] = "jsonl"
            traces.append(trace)
    return traces
