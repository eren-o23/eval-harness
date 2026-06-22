# Handoff — eval-harness

_Last updated: 2026-06-22_

---

## Goal

Build a framework-agnostic LLM agent trace eval harness per `SPEC.md`: ingest
agent traces, run YAML-defined evaluators (`llm_judge`, `threshold`) against them,
store results in SQLite tagged by version, and detect regressions between versions.
CLI + local library only. First real consumer is Corpus (RFP extraction via
LangSmith). Follow the SPEC's non-goals strictly — no extra adapters, evaluator
types, or features beyond v1 scope.

Work proceeds one build-order step at a time; stop and show the user after each.

---

## Current State

Steps 1–3 are committed (`70be4dc` and earlier) and tested. Step 4 is built but
**not committed** and **not fully verified** (the real model call is still pending).

- **Step 1 (committed):** `Trace`/`Step` dataclasses (`models.py`), `from_jsonl`
  adapter, hand-written fixture `tests/fixtures/traces.jsonl` (4 Corpus-flavored
  traces). Verified via `test_jsonl_adapter.py`.
- **Step 2 (LangSmith adapter): SKIPPED by user** — deferred to v2. Do not build
  it unless the user asks. The `Adapter` Protocol stub in `adapters/__init__.py`
  is documentation only.
- **Step 3 (committed):** `config.load_config`, `dotpath.resolve_path`,
  `ThresholdEvaluator`, `LLMJudgeEvaluator`, provider dispatch in `llm.py`,
  `examples/evals.yaml`. Verified via `test_threshold.py` + `test_llm_judge.py`.
- **Step 4 (uncommitted):** `storage.py` (SQLite), `runner.py`
  (`run_evaluations` + `format_summary`), `cli.py` (`run` subcommand + `.env`
  loader), `__main__.py`, plus `[project.scripts]` and deps in `pyproject.toml`.
  - **36 tests pass on Python 3.9** (`PYTHONPATH=src python3 -m pytest -q`).
  - **Threshold-only end-to-end CLI verified** (no API key): ran the `run`
    command against the fixture with a temp threshold-only config; 8 results
    stored in SQLite, summary table correct, trace-004 fails latency (8830 > 4000).
  - **NOT yet run:** the real `llm_judge` call against `examples/evals.yaml`
    (`anthropic/claude-sonnet-4-6`). Blocked on `ANTHROPIC_API_KEY` in `.env`.

---

## Key Invariants

- **Python runtime:** the user's `python3` is **3.9.6** with old pip 21. Run
  everything as `PYTHONPATH=src python3 -m pytest` / `python3 -m eval_harness …`.
  Do **not** `pip install -e .` on this interpreter (see failure table). Deps
  installed via `pip install --user`: `PyYAML` 6.0.3, `anthropic` 0.111.0.
- **`requires-python >=3.9`:** every module starts with `from __future__ import
  annotations`, so `X | None` *annotations* are deferred strings and run on 3.9.
  But any **runtime** `X | Y` union (not in an annotation) is a `TypeError` on
  3.9 — use `typing.Union` (see `config.py:Evaluator`).
- **`llm_judge` model format:** must be `provider/model-name` (e.g.
  `anthropic/claude-sonnet-4-6`). This is a deliberate user instruction that
  **overrides** SPEC.md's bare-`claude-sonnet-4-6` example. Bare strings fail
  config validation. Provider prefix selects the client: `anthropic` → Anthropic
  SDK; anything else → OpenAI-compatible (`<PROVIDER>_BASE_URL`/`_API_KEY` env).
- **Target validation is "resolves against ≥1 trace," not all traces.** The
  fixture is heterogeneous: trace-003 has `output.matches`, not
  `output.extracted_fields`. Validating against every trace would falsely reject
  the example config. Per-trace absence is a runtime skip, not a config error.
- **Runner skips before model calls:** `run_evaluations` catches
  `PathResolutionError` and skips that (evaluator, trace) pair *before* any API
  call — so trace-003 never triggers a judge call.
- **`llm_judge` mock seam = dependency injection** (user's choice):
  `evaluate(trace, complete=fn)`. Default `complete` is the real `get_completion`.
  Tests pass a fake; the CLI/real run uses the default.
- **Storage:** `passed` stored as `1/0/NULL` (NULL = no pass/fail cutoff, e.g.
  llm_judge without a threshold). One `created_at` timestamp per run. The `--version`
  CLI tag is the storage `version_tag`; it is distinct from each trace's
  `metadata.version_tag` (the latter matters for regression diff in step 5).
- **Secrets/data hygiene:** `.env`, `.env.*`, `*.local.jsonl`, `traces/`, `data/`,
  `*.sqlite` are gitignored. Never commit `.env`, the API key, or raw trace data.
- **Repo reality:** despite the session-start "not a git repo" flag, the repo
  **does** exist with remote `origin` = `git@github-personal:eren-o23/eval-harness.git`
  and prior history. Commits land on `main` (the established pattern); nothing has
  been pushed by this work.

---

## What We Tried That Failed

| Approach | Why it failed |
|----------|--------------|
| `pip install -e .` on system Python 3.9 (pip 21 + hatchling) | "editable mode currently requires a setuptools-based build" — old pip can't do PEP 660 editable with hatchling. Use `PYTHONPATH=src` instead. |
| Runtime `Evaluator = LLMJudgeEvaluator \| ThresholdEvaluator` in `config.py` | `TypeError: unsupported operand type(s) for \|` on 3.9 (it's a runtime expression, not a deferred annotation). Fixed with `typing.Union`. |
| Running the `Anaconda` 3.12 interpreter for verification | Works, but the user explicitly wants verification on their real 3.9.6, since that's their environment. Use 3.9. |

---

## Don't Touch

- `/tmp/threshold_only.yaml` and `/tmp/eval_demo.sqlite` are throwaway artifacts
  from the threshold-only smoke test — ignore/delete freely, not part of the repo.
- The `Adapter` Protocol in `adapters/__init__.py` is intentionally a doc-only
  stub (LangSmith adapter is deferred). Don't flesh it out.

---

## Next Step

User adds `ANTHROPIC_API_KEY` to `/Users/erenosman/eval-harness/.env`. Then:
1. Re-confirm `git check-ignore .env` passes (must print `.env`).
2. Run the real end-to-end:
   `PYTHONPATH=src python3 -m eval_harness run --traces tests/fixtures/traces.jsonl --config examples/evals.yaml --version v1.2.0`
   — 3 real `claude-sonnet-4-6` judge calls (trace-001/002/004; 003 skipped) + the
   latency threshold, stored under `v1.2.0`, with a real avg score in the summary.
3. Show the user the output. Once they confirm step 4 is done, commit step 4 to
   `main` (currently uncommitted).

---

## Open Questions / Blockers

- **Blocker:** `.env` with `ANTHROPIC_API_KEY` not yet present — required for the
  real `llm_judge` run that gates step-4 sign-off.
- Commit step 4 before or after the real run? (Plan: after the user confirms the
  real output looks right.)
- Example config pins `anthropic/claude-sonnet-4-6` to match SPEC's RFP example.
  Current Anthropic default would be `claude-opus-4-8`; kept sonnet per SPEC. One
  line to change if the user prefers.

---

## Session History

_Append-only. One line per session — never overwrite previous entries._

- 2026-06-17: Step 1 (schema + jsonl adapter + fixture) and step 3 (config loader
  + threshold/llm_judge evaluators) built and committed; lowered requires-python
  to 3.9 verified on real 3.9.6. Step 2 (LangSmith) skipped per user.
- 2026-06-22: Step 4 built — SQLite storage, runner, `run` CLI; 36 tests pass on
  3.9; threshold-only end-to-end CLI verified. Real `llm_judge` run still pending
  on `.env`/API key. Step 4 uncommitted.
