"""Adapters normalize a source format into `list[Trace]`.

v1 ships exactly two: `from_jsonl` (reference/fallback) and `from_langsmith`
(validated against real Corpus data). The Protocol below documents the shape
future adapters should match — it is not a base class to subclass.
"""

from typing import Protocol

from eval_harness.adapters.jsonl import from_jsonl
from eval_harness.models import Trace


class Adapter(Protocol):
    def load(self, source: str, **kwargs) -> list[Trace]: ...


__all__ = ["Adapter", "from_jsonl"]
