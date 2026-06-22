"""eval-harness CLI.

v1 subcommands per SPEC: `run` (this step), `diff`, `report` (later). No others.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from eval_harness import storage
from eval_harness.adapters import from_jsonl
from eval_harness.config import ConfigError, load_config
from eval_harness.runner import format_summary, run_evaluations


def _load_dotenv(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ (does not override
    values already set in the real environment)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="eval-harness")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="run evaluators against traces and store results")
    run_p.add_argument("--traces", required=True, help="path to a .jsonl traces file")
    run_p.add_argument("--config", required=True, help="path to an evals.yaml config")
    run_p.add_argument("--version", required=True, help="version tag to store results under")
    run_p.add_argument("--db", default="eval_results.sqlite", help="SQLite db path")

    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    return 1  # unreachable while 'run' is the only subcommand


def _cmd_run(args) -> int:
    _load_dotenv()
    traces = from_jsonl(args.traces)
    if not traces:
        print(f"no traces loaded from {args.traces}", file=sys.stderr)
        return 2
    try:
        evaluators = load_config(args.config, traces=traces)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    results, skipped = run_evaluations(traces, evaluators)

    conn = storage.connect(args.db)
    n = storage.save_results(conn, args.version, results)

    print(
        f"Ran {len(evaluators)} evaluator(s) over {len(traces)} trace(s) → "
        f"{n} result(s) stored under version '{args.version}' in {args.db}"
    )
    if skipped:
        print(f"Skipped {len(skipped)} (trace missing the evaluator's target field)")
    print()
    print(format_summary(evaluators, results, skipped))
    return 0
