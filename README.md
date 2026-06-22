# eval-harness

A framework-agnostic CLI tool for evaluating LLM agent traces. Ingest traces
from any source, run YAML-defined evaluators against them, store results
locally, and detect regressions between versions — no server, no account
required.

---

## What it does

- **Ingests** agent traces from a `.jsonl` file (or any source via the adapter
  interface). Normalises everything into a common `Trace`/`Step` schema.
- **Evaluates** each trace using evaluators defined in a YAML config:
  `llm_judge` (model-scored, 1–5), `threshold` (numeric comparison), or
  `trajectory` (step-name subsequence check).
- **Stores** results in a local SQLite database, tagged with a version string.
- **Diffs** two stored runs — per-evaluator score deltas, pass-rate changes,
  and the specific trace IDs responsible for the largest drops.
- **Reports** a standalone markdown or JSON report for any stored run.

---

## Installation

**Dependencies:** Python ≥ 3.9, `PyYAML`, `anthropic` SDK (for `llm_judge`
with Anthropic models). The `openai` package is only needed for
OpenAI-compatible providers.

```bash
# Install directly (no editable install needed)
pip install PyYAML anthropic

# Clone and run via PYTHONPATH
git clone https://github.com/eren-o23/eval-harness
cd eval-harness
PYTHONPATH=src python3 -m eval_harness run --help
```

**API keys** — copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
# edit .env: set ANTHROPIC_API_KEY=sk-ant-...
```

The `.env` file is loaded automatically by the `run` command and is
gitignored. Never commit real keys.

---

## Data model

Every source adapter normalises its format into this shape. Evaluators and
storage only ever see `Trace` — never the original format.

```python
@dataclass
class Step:
    name: str          # e.g. "rfp_extraction", "tool:search_grants"
    type: str          # "llm_call" | "tool_call" | "retrieval" | "other"
    input: dict
    output: dict
    latency_ms: float | None
    metadata: dict     # model name, token counts, etc.

@dataclass
class Trace:
    id: str            # stable ID from source system, or generated
    input: dict        # top-level input to the agent/chain
    output: dict       # final output
    steps: list[Step]  # ordered sequence of steps taken
    metadata: dict     # version_tag, timestamp, total_latency_ms, source, ...
```

**Rules:**
- `version_tag` in `metadata` is required for regression detection. Missing →
  diff fails loudly.
- Adapters may not add required fields to `Trace`/`Step`. Anything
  source-specific goes in `metadata`.
- `steps` order is authoritative for `trajectory` evaluators.

---

## Evaluator config (YAML)

```yaml
# examples/evals.yaml
evaluators:
  - name: rfp_extraction_accuracy
    type: llm_judge
    target: output.extracted_fields      # dot-path into Trace
    rubric: |
      Score 1-5: does the extracted JSON correctly capture the funding amount,
      application deadline, and eligibility criteria from the source RFP?
    model: anthropic/claude-sonnet-4-6   # provider/model-name
    threshold: 4                         # optional pass/fail cutoff (score >= 4)

  - name: extraction_latency
    type: threshold
    target: metadata.total_latency_ms
    max: 4000                            # fail if value exceeds this

  - name: tool_call_order
    type: trajectory
    expected_sequence: ["rfp_extraction", "grant_search", "loi_draft"]
```

### Evaluator types

**`llm_judge`** — sends the trace's input and the resolved `target` to the
specified model along with the `rubric`. Expects a 1–5 integer score back
(parsed from a constrained JSON response). Stores score + judge reasoning per
trace. `model` must be `provider/model-name`; currently supports `anthropic/*`
and any OpenAI-compatible endpoint via `<PROVIDER>_BASE_URL`.

**`threshold`** — pure comparison of `target` against `max`, `min`, or
`equals`. No model call. Deterministic pass/fail.

**`trajectory`** — checks whether `expected_sequence` appears as a
*subsequence* of the trace's `step.name` values in order. Gaps are allowed;
all expected steps must be present and in sequence. No model call.

Config validation runs at load time — the run fails before any model call if a
`target` path doesn't resolve against any loaded trace or an evaluator type is
unrecognised.

---

## CLI

### `run` — evaluate traces and store results

```
eval-harness run --traces <path.jsonl> --config <evals.yaml> --version <tag>
                 [--db <path>]
```

Runs all evaluators in `evals.yaml` against the loaded traces and stores
results in SQLite under `<tag>`. The `--db` default is `eval_results.sqlite`
in the working directory.

**Example — Corpus RFP extraction, v1.2.0:**

```
$ PYTHONPATH=src python3 -m eval_harness run \
    --traces tests/fixtures/traces.jsonl \
    --config examples/evals.yaml \
    --version v1.2.0

Ran 2 evaluator(s) over 4 trace(s) → 7 result(s) stored under version 'v1.2.0'
Skipped 1 (trace missing the evaluator's target field)

evaluator                type       passed  failed  n/a  avg_score  skipped
-----------------------  ---------  ------  ------  ---  ---------  -------
rfp_extraction_accuracy  llm_judge  3       0       0    5.00       1
extraction_latency       threshold  3       1       0    -          0
```

The `rfp_judge` scored every RFP extraction trace 5/5. `trace-004` failed the
4000 ms latency threshold (8830 ms actual). `trace-003` was skipped for the
judge evaluator because its output has `matches`, not `extracted_fields`.

---

### `diff` — compare two runs and flag regressions

```
eval-harness diff <version-a> <version-b> [--db <path>]
```

Compares two stored runs per evaluator: score delta, pass-rate delta,
regression count. Below the table, lists regressed trace IDs with before/after
scores. Traces present in only one version are listed as added/removed.

**Example — catching a regression between pipeline versions:**

```
$ eval-harness diff v1.2.0 v1.3.0

Diff v1.2.0 -> v1.3.0

evaluator                score_delta  pass_rate_delta  regressions
-----------------------  -----------  ---------------  -----------
rfp_extraction_accuracy  -1.33        -67%             2
extraction_latency       -            +0%              0

Regressions:
  rfp_extraction_accuracy / trace-002: score 5 -> 2 (pass -> fail)
  rfp_extraction_accuracy / trace-001: score 5 -> 3 (pass -> fail)

Added/removed traces:
  (none)
```

A regression is any trace where the score dropped or pass/fail flipped from
pass to fail. Trace IDs are sorted by magnitude of score drop, so the worst
regressions appear first. If a version tag isn't in the database, the command
fails immediately with a clear error.

---

### `report` — standalone report for one run

```
eval-harness report --version <tag> [--format md|json] [--db <path>]
```

Renders a full report to stdout. Default format is markdown; pipe to a file
or use `--format json` for structured output.

**Markdown output:**

```markdown
# Eval Report — v1.2.0

## Summary

| evaluator               | passed | failed | n/a | avg_score |
| ---                     | ---    | ---    | --- | ---       |
| rfp_extraction_accuracy | 3      | 0      | 0   | 5.00      |
| extraction_latency      | 3      | 1      | 0   | -         |

## Per-trace results

### trace-001
- **rfp_extraction_accuracy**: PASS — score 5
  - reasoning: The extracted JSON correctly captures all three key fields:
    the funding amount of $500,000, the deadline of 2026-09-30, and the
    eligibility criteria (US-based nonprofits and municipalities), with only
    minor and acceptable paraphrasing of 'US-based nonprofits' to
    'US nonprofits'.
- **extraction_latency**: PASS

### trace-004
- **rfp_extraction_accuracy**: PASS — score 5
  - reasoning: The extracted JSON correctly captures all three key fields:
    the funding amount ($2,000,000), the deadline (2026-08-15, correctly
    interpreted from the letters of intent due date), and the eligibility
    criteria (state and tribal governments, properly split into distinct
    list items).
- **extraction_latency**: FAIL
```

**JSON output** (`--format json`) returns the same data structured for piping:

```json
{
  "version": "v1.2.0",
  "summary": [
    {
      "evaluator": "rfp_extraction_accuracy",
      "passed": 3, "failed": 0, "n_a": 0, "avg_score": 5.0
    },
    {
      "evaluator": "extraction_latency",
      "passed": 3, "failed": 1, "n_a": 0, "avg_score": null
    }
  ],
  "results": [ ... ]
}
```

---

## Trace format (JSONL adapter)

The reference adapter reads `.jsonl` files — one JSON object per line, each
matching the `Trace` shape. This is the fallback for any source not using
LangSmith and the format used for tests.

```jsonl
{"id": "trace-001", "input": {"rfp_url": "...", "rfp_text": "..."}, "output": {"extracted_fields": {"funding_amount": "$500,000", "deadline": "2026-09-30", "eligibility": ["US nonprofits", "municipalities"]}}, "steps": [{"name": "retrieval:rfp_fetch", "type": "retrieval", "input": {}, "output": {}, "latency_ms": 430.5, "metadata": {}}, {"name": "rfp_extraction", "type": "llm_call", "input": {}, "output": {}, "latency_ms": 2100.0, "metadata": {"model": "claude-sonnet-4-6"}}], "metadata": {"version_tag": "v1.2.0", "total_latency_ms": 2530.5, "source": "jsonl"}}
```

---

## Running the tests

```bash
PYTHONPATH=src python3 -m pytest -q
# 41 passed
```

No API calls in the test suite — `llm_judge` tests inject a fake `complete`
function via dependency injection. All tests run on Python 3.9+.

---

## Non-goals (v1)

- No hosted/SaaS version. CLI and local library only.
- No tracing/instrumentation. This tool consumes traces, it does not produce
  them.
- No UI or dashboard. Terminal output and generated markdown/JSON reports only.
- No LangSmith adapter in v1 (deferred; the `Adapter` protocol stub is a
  documented extension point).
- No real-time or streaming evaluation. Batch only.
