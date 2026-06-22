"""Result shape shared by all evaluators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvalResult:
    evaluator: str  # evaluator name from the config
    trace_id: str
    passed: bool | None  # pass/fail; None when no cutoff applies (judge w/o threshold)
    score: float | None = None  # llm_judge 1-5; None for threshold
    value: Any = None  # threshold: the resolved target value
    reasoning: str | None = None  # llm_judge: raw judge reasoning
    detail: str = ""  # human-readable explanation of the outcome
