"""YAML evaluator config loader with load-time validation.

`load_config` parses the YAML, builds typed evaluator objects, and validates
each one's required fields and shape — failing loudly before anything runs. If
`traces` are passed, it also checks that every evaluator's `target` dot-path
resolves against at least one trace, catching typo'd paths up front. (A path is
only flagged when it resolves against *no* trace; heterogeneous trace sets where
a field is present on some traces but not others are expected and allowed.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from eval_harness.dotpath import PathResolutionError, resolve_path
from eval_harness.evaluators.llm_judge import LLMJudgeEvaluator
from eval_harness.evaluators.threshold import ThresholdEvaluator
from eval_harness.models import Trace

Evaluator = Union[LLMJudgeEvaluator, ThresholdEvaluator]


class ConfigError(ValueError):
    """Raised for any malformed or unresolvable evaluator config."""


def load_config(path: str, traces: list[Trace] | None = None) -> list[Evaluator]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("evaluators"), list):
        raise ConfigError("config must have a top-level 'evaluators' list")
    if not raw["evaluators"]:
        raise ConfigError("config has no evaluators")

    evaluators = [_build(entry, i) for i, entry in enumerate(raw["evaluators"])]

    if traces is not None:
        _validate_targets(evaluators, traces)
    return evaluators


def _build(entry: dict, index: int) -> Evaluator:
    where = f"evaluator #{index}"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where}: must be a mapping")
    name = entry.get("name")
    if not name:
        raise ConfigError(f"{where}: missing 'name'")
    where = f"evaluator '{name}'"

    etype = entry.get("type")
    target = entry.get("target")
    if not target:
        raise ConfigError(f"{where}: missing 'target'")

    if etype == "threshold":
        return _build_threshold(entry, name, target, where)
    if etype == "llm_judge":
        return _build_llm_judge(entry, name, target, where)
    raise ConfigError(
        f"{where}: unknown type {etype!r} (expected 'llm_judge' or 'threshold')"
    )


def _build_threshold(entry: dict, name: str, target: str, where: str) -> ThresholdEvaluator:
    bounds = {k: entry[k] for k in ("max", "min", "equals") if k in entry}
    if len(bounds) != 1:
        raise ConfigError(
            f"{where}: threshold needs exactly one of max/min/equals, got {sorted(bounds) or 'none'}"
        )
    return ThresholdEvaluator(name=name, target=target, **bounds)


def _build_llm_judge(entry: dict, name: str, target: str, where: str) -> LLMJudgeEvaluator:
    rubric = entry.get("rubric")
    model = entry.get("model")
    if not rubric:
        raise ConfigError(f"{where}: llm_judge needs a 'rubric'")
    if not model:
        raise ConfigError(f"{where}: llm_judge needs a 'model'")
    if "/" not in model:
        raise ConfigError(
            f"{where}: model must be 'provider/model-name' "
            f"(e.g. 'anthropic/claude-sonnet-4-6'), got {model!r}"
        )
    threshold = entry.get("threshold")
    if threshold is not None and not isinstance(threshold, (int, float)):
        raise ConfigError(f"{where}: threshold must be a number, got {threshold!r}")
    return LLMJudgeEvaluator(
        name=name, target=target, rubric=rubric, model=model, threshold=threshold
    )


def _validate_targets(evaluators: list[Evaluator], traces: list[Trace]) -> None:
    for ev in evaluators:
        if not any(_resolves(t, ev.target) for t in traces):
            raise ConfigError(
                f"evaluator '{ev.name}': target '{ev.target}' does not resolve "
                f"against any of the {len(traces)} loaded traces"
            )


def _resolves(trace: Trace, path: str) -> bool:
    try:
        resolve_path(trace, path)
        return True
    except PathResolutionError:
        return False
