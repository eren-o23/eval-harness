"""Trajectory evaluator — deterministic subsequence check over step names.

Passes when `expected_sequence` appears as a subsequence of the trace's actual
`step.name` values: every expected step present, in order, gaps allowed. No
model call. On failure the detail names the expected step where the match broke.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from eval_harness.evaluators.base import EvalResult
from eval_harness.models import Trace


@dataclass
class TrajectoryEvaluator:
    name: str
    expected_sequence: List[str]

    type = "trajectory"

    def evaluate(self, trace: Trace) -> EvalResult:
        actual = [s.name for s in trace.steps]

        i = 0  # index of the next expected step to match
        for step_name in actual:
            if i < len(self.expected_sequence) and step_name == self.expected_sequence[i]:
                i += 1

        passed = i == len(self.expected_sequence)
        if passed:
            detail = (
                f"matched all {len(self.expected_sequence)} expected step(s) in order"
            )
        else:
            detail = (
                f"sequence broke at expected step '{self.expected_sequence[i]}' "
                f"(index {i}): not found in order after matching "
                f"{i}/{len(self.expected_sequence)}; actual steps: {actual}"
            )
        return EvalResult(
            evaluator=self.name,
            trace_id=trace.id,
            passed=passed,
            detail=detail,
        )
