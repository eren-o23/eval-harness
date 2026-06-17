# Agent Trace Eval Harness — v1 Spec

## What this is

A framework-agnostic CLI tool that ingests AI agent traces from any source, runs
configurable evaluations against them (YAML-defined, no code required per eval),
and detects regressions between versions. Self-hosted, no server, no account.

First real consumer: Corpus (grant intelligence pipeline), traced via LangSmith.

## Why it exists

Existing tools (LangSmith, Langfuse, Confident AI) either lock evals to their own
tracing format, or split observability and evaluation into separate concerns with
evaluation as an afterthought. This tool is evaluation-first: a thin normalization
layer plus a focused eval and regression engine, usable with whatever tracing
backend you already have.

## Non-goals (v1)

These are explicitly out of scope. Do not build them even if they seem like a
natural extension — they dilute a narrow, finished tool into a half-built broad one.

- No hosted/SaaS version. CLI and local library only.
- No tracing/instrumentation. This tool consumes traces, it does not produce them.
- No UI/dashboard. Terminal output and a generated markdown/JSON report only.
- No support for OpenTelemetry, CrewAI, AutoGen, or any adapter beyond LangSmith
  and JSONL in v1. Adapter interface should make these easy to add *later*, but
  they are not built now.
- No more than two evaluator types (`llm_judge`, `threshold`) in v1.
- No real-time/streaming evaluation. Batch only — point it at a set of traces,
  it runs, it finishes.
- No multi-user concerns (auth, permissions, sharing). Single local user.

## Core data model

Every adapter normalizes its source format into this shape. Nothing downstream
(evaluators, regression detection, reporting) touches the original format —
only `Trace`.

```python
@dataclass
class Step:
    name: str                  # e.g. "rfp_extraction", "tool:search_grants"
    type: str                  # "llm_call" | "tool_call" | "retrieval" | "other"
    input: dict
    output: dict
    latency_ms: float | None
    metadata: dict             # model name, token counts, etc. — adapter-specific
                                # fields allowed here, NOT in core schema

@dataclass
class Trace:
    id: str                    # stable ID from source system, or generated
    input: dict                # the original top-level input to the agent/chain
    output: dict                # the final output
    steps: list[Step]          # ordered sequence of steps taken
    metadata: dict              # version_tag, timestamp, total_latency_ms,
                                # total_cost_usd, source ("langsmith" | "jsonl")
```

Rules:
- `version_tag` in `metadata` is required for any trace used in regression detection.
  If missing, regression diff should fail loudly, not silently skip the trace.
- Adapters may NOT add required fields to `Trace` or `Step`. Anything source-specific
  goes in `metadata`. This is what keeps evaluators format-agnostic.
- `steps` order matters — it's the basis for trajectory evaluation.

## Adapters (v1: two only)

### `from_jsonl(path: str) -> list[Trace]`
Reads a `.jsonl` file, one JSON object per line, each matching the `Trace` shape
(or close enough to map directly). This is the reference/test adapter — simplest
possible, and a fallback for anyone not using LangSmith.

### `from_langsmith(project_name: str, ...) -> list[Trace]`
Pulls runs from the LangSmith API for a given project, maps LangSmith's run tree
into `Trace`/`Step`. This is the one validated against real data (Corpus).

Adapter interface (for future extensibility, not built now):
```python
class Adapter(Protocol):
    def load(self, source: str, **kwargs) -> list[Trace]: ...
```

## Evaluator config (YAML)

```yaml
evaluators:
  - name: rfp_extraction_accuracy
    type: llm_judge
    target: output.extracted_fields      # dot-path into Trace
    rubric: |
      Score 1-5: does the extracted JSON match the source RFP's
      eligibility criteria, deadline, and funding amount exactly?
    model: claude-sonnet-4-6
    threshold: 4                          # optional pass/fail cutoff for reporting

  - name: extraction_latency
    type: threshold
    target: metadata.total_latency_ms
    max: 4000                             # fail if value exceeds this
```

Two evaluator types only:

**`llm_judge`** — sends `target` plus `rubric` to the specified model, expects a
1-5 score back (parsed from a constrained response format, not free text).
Stores score + raw judge reasoning per trace.

**`threshold`** — pure comparison against `target` (`max`, `min`, or `equals`).
No model call. Deterministic pass/fail.

Config validation should happen at load time — fail before running anything if
a `target` path doesn't resolve or an evaluator type is unrecognized.

## CLI

```
eval-harness run --traces <path-or-project> --config evals.yaml --version <tag>
```
Runs all evaluators in `evals.yaml` against the loaded traces, stores results
locally (SQLite), tagged with `<tag>`.

```
eval-harness diff <version-a> <version-b>
```
Compares two stored runs. Output: per-evaluator score deltas, flagged regressions,
and the specific trace IDs responsible for the largest drops — not just an
aggregate number.

```
eval-harness report --version <tag> [--format md|json]
```
Generates a standalone report for a single run.

No other subcommands in v1.

## Trajectory evaluation (stretch goal within v1, not a separate phase)

A third evaluator type, only if time allows after the above is solid:

```yaml
  - name: tool_call_order
    type: trajectory
    expected_sequence: ["search_grants", "extract_fields", "draft_loi"]
```
Checks whether `expected_sequence` appears as a subsequence of the actual
`step.name` values in order. Simple containment check, not fuzzy matching.

If this slips past v1, that's fine — it's explicitly the first thing to cut.

## Build order

1. `Trace`/`Step` schema + `from_jsonl` adapter + a hand-written test fixture file.
   Nothing else can be verified without this.
2. `from_langsmith` adapter, run against real Corpus trace data.
3. YAML config loader + `llm_judge` + `threshold` evaluator execution.
4. SQLite storage + `run` command end-to-end.
5. `diff` command.
6. `report` command.
7. (Stretch) `trajectory` evaluator type.
8. README with a real before/after example from Corpus's RFP extraction —
   this is the launch artifact, not an afterthought.

## Definition of done for v1

- Can run `eval-harness run` against real Corpus LangSmith traces and get scored
  results for at least RFP extraction accuracy and one latency threshold.
- Can run `eval-harness diff` between two tagged versions and get a readable
  regression report pointing at specific failing trace IDs.
- `from_jsonl` works against a synthetic fixture with no LangSmith dependency,
  proving the format-agnostic claim is real and not just theoretical.
- README documents the schema, the YAML format, and the two CLI commands clearly
  enough that someone unfamiliar with Corpus could point it at their own traces.
