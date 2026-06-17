"""Core data model.

Every adapter normalizes its source format into these two dataclasses. Nothing
downstream (evaluators, regression detection, reporting) touches the original
format — only `Trace`.

Adapters may NOT add required fields to `Trace` or `Step`. Anything
source-specific goes in `metadata`. That constraint is what keeps the
evaluators format-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    name: str  # e.g. "rfp_extraction", "tool:search_grants"
    type: str  # "llm_call" | "tool_call" | "retrieval" | "other"
    input: dict
    output: dict
    latency_ms: float | None = None
    metadata: dict = field(default_factory=dict)  # model, token counts, etc.

    @classmethod
    def from_dict(cls, data: dict) -> Step:
        return cls(
            name=data["name"],
            type=data["type"],
            input=data.get("input", {}),
            output=data.get("output", {}),
            latency_ms=data.get("latency_ms"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Trace:
    id: str  # stable ID from source system, or generated
    input: dict  # the original top-level input to the agent/chain
    output: dict  # the final output
    steps: list[Step] = field(default_factory=list)  # ordered; order matters
    metadata: dict = field(default_factory=dict)  # version_tag, timestamp,
    # total_latency_ms, total_cost_usd, source ("langsmith" | "jsonl")

    @classmethod
    def from_dict(cls, data: dict) -> Trace:
        return cls(
            id=data["id"],
            input=data.get("input", {}),
            output=data.get("output", {}),
            steps=[Step.from_dict(s) for s in data.get("steps", [])],
            metadata=data.get("metadata", {}),
        )
