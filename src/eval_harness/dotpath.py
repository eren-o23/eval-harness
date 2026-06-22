"""Resolve a dot-path (e.g. "output.extracted_fields") against a Trace.

The first segment is a `Trace` attribute (`input`, `output`, `metadata`, `id`,
`steps`); subsequent segments index into nested dicts. This is the single seam
every evaluator uses to pull its `target` value out of a trace.
"""

from __future__ import annotations

from typing import Any

from eval_harness.models import Trace


class PathResolutionError(KeyError):
    """Raised when a dot-path does not resolve against a trace."""


def resolve_path(trace: Trace, path: str) -> Any:
    parts = path.split(".")
    try:
        obj: Any = getattr(trace, parts[0])
    except AttributeError as e:
        raise PathResolutionError(
            f"trace {trace.id}: '{parts[0]}' is not a Trace field (in '{path}')"
        ) from e
    for part in parts[1:]:
        try:
            obj = obj[part]
        except (KeyError, TypeError, IndexError) as e:
            raise PathResolutionError(
                f"trace {trace.id}: cannot resolve '{part}' in '{path}'"
            ) from e
    return obj
