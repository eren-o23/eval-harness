"""LLM-judge evaluator — sends target + rubric to a model, parses a 1-5 score."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable

from eval_harness.dotpath import resolve_path
from eval_harness.evaluators.base import EvalResult
from eval_harness.llm import get_completion
from eval_harness.models import Trace

_SYSTEM = (
    "You are a strict evaluator. Score the provided target on an integer scale "
    "of 1 to 5 according to the rubric. Respond with ONLY a JSON object of the "
    'form {"score": <int 1-5>, "reasoning": "<one or two sentences>"} and nothing else.'
)

# Complete = the seam tests inject. Signature matches eval_harness.llm.get_completion.
Complete = Callable[[str, str, str], str]


@dataclass
class LLMJudgeEvaluator:
    name: str
    target: str
    rubric: str
    model: str  # provider-qualified, e.g. "anthropic/claude-sonnet-4-6"
    threshold: int | None = None  # optional pass/fail cutoff (score >= threshold)

    type = "llm_judge"

    def evaluate(self, trace: Trace, complete: Complete | None = None) -> EvalResult:
        """Score one trace. `complete` defaults to the real provider client;
        tests inject a stand-in to avoid network calls."""
        call = complete or get_completion
        value = resolve_path(trace, self.target)
        user = (
            f"Rubric:\n{self.rubric}\n\n"
            f"Source input (for reference):\n{json.dumps(trace.input, indent=2, default=str)}\n\n"
            f"Target to evaluate:\n{json.dumps(value, indent=2, default=str)}"
        )
        raw = call(self.model, _SYSTEM, user)
        score, reasoning = _parse_score(raw)
        passed = None if self.threshold is None else score >= self.threshold
        detail = f"score {score}" + (
            f" (threshold {self.threshold})" if self.threshold is not None else ""
        )
        return EvalResult(
            evaluator=self.name,
            trace_id=trace.id,
            passed=passed,
            score=score,
            reasoning=reasoning,
            detail=detail,
        )


def _parse_score(raw: str) -> tuple[float, str]:
    """Parse {"score", "reasoning"} from the judge's response. Tolerates the
    JSON being wrapped in surrounding prose, but not a missing/out-of-range score."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError(f"judge response is not JSON: {raw!r}")
        data = json.loads(match.group(0))

    if "score" not in data:
        raise ValueError(f"judge response missing 'score': {raw!r}")
    score = data["score"]
    if not isinstance(score, (int, float)) or isinstance(score, bool):
        raise ValueError(f"judge score is not numeric: {score!r}")
    if not 1 <= score <= 5:
        raise ValueError(f"judge score {score} outside 1-5")
    return float(score), data.get("reasoning", "")
