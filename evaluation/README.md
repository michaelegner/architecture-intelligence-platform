# AIP Evaluation Suite

Deterministic evaluation kernel for AIP. Implements Iteration 1
([`i1-evaluation-kernel.md`](../docs/specifications/0.2.0/i1-evaluation-kernel.md), shipped as
`v0.2.0-alpha.1`), Iteration 2
([`i2-topology-directionality.md`](../docs/specifications/0.2.0/i2-topology-directionality.md),
`v0.2.0-alpha.2`), and Iteration 3
([`i3-evidence-runtime-semantics.md`](../docs/specifications/0.2.0/i3-evidence-runtime-semantics.md),
`v0.2.0-alpha.3`) of the `v0.2.0` release
([`specification.md`](../docs/specifications/0.2.0/specification.md)).

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

Eight scenarios currently exercise:

- declared architecture input (OpenAPI, AsyncAPI, Architecture Manifest),
- runtime observation input (real OTLP ingestion via `/v1/traces`),
- REST dependencies (`CALLS`/`PROVIDES`) and queue-based dependencies (`SENDS`/`RECEIVES_FROM`),
- the `CONFIRMED`, `OBSERVED_ONLY`, and `NOT_OBSERVED_IN_WINDOW` status classifications,
- declared vs. observed evidence presence,
- canonical identifiers and deterministic comparison,
- **(I2)** a forbidden canonical identity that must not exist (`forbidden.relations`) - failing the
  scenario if it's present,
- **(I2)** exhaustive unexpected-fact detection - any in-scope actual fact that is neither expected
  nor forbidden fails the scenario,
- **(I2)** topology that specifically exercises directionality: orphan messaging (a sender with no
  consumer, and vice versa), mixed REST+async between the same service pair (proving the two
  interaction modes aren't collapsed into one generic dependency), and a bidirectional
  request/response queue pair (proving sender/receiver roles aren't swapped),
- **(I3)** `NOT_OBSERVED_IN_WINDOW` - a declared relation with no matching OBSERVED evidence in the
  selected environment/window remains a real canonical fact, not an absence, and a
  window-sensitivity control proves the classification actually depends on the selected window,
- **(I3)** evidence reconciliation - removing a service's stale `DECLARED` evidence for a relation
  must not remove independently surviving `OBSERVED` evidence: the fact survives and its status
  transitions `CONFIRMED -> OBSERVED_ONLY`.

## What this suite does not (yet) test

The suite remains deliberately narrow. It does **not** implement:

- the complete 8-10 scenario `v0.2.0` suite (`docs/specifications/0.2.0/specification.md`),
- the partial-observation scenario, quantitative coverage qualification, DLQ directionality, or
  cross-batch HTTP correlation scenarios (all deferred to I4),
- a declared-only scenario with no runtime evidence at all (cheap to add later; not required by
  I1's, I2's, or I3's focus),
- a dedicated "wrong direction" report category distinct from missing/unexpected/forbidden -
  directionality is checked through the combination of those three, not a separate classifier,
- an LLM-based evaluator, a generic policy/rules engine, or precision/recall scoring.

I2 closed the two things I1 left unenforced: `forbidden.relations` is no longer rejected when
non-empty, and an unexpected in-scope fact is no longer just a diagnostic - both now fail a
scenario. See §3 of the I2 specification for the full rationale.

I3 closed the remaining status gap (`NOT_OBSERVED_IN_WINDOW`) and proved the evidence-preservation
invariant (`Delete(Fact) iff Evidence(Fact) is empty`) through a real declaration re-import, without
adding any new architecture-intelligence concept - see §4 of the I3 specification.

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
AIP Evaluation — I3

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair
[PASS] 07-not-observed-in-window
[PASS] 08-evidence-reconciliation

Scenarios:          8
Passed:             8
Failed:             0

Missing facts:      0
Unexpected facts:   0
Forbidden facts present: 0
Wrong statuses:     0
Evidence errors:    0

RESULT: PASS
```

Exit code `0` means every scenario passed; `1` means at least one semantic evaluation failure;
`2` means invalid scenario configuration or an infrastructure error (the suite never exits `0` on
failure).

### Failure examples

A missing expected fact or a wrong status/evidence value looks like this (see the I1
specification's own report format for the full rationale):

```text
[FAIL] 02-rest-observed-only

Expected:
  CALLS
  service:order-service
    -> operation:service:product-service:GET:/prices
  status: OBSERVED_ONLY
  evidence: declared=false observed=true

Actual:
  status: CONFIRMED
  evidence: declared=true observed=true

Reason:
  wrong status
  unexpected declared evidence
```

A **forbidden fact present** (I2) - a canonical identity listed in `forbidden.relations` is
present in the actual results:

```text
[FAIL] 06-request-response-queue-pair

Forbidden:
  RECEIVES_FROM
  service:order-service
    -> queue:request-q

Actual:
  status: CONFIRMED
  evidence: declared=true observed=true

Reason:
  forbidden fact present
```

An **unexpected fact** (I2) - an in-scope actual fact that is neither expected nor forbidden (it
has no expected counterpart to display, unlike the two cases above):

```text
[FAIL] 05-mixed-rest-async

Unexpected:
  SENDS
  service:order-service
    -> queue:some-other-queue
  status: CONFIRMED
  evidence: declared=true observed=true

Reason:
  unexpected in-scope fact
```

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

The eight scenarios:

| Directory | Purpose |
| --- | --- |
| `01-rest-confirmed` | OrderService calls ProductService's `GET /products/{id}`; both declared and observed -> `CONFIRMED`. |
| `02-rest-observed-only` | OrderService calls ProductService's `GET /prices` at runtime with no declared caller evidence anywhere -> `OBSERVED_ONLY`. |
| `03-async-confirmed` | OrderService sends to, and InventoryService receives from, `order-events-q`; both directions declared and observed -> `CONFIRMED`. |
| `04-orphan-messaging` | OrderService sends `unused-q` (no consumer); InventoryService receives from `unknown-producer-q` (no producer) - both `CONFIRMED`, with each queue's plausible wrong-guess inverse explicitly forbidden. |
| `05-mixed-rest-async` | OrderService/ProductService use both `CALLS` and `SENDS`/`RECEIVES_FROM` - proving the two interaction modes stay distinct canonical relation types. |
| `06-request-response-queue-pair` | OrderService/ProductService exchange a bidirectional queue pair; each participant's swapped role on the queue it already has a role on is explicitly forbidden. |
| `07-not-observed-in-window` | OrderService declares a call to ProductService's `GET /products/{id}`; a matching runtime observation exists, but outside the scenario's selected window -> `NOT_OBSERVED_IN_WINDOW`, not absence. |
| `08-evidence-reconciliation` | OrderService's call to ProductService is initially declared and observed (`CONFIRMED`); OrderService's declaration is then re-imported without that `CALLS` relation - the stale `DECLARED` evidence disappears, the `OBSERVED` evidence survives, the fact remains, and its status becomes `OBSERVED_ONLY`. |

Each scenario runs from a fully reset graph (`MATCH (n) DETACH DELETE n`) before its own
declarations and telemetry are ingested, so scenarios never interfere with each other.

### The optional reconciliation input phase (I3)

A scenario that needs to prove evidence survives a declaration change - like
`08-evidence-reconciliation` - may add one more input directory:

```text
evaluation/scenarios/08-evidence-reconciliation/
└── input/
    ├── declarations/                      # initial declared architecture
    ├── telemetry/                         # runtime observations after that declaration
    └── reconciliation/
        └── declarations/                  # declaration state re-imported after telemetry -
            └── order-service/...          # a full current-state re-declaration for each service
                                            # it contains, not a diff (AIP's own import is a
                                            # per-service full reimport, spec §9)
```

When `input/reconciliation/declarations/` is present, the runner ingests it - through the same real
`app.graph.importer.import_all_sources` path used for the initial declarations, never an
evaluation-only Cypher mutation - after the telemetry fixture and before projection:

```text
reset -> ingest declarations -> inject telemetry -> re-import reconciliation declarations -> project -> compare
```

This is what lets AIP's own per-service reconciliation (`app.graph.importer.import_service`) expire
a service's stale `DECLARED` evidence for a relation it no longer declares, while any surviving
`OBSERVED` evidence - and any other service's declarations - are left untouched. An
existing-but-empty `input/reconciliation/declarations/` directory is rejected at load time as an
invalid fixture, not silently treated as "no reconciliation phase."

There is no reset between the initial and reconciliation phases - resetting would destroy the very
evidence whose survival is under test. A scenario with no `input/reconciliation/` directory is
completely unaffected (all seven other scenarios).

### `NOT_OBSERVED_IN_WINDOW` is context-qualified (I3)

`NOT_OBSERVED_IN_WINDOW` means exactly: *the relation has declared support, but AIP found no
matching observed evidence in the selected environment and observation window.* It does **not**
mean unused, obsolete, dead, unreachable, or forbidden - the relation remains an expected canonical
fact. `07-not-observed-in-window`'s fixture deliberately contains a real, matched OTLP observation
outside the scenario's selected window, specifically to distinguish "no observation exists in this
context" from "no observation exists anywhere" - and a paired sanity-break test proves that widening
the window to include that observation flips the classification to `CONFIRMED`.

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
  relation_types: [CALLS]         # restricts comparison to these relation types - keep this tight
                                   # (see "unexpected facts" below for why it matters since I2)

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
  relations:                      # canonical identities that MUST NOT exist (I2) - type/source/
    - type: RECEIVES_FROM         # target only; status/evidence (or any other key) are rejected,
      source: service:x           # since a forbidden assertion is unconditional, not a rule
      target: queue:y
```

A canonical relation is "in scope" when its source or target is listed under `scope.entities`
(and, if given, its type is in `scope.relation_types`). Only in-scope facts are compared - this
lets scenarios share infrastructure (e.g. multiple scenarios both mentioning ProductService)
without becoming brittle against unrelated facts.

**Keep `scope.relation_types` tight.** Since I2 enforces unexpected-fact detection, a scope that's
wider than the relation types actually under test will start failing on legitimate facts the
scenario never intended to assert anything about - e.g. a scoped operation's `PROVIDES` edge, if
`relation_types` only lists `CALLS`, would otherwise show up as an `UNEXPECTED` failure. Every
scenario in this suite restricts `relation_types` explicitly for exactly this reason.

## Ground truth is independent of AIP

`expected.yaml` and `forbidden.relations` are hand-authored, not generated from AIP's own
derivation code. In particular, the evaluator never computes a scenario's expected
`CONFIRMED`/`OBSERVED_ONLY` status from evidence booleans itself (that would just duplicate the
behavior under test) - it reads the status AIP already produced (via `app.analysis.runtime`, the
same code backing the real `/api/analysis/runtime/*` endpoints) and compares it against the
independently declared expectation.

## Suite internals (for contributors)

```text
loader.py      discovers scenarios and validates expected.yaml, including forbidden.relations and
               the optional input/reconciliation/declarations/ convention (I3)
runner.py      resets state, ingests declarations, injects OTLP fixtures, optionally re-imports
               reconciliation declarations (I3), orchestrates a run
projector.py   reads raw canonical relation edges from Neo4j, labels them by AIP's own
               CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW classification (never re-derives it)
comparator.py  expectation-driven exact comparison: MISSING, SEMANTIC_MISMATCH,
               FORBIDDEN_PRESENT, and UNEXPECTED mismatches
reporter.py    renders the human-readable PASS/FAIL report for all four mismatch kinds
```

See the I1, I2, and I3 specifications for the full design rationale, including why status must be
read from AIP rather than recomputed, why canonical identity (not Cypher row shape) is the
comparison contract, why forbidden assertions are identity-only rather than a conditional rules
language, and why evidence reconciliation is exercised through a real re-import rather than
simulated.
