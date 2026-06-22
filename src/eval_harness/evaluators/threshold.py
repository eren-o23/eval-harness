"""Threshold evaluator — deterministic comparison, no model call."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eval_harness.dotpath import resolve_path
from eval_harness.evaluators.base import EvalResult
from eval_harness.models import Trace


@dataclass
class ThresholdEvaluator:
    name: str
    target: str
    max: float | None = None
    min: float | None = None
    equals: Any = None

    type = "threshold"

    def evaluate(self, trace: Trace) -> EvalResult:
        value = resolve_path(trace, self.target)
        if self.max is not None:
            passed = value <= self.max
            detail = f"{value} {'<=' if passed else '>'} max {self.max}"
        elif self.min is not None:
            passed = value >= self.min
            detail = f"{value} {'>=' if passed else '<'} min {self.min}"
        else:
            passed = value == self.equals
            detail = f"{value} {'==' if passed else '!='} {self.equals!r}"
        return EvalResult(
            evaluator=self.name,
            trace_id=trace.id,
            passed=passed,
            value=value,
            detail=detail,
        )
