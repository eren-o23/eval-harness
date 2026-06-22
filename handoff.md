# Handoff — eval-harness

_Last updated: 2026-06-22_

---

## Goal

Build a framework-agnostic LLM agent trace eval harness per `SPEC.md`: ingest
agent traces, run YAML-defined evaluators (`llm_judge`, `threshold`,
`trajectory`) against them, store results in SQLite tagged by version, and
detect regressions between versions. CLI + local library only. First real
consumer is Corpus (RFP extraction via LangSmith). Follow the SPEC's non-goals
strictly — no extra adapters, evaluator types, or features beyond v1 scope.

---

## Current State

**All 8 build-order steps are complete and committed.** The tool is
feature-complete per the v1 spec.

| Step | Status | Commit |
|------|--------|--------|
| 1. Trace/Step schema + from_jsonl + fixture | committed | `135cf7a` |
| 2. LangSmith adapter | **SKIPPED by user** — deferred to v2 | — |
| 3. YAML config loader + llm_judge + threshold | committed | `70be4dc` |
| 4. SQLite storage + run command | committed | `1796d18` |
| 5. diff command | committed | `da5cc72` |
| 6. report command | committed | `08f4616` |
| 7. trajectory evaluator (stretch) | committed | `9275504` |
| 8. README | committed | latest |

**Verified end-to-end** (real `claude-sonnet-4-6` judge calls):
- `v1.2.0` run: 3 RFP extractions scored 5/5, trace-004 fails latency (8830 ms)
- `v1.2.1` run: same fixture, identical results (clean diff)
- `v1.3.0` run: includes trajectory evaluator (0/4 pass — fixture lacks `grant_search`/`loi_draft` steps, as expected)

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
  `anthropic/claude-sonnet-4-6`). Bare strings fail config validation. Provider
  prefix selects the client: `anthropic` → Anthropic SDK; anything else →
  OpenAI-compatible (`<PROVIDER>_BASE_URL`/`_API_KEY` env).
- **`llm_judge` prompt includes `trace.input`:** the judge prompt sends both
  the source input and the resolved target so rubrics like "compare against
  source RFP" work correctly. This was added in step 4 after the first real run
  failed — the model correctly refused to score without the source.
- **Target validation is "resolves against ≥1 trace," not all traces.** The
  fixture is heterogeneous: trace-003 has `output.matches`, not
  `output.extracted_fields`. Validating against every trace would falsely reject
  the example config.
- **`trajectory` has no `target`:** it operates on `trace.steps` directly, so
  it's skipped in `_validate_targets` and not subject to the dot-path check.
  It runs against every trace (nothing to skip per-trace).
- **`llm_judge` mock seam = dependency injection:**
  `evaluate(trace, complete=fn)`. Default `complete` is the real `get_completion`.
  Tests pass a fake; the CLI/real run uses the default.
- **Storage:** `passed` stored as `1/0/NULL` (NULL = no pass/fail cutoff, e.g.
  llm_judge without a threshold). Skips are NOT stored — only actual results are.
  The `report` command shows `n/a` (not `skipped`) for NULL-passed results.
- **Secrets/data hygiene:** `.env`, `.env.*`, `*.local.jsonl`, `traces/`, `data/`,
  `*.sqlite` are gitignored. Never commit `.env`, the API key, or raw trace data.
- **Repo:** remote `origin` = `git@github-personal:eren-o23/eval-harness.git`.
  All commits on `main`. Nothing has been pushed yet.

---

## What We Tried That Failed

| Approach | Why it failed |
|----------|--------------|
| `pip install -e .` on system Python 3.9 (pip 21 + hatchling) | "editable mode currently requires a setuptools-based build" — old pip can't do PEP 660 editable with hatchling. Use `PYTHONPATH=src` instead. |
| Runtime `Evaluator = LLMJudgeEvaluator \| ThresholdEvaluator` in `config.py` | `TypeError: unsupported operand type(s) for \|` on 3.9 (it's a runtime expression, not a deferred annotation). Fixed with `typing.Union`. |
| Sending only `target` to llm_judge (no source input) | Model correctly refused to score "does it match the source RFP?" with no source RFP. Fixed by including `trace.input` in the judge prompt. |

---

## What's Left

- **LangSmith adapter (step 2):** deferred to v2. Do not build unless the user
  asks. The `Adapter` Protocol stub in `adapters/__init__.py` is documentation only.
- **Corpus real-world run:** the user has not yet pointed the tool at real
  Corpus/LangSmith traces. When they do, they'll likely need the LangSmith
  adapter (step 2) — or export Corpus traces to `.jsonl` first.
- **Push to remote:** nothing has been pushed to `git@github-personal:eren-o23/eval-harness.git`.

---

## Session History

_Append-only. One line per session — never overwrite previous entries._

- 2026-06-17: Step 1 (schema + jsonl adapter + fixture) and step 3 (config loader
  + threshold/llm_judge evaluators) built and committed; lowered requires-python
  to 3.9 verified on real 3.9.6. Step 2 (LangSmith) skipped per user.
- 2026-06-22: Steps 4–8 built and committed. Full end-to-end verified with real
  Anthropic API calls (claude-sonnet-4-6). 41 tests pass on Python 3.9. Tool is
  v1 feature-complete. Corpus real-world run still pending.
