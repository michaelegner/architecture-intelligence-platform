# AIP v0.2.0 — Iteration 2 Implementation Specification

**Status:** Draft 1 — self-contained implementation contract
**Release target:** `v0.2.0-alpha.2`
**Iteration:** I2 — Topology and Directionality
**Project:** Architecture Intelligence Platform (AIP)

---

## 1. Purpose

Iteration 1 (`v0.2.0-alpha.1`, tagged and released) proved the evaluation kernel end-to-end with
three scenarios, but deliberately left the comparator's strictest checks unenforced:

```text
non-empty forbidden assertions        -> rejected as unsupported configuration
exhaustive unexpected-fact detection  -> counted for diagnostics only, never failed a scenario
explicit inverse-direction assertions -> not required by any I1 scenario
```

Iteration 2 closes exactly that gap. It does not add new AIP architecture intelligence - v0.1
already computes `PROVIDES`/`CALLS`/`SENDS`/`RECEIVES_FROM` correctly, including orphan queues,
mixed sync/async dependencies between the same service pair, and request/response queue pairs. I2
proves it, the same way I1 proved `CONFIRMED`/`OBSERVED_ONLY`.

The iteration is successful when this pipeline works reproducibly for topology-sensitive
scenarios:

```text
scenario fixture (richer topology)
      |
      v
     AIP
      |
      v
canonical architecture facts
      |
      v
scenario-owned comparison scope
      |
      v
expected.yaml + forbidden.yaml assertions
      |
      v
deterministic comparison, now including:
    forbidden-fact detection
    exhaustive unexpected-fact detection
      |
      v
PASS / FAIL
```

The target release for this iteration is:

```text
v0.2.0-alpha.2
```

---

### 1.1 Specification Relationship

This document is self-contained for implementing Iteration 2, and builds directly on the shipped
I1 implementation (`docs/specifications/0.2.0/i1-evaluation-kernel.md`, tagged `v0.2.0-alpha.1` at
commit `52bf2b4`).

```text
I1 specification
    = implementation contract for v0.2.0-alpha.1 (shipped)

I2 specification
    = implementation contract for v0.2.0-alpha.2 (this document)

v0.2.0 specification
    = final release contract and broader delivery context
```

I2 SHALL NOT re-implement or redesign anything I1 already delivers correctly. Where this document
is silent on a topic I1 already specified (isolation strategy, canonical fact access, projection
rules, evidence semantics, CLI shape), the I1 specification remains authoritative.

Existing AIP source code and technical documentation remain authoritative for the behavior of
current OpenAPI, AsyncAPI, Architecture Manifest, OTLP, canonical-ID, evidence, and persistence
components that this specification reuses.

---

## 2. Iteration Goal

Iteration 2 SHALL deliver:

1. `forbidden.relations` evaluation (non-empty forbidden assertions are no longer rejected - they
   are evaluated, and a matching fact present in the graph fails the scenario),
2. exhaustive unexpected-in-scope-fact detection (promoted from I1's diagnostic-only count to a
   release-blocking failure),
3. three new topology-sensitive scenarios exercising orphan messaging, mixed REST+async between
   the same service pair, and a request/response queue pair,
4. explicit inverse-direction assertions in at least the orphan-messaging and request/response
   scenarios,
5. an updated report format reflecting that forbidden/unexpected checks are now enforced.

The three new scenarios are:

```text
4. ORPHAN MESSAGING
5. MIXED REST + ASYNC
6. REQUEST/RESPONSE QUEUE PAIR
```

Together with I1's three scenarios, I2 leaves the suite at six of the eight required core
scenarios from `docs/specifications/0.2.0/specification.md` §14 (Scenarios 2, 3, 5, 6, 7, 8).
Scenario 1 (a pure declared-only `PROVIDES`/`CALLS` relation, no runtime evidence at all) and
Scenarios 4, 9, 10 (`NOT_OBSERVED_IN_WINDOW`, evidence reconciliation, partial observation) remain
out of scope - see §3.

---

## 3. Non-Goals

Iteration 2 SHALL NOT implement:

- `NOT_OBSERVED_IN_WINDOW` (I3),
- evidence reconciliation or partial-observation semantics (I3),
- DLQ directionality or cross-batch HTTP correlation scenarios (I4, optional there too),
- Scenario 1 (declared-only `PROVIDES`/`CALLS`, no runtime evidence) - cheap to add later but not
  required by this iteration's topology/directionality focus,
- a dedicated "wrong direction" report category distinct from missing/unexpected/forbidden -
  Iteration 2 achieves directionality checking through the combination of those three, not a new
  fourth classification (see §13.4),
- a generic policy language or rules engine (forbidden/expected remain concrete fact lists, per I1
  §4.2/§9.6 of the release spec),
- new canonical architecture entity or relation types,
- an LLM-based evaluator, GraphRAG, or precision/recall scoring,
- a dedicated CI release gate beyond what I1 already established.

I2 SHALL use the final scenario-file shape (already used since I1) - `forbidden.relations` was
always present in the schema; only its *evaluation* was deferred. No scenario-format migration is
required.

---

## 4. Design Principles

### 4.1 Still No Second Reasoning Engine

I1 §4.1-§4.4's principles remain unchanged and binding: vertical slice first, ground truth
independent of AIP's own derivation code, canonical semantics (not Cypher row shape) as the
contract, fully deterministic (no LLM key required).

### 4.2 Forbidden Is an Identity Assertion, Not a Fact Assertion

An `expected` relation asserts a concrete fact: identity **and** status **and** evidence.

A `forbidden` relation asserts only that a canonical identity must not exist, **regardless of
status or evidence**:

```text
forbidden.relations[i] = (type, source, target)
```

`status`/`evidence` fields are not part of the forbidden schema. If a scenario author adds them,
the loader SHALL reject the scenario as invalid configuration rather than silently ignoring the
extra fields - I2 does not introduce conditional forbidden assertions ("forbidden only if
OBSERVED", etc.); that would be exactly the rules-DSL creep §9.6 of the release spec rules out.

### 4.3 Unexpected-Fact Enforcement Is Structural, Not Enumerated

Promoting unexpected-fact detection from diagnostic to blocking does not mean enumerating every
possible wrong fact per scenario. It means:

```text
for every in-scope actual fact:
    it is either expected, forbidden-and-absent (fine), or unexpected (FAIL)
```

The comparator does not need a list of "known bad" facts beyond `forbidden.relations` - anything
in scope that isn't explicitly expected is unexpected by construction. This is why scope
precision (I1 §8) matters more starting in I2 than it did in I1: a scenario whose `scope.entities`
casts too wide a net will start failing on legitimate, unrelated facts it never intended to
assert anything about.

### 4.4 Explicit Inverse Assertions Belong Where Direction Is the Point

I1 §11.6 deferred "explicit inverse-direction assertions" to I2 for exactly the scenarios where
getting the direction backwards is the realistic failure mode: orphan messaging (a would-be
consumer must not appear as a producer) and request/response pairs (each participant's two queues
must not have their roles swapped). Mixed REST+async does not need an inverse assertion - `CALLS`
and `SENDS`/`RECEIVES_FROM` are structurally distinct relation types already; there is no
plausible "collapse" for a forbidden assertion to guard against.

### 4.5 Canonical Semantics Used by I2

I2 uses the same four canonical relation types as I1 - no new relation type is introduced:

```text
(Service)-[:CALLS]->(Operation)
(Service)-[:PROVIDES]->(Operation)
(Service)-[:SENDS]->(Queue)
(Service)-[:RECEIVES_FROM]->(Queue)
```

I2 exercises them at *plural* scale within one scenario (a service with two queue targets, or two
services sharing two queues in opposite roles) rather than introducing new semantics - this is
precisely what I1's post-merge hardening fix (`fix/v0.2-i1-evaluation-correctness`, merged before
this document was written) made safe: `evaluation/projector.py` now classifies status at exact
`(type, source, target)` identity, not the coarser `(source, type)` key I1 originally shipped
with, which would have silently mislabeled exactly the multi-target scenarios I2 requires.

---

## 5. Evaluation Data Model Changes

### 5.1 `RelationFact` Is Unchanged

`evaluation/model.py`'s `RelationFact` (type, source, target, status, declared_evidence,
observed_evidence) is reused as-is for both expected and forbidden entries. A forbidden entry is
represented as a `RelationFact` with `status = declared_evidence = observed_evidence = None`
(matching I1's existing "unset field is not part of the assertion" convention) - no new dataclass
is required.

### 5.2 `Scenario` Gains `forbidden_relations`

```python
@dataclass(frozen=True)
class Scenario:
    id: str
    description: str
    scope: ScenarioScope
    observation: Observation
    expected_relations: tuple[RelationFact, ...]
    forbidden_relations: tuple[RelationFact, ...]   # new in I2
    path: Path
```

### 5.3 `ScenarioResult` Gains Explicit Failure Categories

`evaluation/comparator.py`'s `Mismatch.kind` gains two values alongside I1's `MISSING` and
`SEMANTIC_MISMATCH`:

```text
FORBIDDEN_PRESENT   a forbidden (type, source, target) identity exists in the actual facts
UNEXPECTED          an in-scope actual fact is neither expected nor forbidden
```

For `FORBIDDEN_PRESENT` and `UNEXPECTED` mismatches, `Mismatch.expected` holds the forbidden
identity or `None` respectively, and `Mismatch.actual` holds the actual fact found. The exact
dataclass shape is an implementation detail; the four-category failure vocabulary above is
normative.

---

## 6. Declarative Scenario Format Changes

### 6.1 `forbidden.relations` Is Now Evaluated

```yaml
forbidden:
  relations:
    - type: RECEIVES_FROM
      source: service:inventory-service
      target: queue:unused-q
```

Each entry requires exactly `type`, `source`, `target` - the same validation as an expected
relation's identity fields (known relation type, well-formed canonical id), but `status` and
`evidence` keys are forbidden on a forbidden entry (§4.2) and SHALL cause a
`ScenarioValidationError` if present.

Duplicate forbidden entries (same `(type, source, target)`) SHALL be rejected the same way I1
rejects duplicate expected entries.

A forbidden identity that also appears in `expected.relations` is a contradictory scenario
(asserting a fact must both exist and not exist) and SHALL be rejected as invalid configuration.

### 6.2 No Change to `expected.relations` or `scope`

I1's schema for `expected.relations` and `scope` is unchanged. Scenario authors SHOULD keep
`scope.entities` as tight as the topology under test allows, per §4.3.

---

## 7. Comparison Algorithm Changes

Extends I1 §16 (`evaluation/comparator.py`). For each scenario, given `expected`, `forbidden`, and
projected in-scope `actual`:

```text
1. every expected fact must have an exact matching actual fact
   (identity + status + evidence, unchanged from I1)
   -> otherwise MISSING or SEMANTIC_MISMATCH

2. every forbidden identity must have no matching actual fact
   (identity only - status/evidence irrelevant)
   -> otherwise FORBIDDEN_PRESENT

3. every in-scope actual fact whose identity is neither expected nor forbidden
   is UNEXPECTED
```

### 7.1 Ordering and Independence

These three checks are independent and additive - a scenario can accumulate mismatches from more
than one category. `unexpected_count` (I1's diagnostic-only field) is retired in favor of real
`UNEXPECTED` mismatches; a scenario with zero mismatches across all three categories passes.

### 7.2 Matching Remains Exact

No fuzzy matching, wildcards, or partial-identity matching is introduced. A forbidden entry
matches an actual fact only when `type`, `source`, and `target` are all exactly equal (I1 §16.3's
exact-matching rule extends unchanged to forbidden identity comparison).

---

## 8. Reporting Changes

Extends I1 §17 (`evaluation/reporter.py`). The diagnostic line:

```text
Unexpected facts:   not enforced in I1
```

is replaced with a real, enforced count, and a new forbidden-facts line is added:

```text
AIP Evaluation — I2

[PASS] 01-rest-confirmed
[PASS] 02-rest-observed-only
[PASS] 03-async-confirmed
[PASS] 04-orphan-messaging
[PASS] 05-mixed-rest-async
[PASS] 06-request-response-queue-pair

Scenarios:            6
Passed:                6
Failed:                0

Missing facts:         0
Unexpected facts:      0
Forbidden facts present: 0
Wrong statuses:        0
Evidence errors:       0

RESULT: PASS
```

A failure example for each new category SHOULD be documented in `evaluation/README.md`, following
I1's existing failure-example convention.

A dedicated "Wrong directions" line (as sketched illustratively in the release-level
specification's final report, §15) is not required by I2 - a direction error naturally surfaces as
one `MISSING` (the correct-direction fact is absent) plus, if a `forbidden` entry names the
swapped-direction fact, one `FORBIDDEN_PRESENT`, or otherwise one `UNEXPECTED`. Adding a distinct
"wrong direction" classification on top of that is deferred to I4/I5 if it proves cheap once real
usage shows it's worth the extra bookkeeping (§3).

---

## 9. Loader Changes

Extends I1 §7 (`evaluation/loader.py`):

- `forbidden.relations` MAY now be non-empty; the I1-specific rejection
  (`"non-empty forbidden.relations is not supported in I1"`) is removed.
- Each forbidden entry is validated for known relation type, well-formed canonical `source`/
  `target` ids, and absence of `status`/`evidence` keys (§6.1).
- Duplicate forbidden entries are rejected (§6.1).
- A forbidden identity duplicated in `expected.relations` is rejected as contradictory (§6.1).

I1's post-merge hardening (nested mapping/list validation, timestamp validation, empty-suite
rejection - `docs/gaps/AIP_v0.2.0_I1_Post_Merge_Review.md` F2-F4) already covers the general
validation infrastructure I2's forbidden-parsing reuses; no further hardening of those mechanisms
is anticipated here.

---

## 10. Scenario 4 — Orphan Messaging

### 10.1 Purpose

Verify that AIP does not invent a consumer for a sender-only queue, or a producer for a
consumer-only queue - the declared-topology analyses (spec `analysis/queues.py` A3/A4) already
detect these; this scenario proves the *canonical facts underneath* those analyses are correct via
the RelationFact comparison contract, and explicitly forbids the plausible wrong-guess inverse
relation for each.

Per `CLAUDE.md`'s existing fixture guidance ("Additional fixtures should include `unused-q`
(sender, no consumer) and `unknown-producer-q` (consumer, no known sender) to exercise analyses
A3/A4"), this scenario is the first place that guidance is actually exercised by the evaluation
suite.

### 10.2 Architecture

```text
OrderService
     |
     | SENDS
     v
unused-q                (no consumer anywhere)


unknown-producer-q      (no producer anywhere)
     ^
     | RECEIVES_FROM
     |
InventoryService
```

### 10.3 Required Input

Declared: OrderService's AsyncAPI declares `publish` on `unused-q` only (no other service
declares `subscribe` on it anywhere in the scenario's `input/declarations/`). InventoryService's
AsyncAPI declares `subscribe` on `unknown-producer-q` only (no other service declares `publish` on
it).

Runtime: both edges SHALL also be observed (both `CONFIRMED`), so the scenario proves orphan
topology is compatible with `CONFIRMED` status, not just declared-only status - an orphan queue is
not inherently unobserved.

### 10.4 Expected Result

```yaml
expected:
  relations:
    - type: SENDS
      source: service:order-service
      target: queue:unused-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: RECEIVES_FROM
      source: service:inventory-service
      target: queue:unknown-producer-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

forbidden:
  relations:
    - type: RECEIVES_FROM
      source: service:inventory-service
      target: queue:unused-q
    - type: SENDS
      source: service:order-service
      target: queue:unknown-producer-q
```

### 10.5 Acceptance

```text
both expected facts exist with status CONFIRMED
neither forbidden fact exists
no other in-scope fact exists (unexpected-fact enforcement)
```

---

## 11. Scenario 5 — Mixed REST and Async Between the Same Services

### 11.1 Purpose

Verify that a service pair using both a synchronous and an asynchronous interaction mode has both
preserved as distinct canonical relation types, not collapsed into one generic dependency edge.

### 11.2 Architecture

```text
OrderService
     |
     | CALLS
     v
ProductService.GET /products/{id}

OrderService
     |
     | SENDS
     v
order-status-q
     ^
     | RECEIVES_FROM
     |
ProductService
```

### 11.3 Required Input

Reuses I1 scenario 1's declared REST pair (OrderService Architecture Manifest `CALLS`
`product-service.getProduct`; ProductService OpenAPI `GET /products/{id}`), plus a new AsyncAPI
declaration on both services for `order-status-q` (OrderService `publish`, ProductService
`subscribe`).

Runtime: all three relations (`CALLS`, `SENDS`, `RECEIVES_FROM`) are observed -> all `CONFIRMED`.

### 11.4 Expected Result

```yaml
expected:
  relations:
    - type: CALLS
      source: service:order-service
      target: operation:service:product-service:GET:/products/{id}
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: SENDS
      source: service:order-service
      target: queue:order-status-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: RECEIVES_FROM
      source: service:product-service
      target: queue:order-status-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

forbidden:
  relations: []
```

No forbidden entries are required here (§4.4) - unexpected-fact enforcement alone is sufficient to
catch an accidental extra edge, and there is no plausible "collapse" failure mode to name
explicitly.

### 11.5 Acceptance

```text
all three expected facts exist with status CONFIRMED
no other in-scope fact exists
```

---

## 12. Scenario 6 — Request/Response Queue Pair

### 12.1 Purpose

Verify a bidirectional queue pair between two services, where each participant is a sender on one
queue and a receiver on the other - the topology most likely to have its direction accidentally
swapped during ingestion or resolution.

### 12.2 Architecture

```text
OrderService     --SENDS-->         request-q       --RECEIVES_FROM-->   ProductService
ProductService   --SENDS-->         response-q      --RECEIVES_FROM-->   OrderService
```

### 12.3 Required Input

New AsyncAPI declarations: OrderService `publish`s `request-q` and `subscribe`s `response-q`;
ProductService `subscribe`s `request-q` and `publish`s `response-q`.

Runtime: all four relations observed -> all `CONFIRMED`.

### 12.4 Expected Result

```yaml
expected:
  relations:
    - type: SENDS
      source: service:order-service
      target: queue:request-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: RECEIVES_FROM
      source: service:product-service
      target: queue:request-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: SENDS
      source: service:product-service
      target: queue:response-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true
    - type: RECEIVES_FROM
      source: service:order-service
      target: queue:response-q
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

forbidden:
  relations:
    - type: RECEIVES_FROM
      source: service:order-service
      target: queue:request-q
    - type: SENDS
      source: service:product-service
      target: queue:response-q
      # NOTE: product-service DOES send response-q (see expected, above) - this entry is
      # deliberately NOT included; it is listed here only to call out the trap. The real forbidden
      # set is the four *swapped-role* facts below.
```

The last commented example above is a deliberate illustration of the trap this specification
wants implementers to avoid: do not forbid a service's *correct* role on its *other* queue. The
actual forbidden set is each participant's swapped role on **the same queue** it already has a
role on:

```yaml
forbidden:
  relations:
    - type: RECEIVES_FROM
      source: service:order-service
      target: queue:request-q          # OrderService sends request-q, must not also receive it
    - type: SENDS
      source: service:product-service
      target: queue:request-q          # ProductService receives request-q, must not also send it
    - type: SENDS
      source: service:order-service
      target: queue:response-q         # OrderService receives response-q, must not also send it
    - type: RECEIVES_FROM
      source: service:product-service
      target: queue:response-q         # ProductService sends response-q, must not also receive it
```

### 12.5 Acceptance

```text
all four expected facts exist with status CONFIRMED
none of the four swapped-role forbidden facts exist
no other in-scope fact exists
```

---

## 13. Runtime Fixture Strategy

Unchanged from I1 §12: static OTLP fixtures through the real `/v1/traces` path, built the same way
`tests/integration/test_telemetry_api.py` and I1's `evaluation/scenarios/*/input/telemetry/spans.py`
already do. Scenario 4 needs two independent messaging spans (one per orphan queue); Scenario 5
needs one HTTP CLIENT/SERVER pair plus one messaging pair; Scenario 6 needs two messaging pairs (a
send/receive observation for each of `request-q` and `response-q`).

No new fixture *mechanism* is required - only new fixture *content*, following the established
`build_export_request() -> bytes` convention per scenario.

---

## 14. Evaluation-State Isolation

Unchanged from I1 §13. No new isolation concern is introduced by richer per-scenario topology.

---

## 15. Canonical Fact Access

Unchanged from I1 §14, with one correction already applied ahead of this document: I1's original
`evaluation/projector.py` read status via `app.analysis.runtime`'s `confirmed_relations()`/
`observed_only_relations()` and joined on `(source_id, relation_type)`, which is exactly the
coarse key I2's multi-target scenarios would have broken (`docs/gaps/AIP_v0.2.0_I1_Post_Merge_Review.md`
F1). The post-merge hardening fix already replaced this with a query built from
`app.analysis.runtime`'s own `_DECLARED_EXISTS`/`_NOT_DECLARED_EXISTS`/`_OBSERVED_EXISTS` guard
predicates, classifying at true `(type, source, target)` identity. I2 requires no further change
to `projector.py` itself - only to `comparator.py`, `loader.py`, and `reporter.py` as described
above.

---

## 16. Implementation Tasks

A practical implementation breakdown, mirroring I1's task-per-branch convention
(`docs/specifications/0.2.0/git-workflow.md`):

### Task I2.1 — Forbidden and Unexpected Enforcement

Deliver:

```text
Scenario.forbidden_relations
loader.py: parse/validate forbidden.relations (non-empty allowed, identity-only, no
    status/evidence, duplicate/contradiction checks)
comparator.py: FORBIDDEN_PRESENT and UNEXPECTED mismatch kinds, retire diagnostic-only
    unexpected_count
reporter.py: enforced "Unexpected facts" count, new "Forbidden facts present" line
```

Exit condition:

```text
a synthetic scenario with a deliberately present forbidden fact fails with FORBIDDEN_PRESENT
a synthetic scenario with a deliberately unexpected in-scope fact fails with UNEXPECTED
all three existing I1 scenarios still pass unchanged (forbidden.relations: [] in each)
```

### Task I2.2 — Three New Scenarios

Deliver:

```text
04-orphan-messaging      (declarations, telemetry, expected.yaml, forbidden entries)
05-mixed-rest-async      (declarations, telemetry, expected.yaml)
06-request-response-queue-pair  (declarations, telemetry, expected.yaml, forbidden entries)
```

Exit condition:

```text
6/6 scenarios pass deterministically
```

### Task I2.3 — Reporting, Documentation, Definition of Done

Deliver:

```text
reporter.py output matches §8's target shape
evaluation/README.md updated: forbidden/unexpected are now enforced, three new scenarios
    documented, failure examples for FORBIDDEN_PRESENT and UNEXPECTED added
```

Exit condition:

```text
Definition of Done (§17) fully satisfied
```

These tasks may be implemented in fewer or more GitHub issues if that better matches the
repository workflow, per I1's own closing note on this point.

---

## 17. Definition of Done

Iteration 2 is complete when all of the following are true:

- [ ] `forbidden.relations` is evaluated; a present forbidden fact fails the scenario.
- [ ] An in-scope actual fact that is neither expected nor forbidden fails the scenario.
- [ ] Forbidden entries are validated as identity-only (no `status`/`evidence`).
- [ ] Duplicate forbidden entries are rejected.
- [ ] A forbidden identity duplicated in `expected.relations` is rejected as contradictory.
- [ ] `04-orphan-messaging` passes, including both forbidden inverse-direction assertions.
- [ ] `05-mixed-rest-async` passes, proving `CALLS` and `SENDS`/`RECEIVES_FROM` coexist without
      collapsing.
- [ ] `06-request-response-queue-pair` passes, including all four swapped-role forbidden
      assertions.
- [ ] All three I1 scenarios still pass unchanged.
- [ ] The report shows enforced (not diagnostic) unexpected-fact and forbidden-fact counts.
- [ ] `evaluation/README.md` documents the new enforcement and the three new scenarios.
- [ ] Existing project tests remain green; new unit/integration tests cover
      `FORBIDDEN_PRESENT`/`UNEXPECTED` at the comparator level (pure Python) and end-to-end for
      each new scenario (Neo4j-backed).
- [ ] The evaluation suite still runs without an LLM API key.
- [ ] No new canonical model concept is introduced.

---

## 18. Alpha.2 Release Criteria

`v0.2.0-alpha.2` may be cut when:

```text
Scenarios:        6
Passed:           6
Failed:           0

Critical semantic errors: 0
```

and a clean checkout can reproduce the result using documented commands, per the same discipline
I1 established (`docs/gaps/AIP_v0.2.0_I1_Completion_Instructions.md`): implementation PR(s) merged,
remote CI green on the resulting `main` commit, local `main` fast-forwarded, tag pushed only after
that verification - not immediately after merge.

Its meaning is narrower than the full `v0.2.0` release:

> **AIP preserves canonical relation type and direction under richer topology, and the evaluation
> kernel now catches both a false-positive fact (forbidden) and a false-negative gap in
> enforcement (unexpected) - not just a missing or misclassified expected fact.**

---

## 19. Expected Follow-Up in Iteration 3

Iteration 3 is expected to extend the same kernel with:

```text
NOT_OBSERVED_IN_WINDOW
evidence reconciliation
evidence-preservation assertions
status transitions caused by surviving evidence
```

Iteration 2 SHOULD therefore avoid design choices that prevent those additions - in particular,
`evaluation/projector.py`'s classified-query approach (§15) already has room for a third branch per
relation type (`_DECLARED_EXISTS AND _NOT_OBSERVED_EXISTS -> NOT_OBSERVED_IN_WINDOW`, mirroring
`app.analysis.runtime`'s own O4) without restructuring anything I2 delivers - but SHALL NOT
implement it prematurely.

---

## 20. Summary

Iteration 2 makes the evaluation kernel strict in the two ways I1 explicitly deferred:

```text
a false architecture dependency (forbidden, present)   -> now caught
an undocumented extra dependency (unexpected, in scope) -> now caught
```

and proves those two checks hold under the topology shapes most likely to expose a directionality
or type-collapsing bug: orphan messaging, mixed sync/async, and request/response queue pairs.

The governing principle carries over unchanged from I1:

> **Prove the evaluation architecture with the smallest complete extension before expanding the
> scenario corpus further.**
