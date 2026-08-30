# AIP Evaluation Suite

Deterministic evaluation kernel for AIP, implementing Iteration 1 (`v0.2.0-alpha.1`) of
[`docs/specifications/0.2.0/i1-evaluation-kernel.md`](../docs/specifications/0.2.0/i1-evaluation-kernel.md).

> **v0.2.0's goal is not to add a new architecture-intelligence dimension.** AIP `v0.1` already
> produces declared/observed architecture facts, statuses (`CONFIRMED`/`OBSERVED_ONLY`/
> `NOT_OBSERVED_IN_WINDOW`), and evidence. This suite exists to prove, reproducibly, that those
> facts are actually correct against independently authored ground truth - it never adds a new kind
> of architecture fact itself.

## What this suite tests

Given a known declared/observed architecture situation, the suite runs it through real AIP
ingestion and runtime resolution, projects the resulting canonical facts, and compares them
against a hand-written `expected.yaml`:

```text
scenario fixture -> AIP -> canonical architecture facts -> compare -> PASS/FAIL
```

Iteration 1 exercises exactly three scenarios, covering:

- declared architecture input (OpenAPI, AsyncAPI, Architecture Manifest),
- runtime observation input (real OTLP ingestion via `/v1/traces`),
- REST dependencies (`CALLS`/`PROVIDES`) and queue-based dependencies (`SENDS`/`RECEIVES_FROM`),
- the `CONFIRMED` and `OBSERVED_ONLY` status classifications,
- declared vs. observed evidence presence,
- canonical identifiers and deterministic comparison.

## What this suite does not (yet) test

I1 is deliberately narrow. It does **not** implement:

- the complete 8-10 scenario `v0.2.0` suite (`docs/specifications/0.2.0/specification.md`),
- `NOT_OBSERVED_IN_WINDOW`,
- evidence reconciliation or partial-observation semantics,
- request/response queue pairs, orphan queues, or DLQ scenarios,
- **non-empty `forbidden` assertions** - every I1 scenario's `forbidden.relations` must be
  present and empty; a non-empty list is rejected as unsupported configuration, not evaluated,
- **exhaustive unexpected-fact detection** - an in-scope canonical fact that isn't in
  `expected.relations` is counted for diagnostics (reported as "not enforced in I1") but never
  fails a scenario on its own,
- an LLM-based evaluator, a generic policy/rules engine, or precision/recall scoring.

Full `forbidden`/unexpected-fact semantics, strict relation-direction checks, orphan messaging, and
mixed REST+async scenarios are the focus of Iteration 2.

## Running

Requires Docker (the runner starts its own ephemeral Neo4j via Testcontainers, the same mechanism
this project's `tests/integration/` suite already uses - no separately running Neo4j needed):

```bash
uv run python -m evaluation run                              # all scenarios
uv run python -m evaluation run 01-rest-confirmed             # one scenario, by directory name
uv run python -m evaluation run --scenario 01-rest-confirmed  # equivalent
```

Expected result on a clean checkout:

```text
AIP Evaluation — I1

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed

Scenarios:          3
Passed:             3
Failed:             0
...
RESULT: PASS
```

Exit code `0` means every scenario passed; `1` means at least one semantic evaluation failure;
`2` means invalid scenario configuration or an infrastructure error (the suite never exits `0` on
failure).

## Scenario structure

Each scenario is a self-contained directory under `evaluation/scenarios/`:

```text
evaluation/scenarios/01-rest-confirmed/
├── expected.yaml                          # declarative ground truth (see below)
└── input/
    ├── declarations/                      # OpenAPI/AsyncAPI/Architecture Manifest fixtures,
    │   ├── order-service/...              # laid out exactly like a real project root - one
    │   └── product-service/...            # subdirectory per service, ingested unmodified through
    │                                       # app.graph.importer.import_all_sources
    └── telemetry/
        └── spans.py                       # build_export_request() -> bytes: a real OTLP
                                            # ExportTraceServiceRequest protobuf, injected through
                                            # the real POST /v1/traces path (decode -> resolve ->
                                            # persist) - no shortcut around OTLP ingestion
```

The three I1 scenarios:

| Directory | Purpose |
| --- | --- |
| `01-rest-confirmed` | OrderService calls ProductService's `GET /products/{id}`; both declared and observed -> `CONFIRMED`. |
| `02-rest-observed-only` | OrderService calls ProductService's `GET /prices` at runtime with no declared caller evidence anywhere -> `OBSERVED_ONLY`. |
| `03-async-confirmed` | OrderService sends to, and InventoryService receives from, `order-events-q`; both directions declared and observed -> `CONFIRMED`. |

Each scenario runs from a fully reset graph (`MATCH (n) DETACH DELETE n`) before its own
declarations and telemetry are ingested, so scenarios never interfere with each other.

## How `expected.yaml` is interpreted

```yaml
scenario: rest-confirmed          # stable scenario identifier (independent of the directory name)
description: >
  Human-readable purpose of the scenario.

scope:
  entities:                       # canonical entity ids this scenario owns
    - service:order-service
    - service:product-service
    - operation:service:product-service:GET:/products/{id}
  relation_types: [CALLS]         # optional - restricts comparison to these relation types

observation:
  environment: test               # required whenever the scenario has input/telemetry/
  window:
    start: "2026-08-01T10:00:00Z"
    end: "2026-08-01T11:00:00Z"

expected:
  relations:                      # canonical facts that MUST exist, matched exactly
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/products/{id}
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

forbidden:
  relations: []                   # MUST be present and empty in I1 (see above)
```

A canonical relation is "in scope" when its source or target is listed under `scope.entities`
(and, if given, its type is in `scope.relation_types`). Only in-scope facts are compared - this
lets scenarios share infrastructure (e.g. multiple scenarios both mentioning ProductService)
without becoming brittle against unrelated facts.

## Ground truth is independent of AIP

`expected.yaml` is hand-authored, not generated from AIP's own derivation code. In particular, the
evaluator never computes a scenario's expected `CONFIRMED`/`OBSERVED_ONLY` status from evidence
booleans itself (that would just duplicate the behavior under test) - it reads the status AIP
already produced (via `app.analysis.runtime`, the same code backing the real
`/api/analysis/runtime/*` endpoints) and compares it against the independently declared expectation.

## Suite internals (for contributors)

```text
loader.py      discovers scenarios and validates expected.yaml (spec §7)
runner.py      resets state, ingests declarations, injects OTLP fixtures, orchestrates a run
projector.py   reads raw canonical relation edges from Neo4j, labels them by AIP's own
               CONFIRMED/OBSERVED_ONLY classification (never re-derives it)
comparator.py  expectation-driven exact comparison against expected.yaml
reporter.py    renders the human-readable PASS/FAIL report
```

See the I1 specification for the full design rationale, including why status must be read from AIP
rather than recomputed, and why canonical identity (not Cypher row shape) is the comparison
contract.
