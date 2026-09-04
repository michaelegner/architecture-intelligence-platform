# AIP Evaluation Suite

This directory holds two independent deterministic-evaluation suites, run via `python -m
evaluation run` (relation facts, below) and `python -m evaluation answers` (architecture answers,
[§ below](#the-architecture-answers-suite-i14)). Both prove AIP's real output against hand-authored,
independently frozen ground truth - never generated from AIP's own output - but compare a different
public shape: the older suite compares canonical relation facts (`type`/`source`/`target`/`status`/
evidence booleans); the newer one compares the complete v0.4 `ArchitectureAnswer` envelope. They
share nothing but the trivial: scenario-directory discovery conventions and
`app.architecture_intelligence.canonical_json`'s deterministic JSON serialization.

Deterministic evaluation kernel for AIP. Implements Iteration 1
([`i1-evaluation-kernel.md`](../docs/specifications/0.2.0/i1-evaluation-kernel.md), shipped as
`v0.2.0-alpha.1`), Iteration 2
([`i2-topology-directionality.md`](../docs/specifications/0.2.0/i2-topology-directionality.md),
`v0.2.0-alpha.2`), Iteration 3
([`i3-evidence-runtime-semantics.md`](../docs/specifications/0.2.0/i3-evidence-runtime-semantics.md),
`v0.2.0-alpha.3`), and Iteration 4
([`i4-coverage-hardening.md`](../docs/specifications/0.2.0/i4-coverage-hardening.md),
`v0.2.0-rc.1`) of the `v0.2.0` release
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

Ten scenarios currently exercise:

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
  transitions `CONFIRMED -> OBSERVED_ONLY`,
- **(I4)** partial observation - within a single scenario, one declared relation is observed while
  a second declared relation of the *same* observed interaction kind and a third of a *different,
  unobserved* interaction kind are not, and each gets its own independently correct status and
  qualitative coverage rather than being collapsed into one coarse per-service signal,
- **(I4)** a pure declared-only REST relation with no runtime observation at all, completing the
  release specification's ten-scenario core-suite target.

## What this suite does not (yet) test

The suite remains deliberately narrow. It does **not** implement:

- DLQ directionality or cross-batch HTTP correlation scenarios (both explicitly optional even at
  final release, per §16-17 of the I4 specification - added only if inexpensive, never required),
- quantitative telemetry coverage - coverage stays the fixed qualitative vocabulary
  `SUFFICIENT`/`PARTIAL`/`NONE`/`UNKNOWN`, never a numeric score,
- a dedicated "wrong direction" report category distinct from missing/unexpected/forbidden -
  directionality is checked through the combination of those three, not a separate classifier,
- an LLM-based evaluator, a generic policy/rules engine, or precision/recall scoring.

I2 closed the two things I1 left unenforced: `forbidden.relations` is no longer rejected when
non-empty, and an unexpected in-scope fact is no longer just a diagnostic - both now fail a
scenario. See §3 of the I2 specification for the full rationale.

I3 closed the remaining status gap (`NOT_OBSERVED_IN_WINDOW`) and proved the evidence-preservation
invariant (`Delete(Fact) iff Evidence(Fact) is empty`) through a real declaration re-import, without
adding any new architecture-intelligence concept - see §4 of the I3 specification.

I4 completed the release-level ten-scenario core suite (partial observation with qualitative
coverage qualification, the pure declared-only REST case) and turned the alpha-quality suite into a
release-candidate-quality one: strict scenario-schema validation, reconciliation-fixture
hardening, and deterministic comparator/report ordering - without adding another
architecture-intelligence dimension. See §2/§4/§8-10 of the I4 specification.

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
AIP Evaluation — I4

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair
[PASS] 07-not-observed-in-window
[PASS] 08-evidence-reconciliation
[PASS] 09-partial-observation
[PASS] 10-declared-rest-relation

Scenarios:          10
Passed:             10
Failed:             0

Missing facts:      0
Unexpected facts:   0
Forbidden facts present: 0
Wrong statuses:     0
Evidence errors:    0

RESULT: PASS
```

Exit code `0` means every scenario passed; `1` means at least one semantic evaluation failure;
`2` means invalid scenario configuration (the suite never exits `0` on failure). An unexpected
programmer or infrastructure error (e.g. Docker/Testcontainers unavailable) is not normalized to
one of these codes - it terminates with a Python traceback instead (I4 spec §11 deliberately does
not require suppressing those).

### Local reproducibility and determinism (I4)

A clean checkout reproduces this result without Docker running anything but the ephemeral
Testcontainers Neo4j, and without any LLM API key (this suite never invokes the LLM query layer):

```bash
uv sync

uv run ruff check .
uv run ruff format --check .

uv run pytest tests/unit
uv run pytest tests/integration

uv run python -m evaluation run
```

Running the last command more than once against a fresh container produces byte-identical stdout:
same scenarios, same PASS/FAIL result, same ordered scenario lines, same ordered mismatch output,
same counters. This holds because `comparator.py`'s `compare()` sorts its own `mismatches` output
by canonical `(type, source, target, kind)` identity before returning it (I4) - it does not depend
on Python's `set[RelationFact]` iteration order (subject to string-hash randomization) the way an
earlier, unsorted version would have. No dedicated benchmark/history framework is introduced to
check this; it is a property of the comparator itself.

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

The ten scenarios:

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
| `09-partial-observation` | OrderService declares two REST calls and one messaging send; only the ProductService call is observed -> `CONFIRMED`, while the InventoryService call and the queue send are each `NOT_OBSERVED_IN_WINDOW` with independently correct qualitative coverage (`SUFFICIENT` for the unobserved call, `PARTIAL` for the unobserved send). |
| `10-declared-rest-relation` | ProductService declares `GET /products/{id}`; OrderService explicitly declares a `CALLS` dependency on it. No telemetry, no `observation` block, no runtime status/evidence assertion - relation identity and direction only. |

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
completely unaffected (all nine other scenarios).

### `NOT_OBSERVED_IN_WINDOW` is context-qualified (I3)

`NOT_OBSERVED_IN_WINDOW` means exactly: *the relation has declared support, but AIP found no
matching observed evidence in the selected environment and observation window.* It does **not**
mean unused, obsolete, dead, unreachable, or forbidden - the relation remains an expected canonical
fact. `07-not-observed-in-window`'s fixture deliberately contains a real, matched OTLP observation
outside the scenario's selected window, specifically to distinguish "no observation exists in this
context" from "no observation exists anywhere" - and a paired sanity-break test proves that widening
the window to include that observation flips the classification to `CONFIRMED`.

### Partial observation and qualitative coverage (I4)

Status and coverage answer two different questions (I4 spec §4.2):

```text
status    = is this relation observed in the selected environment/window?
coverage  = how much relevant telemetry did AIP actually see for the subject at all?
```

A `NOT_OBSERVED_IN_WINDOW` relation can have any of `SUFFICIENT`/`PARTIAL`/`NONE`/`UNKNOWN`
coverage without that combination ever meaning obsolete, unused, dead, or architecturally absent -
coverage qualifies how much weight the non-observation should carry, it never overrides the
status. `09-partial-observation` exercises this directly: OrderService's unobserved call to
InventoryService shares its interaction kind (HTTP) with the one relation that *is* observed, so
its coverage is `SUFFICIENT`; its unobserved send to `audit-q` doesn't (no messaging telemetry
exists at all), so its coverage is `PARTIAL`. The evaluator asserts this by calling AIP's existing
production runtime-analysis boundary directly -
`app.analysis.runtime.declared_only_relations()`/`telemetry_coverage()` - the same functions
behind the real `/api/analysis/runtime/*` endpoints, never a reimplementation of
`_classify_coverage`'s logic.

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
loader.py      discovers scenarios and strictly validates expected.yaml (I4) - forbidden.relations,
               the optional input/reconciliation/declarations/ convention (I3, source-discovery-
               backed rejection of non-importable fixtures since I4), and scope-consistency
runner.py      resets state, ingests declarations, injects OTLP fixtures, optionally re-imports
               reconciliation declarations (I3), orchestrates a run
projector.py   reads raw canonical relation edges from Neo4j, labels them by AIP's own
               CONFIRMED/OBSERVED_ONLY/NOT_OBSERVED_IN_WINDOW classification (never re-derives it)
comparator.py  expectation-driven exact comparison - MISSING, SEMANTIC_MISMATCH,
               FORBIDDEN_PRESENT, and UNEXPECTED mismatches - sorted deterministically (I4)
reporter.py    renders the human-readable PASS/FAIL report for all four mismatch kinds
```

See the I1, I2, I3, and I4 specifications for the full design rationale, including why status must
be read from AIP rather than recomputed, why canonical identity (not Cypher row shape) is the
comparison contract, why forbidden assertions are identity-only rather than a conditional rules
language, why evidence reconciliation is exercised through a real re-import rather than simulated,
and why scenario-schema strictness and comparator ordering are load-bearing for a
release-candidate-quality suite rather than cosmetic.

---

## The architecture-answers suite (I1.4)

Implements Iteration 1.4
([`i1-service-contract-and-dependency-vertical-slice.md`](../docs/specifications/0.4.0/i1-service-contract-and-dependency-vertical-slice.md)
§25) of the `v0.4.0` release. Proves `ArchitectureIntelligenceService.get_service_dependencies` -
the whole I1 dependency vertical slice - against independently authored ground truth: destination
resolution, qualification, claims, limitations, evidence references, and snapshot/observation-context
identity, compared exactly against a frozen `expected_answer.json`.

### What this suite tests

```text
scenario fixture -> real ArchitectureIntelligenceService.get_service_dependencies -> compare -> PASS/FAIL
```

Eight scenarios exercise the spec's required semantic anchors: an HTTP dependency (`CONFIRMED`), a
messaging dependency (`CONFIRMED`), `NOT_OBSERVED_IN_WINDOW` with coverage, an undeclared but
observed dependency (`OBSERVED_ONLY`), an unresolved queue destination (`DIRECT_TARGET_FALLBACK` +
`UNRESOLVED_IDENTITY`), one destination reached through two independent delivery paths, an unknown
service, and a known service with zero dependencies. Outcome branches already proven by unit tests
(`PARTIAL`, `OBSERVATION_CONTEXT_REQUIRED`, `SNAPSHOT_NOT_AVAILABLE`, `RESULT_LIMIT_EXCEEDED`) are
not duplicated here.

### Running

```bash
uv run python -m evaluation answers                        # all scenarios
uv run python -m evaluation answers sync-confirmed          # one scenario, by directory name
uv run python -m evaluation answers --scenario sync-confirmed
```

`python -m evaluation run` (no arguments) is unchanged and still runs the relation-facts suite -
`answers` is a separate, additive subcommand. Same exit-code contract as `run`: `0` every scenario
passed and both runs were semantically identical, `1` at least one semantic failure, `2` invalid
scenario configuration.

Every invocation runs the **full scenario suite twice**, end to end (reset -> ingest declarations ->
inject telemetry -> reconcile -> call the real service), and writes a deterministic JSON report to
`evaluation/architecture_answers/results/i1-evaluation-result.json`:

```json
{
  "schema_version": "aip-evaluation-result/v1",
  "suite": "architecture-answers-i1",
  "result": "PASS",
  "run_count": 2,
  "semantic_outputs_identical": true,
  "run_output_sha256": ["sha256:...", "sha256:..."],
  "scenarios": [
    {
      "id": "sync-confirmed",
      "result": "PASS",
      "missing_claim_ids": [],
      "unexpected_claim_ids": [],
      "field_mismatches": [],
      "broken_evidence_refs": []
    }
  ],
  "summary": { "scenarios": 8, "passed": 8, "failed": 0 }
}
```

No timestamps, absolute paths, or other run-specific values appear anywhere in this file - two
invocations against a fresh container produce a byte-identical report.

### Scenario structure

```text
evaluation/architecture_answers/scenarios/sync-confirmed/
├── request.yaml            # small, hand-authored: service_id, observation{environment,window}
├── expected_answer.json    # frozen literal ArchitectureAnswer - every public field
└── input/
    ├── declarations/        # same OpenAPI/AsyncAPI/Architecture Manifest convention as the
    │                         # relation-facts suite - self-contained per scenario, never examples/
    └── telemetry/spans.py   # same real-OTLP-path convention
```

`expected_answer.json` is not a bespoke ground-truth format - it's a literal instance of the same
`ArchitectureAnswer[ServiceDependenciesData]` Pydantic type
(`app.architecture_intelligence.contracts`) the real service returns, loaded via `model_validate`.
This means the frozen fixture is schema-validated for free, and every public field (producer,
snapshot, observation context, full claim envelope including both evidence-reference lists,
limitations with `code`/`message`/`claim_ids`) is represented explicitly - nothing about the answer
can be silently narrowed away by a trimmed comparison model.

### Ground truth is independent of AIP - literally, not just by convention

Unlike hashes a human could plausibly hand-verify, `claim_id`, `context_id`, `snapshot_id`, and
`model_revision` are sha256 digests of canonicalized state. Comparing AIP's output against a value
computed by calling AIP's own hashing functions a second time would let a shared defect pass its own
grading. `evaluation/architecture_answers/reference/` is a small, deliberately separate
reimplementation of those formulas - transcribed from the spec text (§12.1, §16.2, §17/§18), not
imported from `app.architecture_intelligence.*` - used **only at scenario-authoring time**, never by
the live loader/runner/comparator:

```bash
uv run python -m evaluation.architecture_answers.reference snapshot evaluation/architecture_answers/scenarios/sync-confirmed
uv run python -m evaluation.architecture_answers.reference context-id test 2026-08-26T00:00:00Z 2026-08-27T00:00:00Z
uv run python -m evaluation.architecture_answers.reference claim-id <subject_id> DIRECT_DEPENDENCY <object_id> <delivery_kind> <delivery_via_id>
uv run python -m evaluation.architecture_answers.reference declared-evidence-id <source_type> <service_slug> [revision]
uv run python -m evaluation.architecture_answers.reference observed-evidence-id <environment> <bucket_start> <subject_id> <relation_type> <object_id>
```

An author runs this against a scenario's prepared fixture, hand-verifies the printed literals
against the fixture's own topology, and freezes them into `expected_answer.json`. **Regenerate a
scenario's `snapshot_id`/`model_revision` (the largest, most maintenance-sensitive piece of the
reference tool - it re-implements §18's full canonicalization procedure) whenever that scenario's
own `input/` fixture files change** - this is inherent to frozen-literal expectations, not
optional.

**`producer.build_revision` is the one field deliberately *not* frozen.** Every other identity is a
property of a scenario's fixture content, stable across commits - `producer.build_revision` is the
current commit's own SHA, which by definition changes every commit. Freezing it would reproduce
exactly the portability defect the snapshot/context identities already had to be fixed for (an
earlier version of this suite did freeze `Evidence.source_file`-derived hashes via an absolute,
checkout-location-specific path, and it broke on the first CI run on a different machine). Instead,
`runner.py` injects the real candidate git SHA (`evaluation/architecture_answers/candidate.py`,
`git rev-parse HEAD`) into the live service call, and `comparator.py` independently re-derives that
same SHA to check the actual answer against - never trusting whatever the runner happened to
inject, and never a placeholder literal (spec §27/§28 name a missing or placeholder build revision
as a release blocker).

### Suite internals (for contributors)

```text
model.py       Request/Scenario - the expected side is the real ArchitectureAnswer type directly,
               not a bespoke dataclass
loader.py      validates request.yaml's small schema; loads+validates expected_answer.json via the
               real Pydantic contract
comparator.py  full-envelope diff: claim identity by real claim_id (never re-derived), every claim
               field including both evidence-reference lists, answer-level fields (schema_version,
               tool, producer, outcome, snapshot, context, top-level evidence_refs, limitations),
               plus an independent real-Neo4j evidence-existence check (broken_evidence_refs)
runner.py      two full clean-state passes per suite run, using evaluation.fixture_setup's shared
               reset/ingest/telemetry/reconcile helpers and the real ArchitectureIntelligenceService
reporter.py    deterministic JSON report, written to evaluation/architecture_answers/results/ only
               for an unfiltered full-suite run - a scenario-filtered run prints, never overwrites
candidate.py   the real candidate git SHA (`git rev-parse HEAD`), asked independently by both
               runner.py (what it injects) and comparator.py (what it checks against)
reference/     offline-only identity reimplementation (see above) - never imported by the modules
               above
```
