# AIP v0.4.1 — I2 Messaging Semantic Guards

**Status:** Draft 0.1

**Target release:** `v0.4.1`

**Release increment:** I2 — Messaging Semantic Guards

**Target repository path:** `docs/specifications/0.4.1/i2-messaging-semantic-guards.md`

**Governing specification:** `docs/specifications/0.4.1/specification.md`

**Entry baseline:** Published and post-release-verified `v0.4.0`, accepted ADR 0013, and completed
`v0.4.1` I1

**Primary outcome:** A recognized runtime messaging span can create a canonical Queue relation only
after two deterministic, production-reachable decisions establish that its destination is compatible
with AIP's competing-consumer `Queue` model and that its runtime service identity is safe to use.

---

## 1. Purpose

The current runtime messaging pipeline recognizes a narrow set of OpenTelemetry spans and then
resolves both endpoints with unconditional observed-only fallbacks:

```text
recognized messaging.operation.type
        |
        +--> resolve_service(...)
        |        `-- no declared match -> mint OBSERVED_ONLY Service
        |
        `--> resolve_queue(...)
                 `-- no declared match -> mint OBSERVED_ONLY Queue

             -> SENDS / RECEIVES_FROM
```

That fallback is correct only when the available evidence is strong enough to identify both a
service and a competing-consumer queue. It is unsafe for two independently demonstrated shapes:

- a fan-out/topic destination could be represented as a `Queue`; and
- a generic identity such as `service.name: unknown_service` could collapse several runtime roles
  into one invented canonical Service.

Those false facts do not occur in the frozen Quarkus and Airflow runs today because their operation
attribute shapes are outside AIP's current recognition allowlist. Narrow recognition is not a
semantic guard, however. A future recognition change could make both unsafe paths reachable.

I2 SHALL establish this guarantee:

> **AIP emits a runtime `SENDS` or `RECEIVES_FROM` fact only when deterministic evidence supports
> both Queue-compatible destination semantics and a non-ambiguous service identity. Unsupported or
> unresolved evidence is refused before any canonical entity, evidence node, or relation is derived
> from that messaging span.**

I2 is a safety-hardening increment. It SHALL NOT broaden messaging discovery or add a Pub/Sub model.

---

## 2. Normative Language

The key words **MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD
NOT**, and **MAY** are normative.

The governing release specification is:

```text
docs/specifications/0.4.1/specification.md
```

If this I2 specification conflicts with the parent specification, implementation SHALL stop and
resolve the conflict explicitly. It MUST NOT silently select one interpretation.

Executable unit and real-Neo4j integration tests, plus the frozen Quarkus/Airflow evidence, SHALL be
the authoritative implementation evidence when I2 exits.

---

## 3. Governing Decision — Explicit Content

I2 implements the prerequisites recorded by ADR 0013, “No topic/pub-sub family in the Canonical
Model without both safety guards.” The relevant decision is reproduced here so this specification
is self-contained.

### 3.1 Canonical meaning being protected

The current Canonical Model contains `Queue`, `Message`, and the relations `SENDS` and
`RECEIVES_FROM`. `Queue` has competing-consumer semantics. It does not mean “any named messaging
destination.”

The Canonical Model does not contain:

```text
Topic
Subscription
consumer group
fan-out
broadcast
publish/subscribe relation family
```

AIP therefore cannot faithfully represent a topic-shaped observation by relabeling it as a Queue.
Unsupported is more accurate than incorrectly supported.

### 3.2 Two independent prerequisites

ADR 0013 requires both:

1. a topic-versus-Queue guard; and
2. a service-identity guard.

Passing either guard does not compensate for failing the other:

```text
recognized messaging span
        |
        +--> destination semantics ---- refuse / Queue-compatible
        |
        `--> service identity --------- refuse / safe identity
                         |
                         `-- both safe -> resolution may produce a fact
```

### 3.3 The rule survives future recognition changes

The guards SHALL be part of the production runtime-correlation path, not accidental consequences of
the current operation allowlist. Tests SHALL reach each guard with an operation shape that AIP
recognizes today.

I2 itself SHALL keep the operation allowlist frozen. The guards become prerequisites that a later
increment must cite and re-test before widening recognition.

---

## 4. Current Production Baseline

The implementation baseline is `app/telemetry/adapter.py::correlate_queue_observations`:

1. recognize only `messaging.operation.type` values `send`, `receive`, and `process`;
2. require `messaging.destination.name`;
3. require an observation environment;
4. resolve the runtime service;
5. resolve the Queue;
6. record observed-only entities when either resolver mints one;
7. create observed Evidence and a `SENDS` or `RECEIVES_FROM` fact.

`resolve_service` and `resolve_queue` each return an observed-only identity when they cannot select
a declared candidate. Neither can currently return a refusal.

The OTLP decoder already preserves span/resource attributes in `RuntimeSpan`. I2 therefore does not
require an OTLP wire-format or decoder redesign merely to inspect destination-kind evidence.

`UnresolvedObservation` is intentionally diagnostic and contains only `trace_id` plus a short reason
code. It is not persisted to the graph.

---

## 5. Scope

I2 SHALL deliver:

1. one deterministic destination-semantics decision for the runtime messaging path;
2. one deterministic service-identity decision for the runtime messaging path;
3. production wiring that evaluates both decisions before recording any entity or fact for the
   messaging span;
4. explicit refusal outcomes represented through the existing unresolved-observation boundary;
5. unit tests for each decision and their composition;
6. real-Neo4j integration proof that refused spans create no canonical semantic artifacts;
7. frozen Quarkus/Airflow regressions;
8. a completion record with the I2 exit statement and exact candidate identity.

The following are explicitly outside I2:

```text
Topic or Subscription entities
new canonical relations
Kafka or Celery support
messaging operation-attribute widening
legacy destination-name recognition
source-specific adapters
global redesign of Service or Queue identity
HTTP correlation behavior changes
new public API or MCP schemas
new configuration switches that disable either guard
LLM/fuzzy classification
persisted unresolved-observation storage
```

---

## 6. Semantic Boundary and Ordering

The production sequence SHALL be:

```text
operation recognition
        |
        +-- unrecognized -> silently skip (existing behavior)
        |
        v
required destination name
        |
        +-- absent -> no_destination_name
        |
        v
required environment
        |
        +-- absent -> no_environment
        |
        v
pure destination decision
        |
        +-- refused -> one destination reason; stop
        |
        v
pure service-identity decision
        |
        +-- refused -> one service reason; stop
        |
        v
record any accepted observed-only entities
        |
        v
construct Evidence and SENDS / RECEIVES_FROM fact
```

The two guard decisions MUST NOT mutate the graph, append to the output entity collection, or create
Evidence. Resolution may compute deterministic IDs, but those IDs do not become canonical artifacts
until both decisions succeed.

Destination-first ordering is normative because `UnresolvedObservation` currently carries one
reason. If both guards would refuse the same span, the result SHALL contain the destination refusal
reason only. The result MUST still contain no Service, Queue, Evidence, or messaging fact derived
from that span.

This precedence is an output rule, not permission to retain side effects from a partially successful
decision.

---

## 7. Guard Outcome Contract

Each guard SHALL return one of these semantic outcomes:

```text
DECLARED
    one existing canonical candidate was selected deterministically

OBSERVED_ONLY
    no declared candidate applies, but evidence is sufficiently explicit to mint an identity

REFUSED
    evidence is unsupported, unresolved, ambiguous, placeholder-shaped, or conflicting
```

An accepted result SHALL contain the resolved canonical ID and discovery status. A refused result
SHALL contain a stable reason code and SHALL NOT contain a usable canonical ID.

The exact Python representation is an implementation choice. A frozen dataclass plus enum/string
constants is preferred over exceptions or loosely shaped dictionaries. Refusal is an expected
semantic result, not an exceptional program failure.

The guards SHOULD be pure functions whose inputs are flat runtime values, declared candidates, and
configured aliases. They MUST NOT import Neo4j, FastAPI, MCP, or an LLM client.

---

## 8. Destination Evidence Inputs

The destination guard SHALL use only the following inputs in I2:

- `messaging.destination.name`, already required by operation correlation;
- `messaging.system`, when present;
- `messaging.destination_kind`, when present;
- declared Queue candidates fetched through the existing read boundary;
- configured Queue aliases.

Reading `messaging.destination_kind` as safety evidence does not widen operation recognition. It
MUST NOT make a span a messaging candidate by itself and MUST NOT substitute for
`messaging.destination.name`.

I2 SHALL NOT recognize the Airflow/Celery legacy destination key `messaging.destination`. That is a
future operation/destination compatibility decision.

The guard MUST NOT infer Queue compatibility from:

- the destination name;
- substrings or suffixes such as `-q`, `queue`, `topic`, or `events`;
- `messaging.system` alone;
- span name, code namespace, repository name, or upstream project identity;
- a protocol/vendor allowlist or denylist;
- an LLM or fuzzy classifier.

In particular, `messaging.system: kafka` alone is neither positive Queue evidence nor sufficient
generic proof of topic topology. It therefore cannot authorize an observed-only Queue.

---

## 9. Destination-Kind Normalization

When `messaging.destination_kind` is present, the guard SHALL:

1. accept only a string value;
2. strip surrounding ASCII whitespace;
3. compare case-insensitively;
4. classify the normalized exact value `queue` as Queue-compatible;
5. classify `topic`, `subscription`, `pubsub`, `publish-subscribe`, `fanout`, and `broadcast` as
   explicitly outside the current Queue model;
6. treat an empty or any other value as unresolved destination semantics.

This vocabulary distinguishes diagnostics; all non-`queue` outcomes refuse canonical Queue
correlation. The list is not a claim that I2 supports or fully models those destination types.

No substring matching is allowed. For example, `orders-topic` is a destination name and carries no
semantic weight, while kind `topic` is explicit semantic evidence.

---

## 10. Declared Queue Matching

An existing declared Queue is positive Queue-semantic evidence only when its identity match is
deterministic and no explicit destination-kind evidence contradicts it.

Candidate matching SHALL use exact strings and this precedence:

1. if `messaging.system` is present, form the candidates whose namespace equals the system and whose
   name equals the destination name;
2. otherwise, or if tier 1 has no candidate, form the exact-name candidates that do not carry a
   conflicting non-null namespace;
3. accept the selected tier when it contains exactly one distinct candidate ID;
4. after no direct unique match, accept an exact configured alias only when its target ID identifies
   exactly one declared Queue candidate; a valid alias MAY disambiguate multiple direct candidates;
5. otherwise refuse zero matches as unresolved or multiple matches as ambiguous according to §11.

A declared candidate with `namespace=None` carries no namespace assertion and MAY match an observed
destination with a system value. This preserves the current AsyncAPI-to-OTel unification, because
the existing AsyncAPI adapter commonly produces Queues without namespaces.

Two non-null, unequal namespaces conflict. A bare-name fallback MUST NOT merge across that conflict.

An exact system-and-name match takes precedence over an unnamespaced candidate with the same name.
If more than one candidate remains equally eligible at the selected tier, the result is ambiguous.

Aliases are operator-authored disambiguation, not authority to invent a declaration. An alias whose
target is absent from the candidate set SHALL be refused as ambiguous destination identity.

---

## 11. Destination Decision Table

The destination guard SHALL implement this table in order:

| Explicit kind | Declared identity result | Required outcome |
|---|---|---|
| topic/subscription/pubsub/fanout/broadcast | any | `REFUSED` — unsupported semantics |
| unknown, malformed, or empty | any | `REFUSED` — unresolved semantics |
| queue | one deterministic match | `DECLARED` |
| queue | no declared match and no ambiguity/conflict | `OBSERVED_ONLY` |
| queue | ambiguous or namespace-conflicting match | `REFUSED` — ambiguous identity |
| absent | one deterministic match | `DECLARED` |
| absent | no declared match | `REFUSED` — unresolved semantics |
| absent | ambiguous or namespace-conflicting match | `REFUSED` — ambiguous identity |

An explicit non-Queue kind always wins over a declared Queue name. This is the required
conflict-safe behavior: an observation that says “topic” cannot become Queue merely because its name
collides with an existing Queue.

An unmatched destination may become an observed-only Queue only when kind `queue` positively
supplies the missing semantics. A name and system without a declared match are insufficient.

---

## 12. Destination Refusal Reasons

I2 SHALL add and use these stable diagnostic reason strings:

```text
unsupported_destination_semantics
unresolved_destination_semantics
ambiguous_destination_identity
```

They mean:

- `unsupported_destination_semantics`: explicit kind is outside the Queue model;
- `unresolved_destination_semantics`: no positive Queue evidence exists, or kind is malformed or
  unknown;
- `ambiguous_destination_identity`: evidence says Queue, but candidate/alias/namespace identity
  cannot select one safe canonical Queue.

The reason MUST NOT include raw destination names, attributes, or other telemetry payload data.

---

## 13. Service Identity Inputs

The messaging service guard SHALL use only:

- `RuntimeSpan.service_name`;
- `RuntimeSpan.service_namespace`, when present;
- declared Service candidates;
- configured Service aliases.

`service.instance.id` SHALL remain ignored for canonical Service identity. It identifies a runtime
instance, not an architecture Service.

Environment SHALL remain observation/evidence context and SHALL NOT become part of canonical
Service identity. A fact accepted in `staging` must carry `staging`; it must not qualify as observed
in `production`. I2 MUST NOT create environment-suffixed Service IDs to achieve that isolation.

The guard MUST NOT use fuzzy matching, substring matching, topology guesses, span names, destination
names, upstream project identity, or an LLM.

---

## 14. Deterministic Declared Service Matching

Declared Service resolution in the messaging path SHALL use exact strings and this precedence:

1. if a namespace is present, form the candidates with the same namespace and exact name;
2. if tier 1 has no candidate, exact-name candidates with `namespace=None` MAY apply because they
   make no contradictory namespace assertion;
3. if no namespace is present, form all candidates with the exact name;
4. accept the selected tier when it contains exactly one distinct candidate ID;
5. after no direct unique match, accept an exact configured alias only when its target ID identifies
   exactly one declared Service candidate; a valid alias MAY disambiguate multiple direct candidates;
6. otherwise refuse multiple matches as ambiguous and a namespace contradiction as conflicting.

A runtime namespace and a different non-null declared namespace conflict. The messaging path MUST
NOT fall through to a namespace-agnostic name match in that case.

A valid configured alias is an explicit operator decision and MAY disambiguate names, but it MUST
resolve to an existing declared candidate. An alias target that does not exist is refused; it is not
reported as declared and is not minted.

These stricter rules are scoped to messaging correlation. I2 SHALL NOT silently change the shared
`resolve_service` behavior used by HTTP correlation. The implementation MAY reuse safe primitives,
but any global resolver change requires proof that every non-messaging caller preserves its contract.

---

## 15. Explicit Observed-Only Service Predicate

When no declared Service name or valid alias applies, an observed-only Service MAY be minted only if
the runtime name is explicit enough to be a stable architecture identity.

The minimum deterministic predicate is:

1. the value is a string;
2. stripping surrounding whitespace leaves a non-empty value;
3. the existing canonical slug operation produces a non-empty slug;
4. the normalized value is not a reserved placeholder;
5. no declared candidate with the same name carries conflicting identity evidence;
6. minting the ID is deterministic from the existing name/namespace inputs.

For I2, normalization for placeholder detection SHALL strip whitespace, case-fold, replace runs of
spaces and underscores with `-`, and collapse repeated hyphens.

The following normalized identities SHALL be refused:

```text
unknown
unknown-service
unknownservice
```

An SDK-style value beginning with `unknown_service:` or `unknown-service:` SHALL also be refused,
regardless of the executable suffix. This closes the demonstrated generic-default family without
maintaining an application-name denylist.

The reserved set MAY be expanded only with source-independent evidence and matching tests. It MUST
NOT contain real-system product names or known application service names.

Examples such as `FraudService` and `LegacyPricingService` satisfy the predicate when no conflicting
declared identity exists. Being undeclared is not itself a refusal reason.

---

## 16. Ambiguous and Conflicting Service Identity

The following SHALL be refused rather than minted:

- more than one equally eligible declared candidate for the same observed identity;
- a supplied non-null namespace conflicting with a same-name candidate's different non-null
  namespace;
- a configured alias whose target does not identify exactly one declared Service candidate;
- a placeholder identity from §15;
- a blank or non-canonicalizable identity.

When a distinctive name has no same-name declared candidate at all, a supplied namespace is valid
observed-only identity evidence and SHALL be preserved in the deterministic Service ID.

This distinction is normative:

```text
FraudService, namespace=commerce
no declared same-name candidate
    -> explicit OBSERVED_ONLY identity is allowed

FraudService, namespace=warehouse
declared FraudService, namespace=commerce
    -> conflicting identity is refused; no cross-namespace merge or parallel guess
```

---

## 17. Service Refusal Reasons

I2 SHALL add and use these stable diagnostic reason strings:

```text
placeholder_service_identity
ambiguous_service_identity
conflicting_service_identity
```

They mean:

- `placeholder_service_identity`: the name is blank, non-canonicalizable, or in the reserved
  placeholder family;
- `ambiguous_service_identity`: multiple candidates apply or an alias target is absent/ambiguous;
- `conflicting_service_identity`: a same-name declared identity contradicts the supplied namespace.

The reason MUST NOT include the service name, namespace, instance ID, or raw telemetry attributes.

---

## 18. Composition Rule

A messaging fact is eligible only when:

```text
operation is recognized
AND destination name is present
AND environment is present
AND destination decision is DECLARED or OBSERVED_ONLY
AND service decision is DECLARED or OBSERVED_ONLY
```

If eligible, the current mapping remains:

| `messaging.operation.type` | Relation | Correlation mode |
|---|---|---|
| `send` | `SENDS` | `MESSAGING_SEND` |
| `receive` | `RECEIVES_FROM` | `MESSAGING_RECEIVE` |
| `process` | `RECEIVES_FROM` | `MESSAGING_PROCESS` |

Evidence ID construction, day bucketing, timestamps, trace samples, service version, and relation
direction SHALL remain unchanged.

The implementation MUST record observed-only entities only after both guards accept. If one endpoint
would be observed-only and the other guard refuses, neither endpoint is added to the batch.

---

## 19. Meaning of “No Canonical Artifact”

For a refused span, the returned `ObservationBatch` SHALL contain:

```text
entities derived from that messaging span = 0
facts derived from that messaging span = 0
Evidence derived from that messaging span = 0
unresolved entries for that messaging span = 1
```

For an OTLP batch containing other valid HTTP or messaging spans, their independently valid outputs
remain present.

At the persisted graph boundary, a refused span SHALL create or update none of:

- a Service node;
- a Queue node;
- an Evidence node;
- a `SENDS` relation;
- a `RECEIVES_FROM` relation.

The existing telemetry endpoint may still open its normal transaction, ensure schema, and advance
the repository revision for the batch. I2 does not redefine revision-fence semantics. Tests MUST
assert absence of semantic artifacts, not absence of every database transaction.

---

## 20. Existing Validation and Error Precedence

Existing pre-guard outcomes SHALL remain stable:

| Input condition | Result |
|---|---|
| operation type missing or unrecognized | silently skipped; no unresolved entry |
| recognized operation, destination name absent | `no_destination_name` |
| recognized operation and destination, environment absent | `no_environment` |

The new guards run only after these checks. They MUST NOT reclassify an unrecognized operation as an
unresolved topic or service identity.

Within the new guards, the precedence is:

```text
destination semantics/identity refusal
before
service identity refusal
```

This produces exactly one deterministic diagnostic when both fail.

---

## 21. Operation Recognition Freeze

I2 SHALL preserve exactly this recognized input surface:

```text
attribute: messaging.operation.type
values:    send | receive | process
```

The current case-insensitive value comparison MAY remain. I2 SHALL NOT add:

```text
messaging.operation
publish
consume
messaging.destination as a destination-name fallback
destination_kind as an operation signal
span-kind-derived messaging operations
```

The complete Quarkus legacy shape and Airflow/Celery shape SHALL continue to be unrecognized and
silently skipped. Guard reachability is proven separately with currently recognized operation
values.

---

## 22. No Guard Bypass

Every production path that turns a runtime messaging span into `SENDS` or `RECEIVES_FROM` SHALL pass
both decisions.

At the I2 baseline, that path is `correlate_queue_observations` called by `adapt` and ultimately by
`POST /v1/traces`. Tests SHALL cover the direct adapter boundary and the real endpoint/persistence
boundary.

No call site may invoke an unsafe “mint anyway” option. I2 SHALL add no feature flag, settings key,
environment variable, or API parameter that disables either guard.

Direct resolver helpers may continue to exist for other established callers. Their existence is not
a bypass unless a production messaging fact can reach them without the two guard decisions.

---

## 23. Architecture and Dependency Direction

The preferred dependency shape is:

```text
OTLP receiver
    -> RuntimeSpan
        -> messaging adapter/orchestration
            -> pure messaging destination guard
            -> pure messaging service guard
                -> accepted ObservationBatch
                    -> existing aggregator
                        -> Neo4j
```

The guard module MAY reuse candidate and resolution value types from the existing resolvers, but it
SHALL remain independent of database sessions and transport frameworks.

The adapter is responsible for translating a refused guard result into one
`UnresolvedObservation`. The aggregator SHALL remain unaware of destination/service classification;
it persists only already-accepted batches.

I2 SHOULD avoid changing the public signatures of `adapt` and `correlate_queue_observations` because
all required inputs already exist. If a signature change is necessary, every caller and direct test
must migrate in the same slice.

---

## 24. Determinism Requirements

The following SHALL be deterministic under input reordering:

- candidate matching;
- ambiguity detection;
- alias validation;
- placeholder normalization;
- reason selection;
- canonical ID construction;
- output entity deduplication.

Candidate list order MUST NOT select a winner. Repeated rows with the same candidate ID SHALL be
deduplicated before cardinality is evaluated. Candidates with the same semantic identity but
different IDs are ambiguous unless a valid alias explicitly selects one.

No wall clock, random value, network call, database write, or model response may influence a guard
decision.

---

## 25. Destination Unit Matrix

The destination decision SHALL be unit-tested directly against at least this matrix:

| ID | Declared candidates / alias | Runtime evidence | Expected |
|---|---|---|---|
| D1 | exact declared Queue | no kind | declared Queue accepted |
| D2 | exact declared Queue | kind `queue` | declared Queue accepted |
| D3 | exact declared Queue | kind `topic` | unsupported refusal |
| D4 | none | kind `queue` | deterministic observed-only Queue |
| D5 | none | no kind | unresolved refusal |
| D6 | none | unknown/malformed kind | unresolved refusal |
| D7 | duplicate exact candidates | kind `queue` | ambiguous refusal |
| D8 | exact namespaced candidate | same system | declared Queue accepted |
| D9 | same name, different non-null namespace | kind absent | identity refusal; no cross-namespace merge |
| D10 | same name, different non-null namespace | kind `queue` | ambiguous identity refusal; no parallel Queue guess |
| D11 | unnamespaced declared candidate | system present | declared Queue accepted |
| D12 | valid alias to declared candidate | no kind | declared Queue accepted |
| D13 | alias to absent candidate | kind `queue` | ambiguous refusal |
| D14 | name contains `topic`, kind `queue` | no candidate | observed-only Queue accepted; names do not classify semantics |
| D15 | ordinary name, kind `topic` | any system | unsupported refusal |
| D16 | Kafka system, no kind, no declaration | unresolved refusal; system alone is insufficient |
| D17 | shuffled candidate order | same logical input | identical result |

D10 MUST NOT merge to the conflicting declaration or mint a parallel observed-only Queue. The
explicit kind proves Queue semantics but does not resolve the conflicting canonical identity.

---

## 26. Service-Identity Unit Matrix

The messaging service decision SHALL be unit-tested directly against at least this matrix:

| ID | Declared candidates / alias | Runtime identity | Expected |
|---|---|---|---|
| S1 | exact declared Service | exact name, no namespace | declared Service accepted |
| S2 | exact namespaced Service | exact name + namespace | declared Service accepted |
| S3 | unnamespaced declared Service | exact name + runtime namespace | declared Service accepted; declaration is non-conflicting |
| S4 | namespaced declared Service | exact name + different namespace | conflicting refusal |
| S5 | duplicate exact-name candidates | no namespace | ambiguous refusal |
| S6 | valid alias to one declared candidate | alias name | declared Service accepted |
| S7 | alias to absent candidate | alias name | ambiguous refusal |
| S8 | no candidate | `FraudService` | deterministic observed-only Service |
| S9 | no candidate | `LegacyPricingService` | deterministic observed-only Service |
| S10 | no candidate | `unknown_service` | placeholder refusal |
| S11 | no candidate | case/whitespace variants of `unknown_service` | placeholder refusal |
| S12 | no candidate | `unknown_service:python` | placeholder refusal |
| S13 | no candidate | blank or punctuation-only value | placeholder refusal |
| S14 | no candidate | distinctive name + namespace | observed-only ID preserves namespace |
| S15 | shuffled/duplicated candidate order | same logical input | identical result/refusal |
| S16 | two instance IDs, same accepted service identity | otherwise identical | same canonical Service ID |

At least one test SHALL prove that the explicit observed-only case fails if the predicate is
incorrectly changed to “declared services only.”

---

## 27. Composed Adapter Matrix

Tests through `correlate_queue_observations` SHALL cover at least:

| ID | Service | Destination | Operation | Expected |
|---|---|---|---|---|
| C1 | declared | declared Queue | send | one `SENDS`, no unresolved |
| C2 | declared | declared Queue | receive | one `RECEIVES_FROM`, receive mode |
| C3 | declared | declared Queue | process | one `RECEIVES_FROM`, process mode |
| C4 | explicit observed-only | declared Queue | send | Service entity + one `SENDS` |
| C5 | declared | explicit kind `queue`, undeclared destination | send | Queue entity + one `SENDS` |
| C6 | explicit observed-only | explicit kind `queue`, undeclared destination | send | Service + Queue entities + one fact |
| C7 | valid service | explicit kind `topic` | send | no entities/fact; destination refusal |
| C8 | valid service | unresolved destination semantics | send | no entities/fact; destination refusal |
| C9 | placeholder service | declared Queue | send | no entities/fact; service refusal |
| C10 | ambiguous service | declared Queue | send | no entities/fact; service refusal |
| C11 | conflicting namespace | declared Queue | send | no entities/fact; service refusal |
| C12 | placeholder service | explicit kind `topic` | send | no entities/fact; destination reason only |
| C13 | valid namespaced service | declared Queue | send in staging | evidence environment is staging only |
| C14 | missing/unrecognized operation | otherwise guard-failing | none | silent skip; guards do not make it a candidate |
| C15 | missing destination | otherwise valid | send | existing `no_destination_name` |
| C16 | missing environment | otherwise valid | send | existing `no_environment` |
| C17 | one refused + one valid span | mixed batch | only valid span contributes artifacts |

These tests SHALL assert complete `entities`, `facts`, and `unresolved` results, not only fact count.

---

## 28. Existing Tests That Encode the Unsafe Baseline

Several current tests intentionally characterize the pre-I2 gap. I2 SHALL replace or rename their
expectations rather than retaining contradictory assertions:

- the queue-resolver test that proves a topic-shaped unmatched destination is currently minted;
- the service-resolver test that proves `unknown_service` is currently minted;
- the adapter test that allows both an observed-only Service and Queue using names alone;
- ambiguity tests that currently fall through to observed-only minting.

This is an approved semantic correction, not unrelated expected-output churn. Where the underlying
generic resolver remains unchanged for HTTP compatibility, the old direct-resolver characterization
MAY remain, but the new messaging-guard test MUST prove that production messaging cannot reach the
unsafe result.

Tests for existing valid declared Queues and explicit runtime-only Services SHALL continue to pass.

---

## 29. Real-Neo4j Persistence Qualification

Integration tests SHALL exercise the actual OTLP endpoint or the complete
decode/adapt/persist boundary against real Neo4j.

For each refusal family, the test SHALL begin from a known graph, submit the span, and prove that no
new semantic artifacts attributable to that span exist:

```text
topic-shaped destination
unresolved destination
placeholder service
ambiguous service
both guards fail
```

At least one positive control in the same integration suite SHALL prove that a currently recognized,
guard-approved Queue span persists its Service/Queue resolution, Evidence, and relation normally.

The negative assertion SHALL query nodes, Evidence, and `SENDS`/`RECEIVES_FROM`, not rely solely on
the endpoint's successful OTLP response. The endpoint is allowed to accept telemetry even when one
span is semantically unresolved.

Integration fixtures MUST use unique deterministic IDs/names and clean up through the repository's
established test isolation mechanism.

---

## 30. Frozen Quarkus Regression

I2 SHALL retain the exact independently captured Quarkus/SmallRye shape:

```text
messaging.operation: publish
messaging.destination.name: fights
messaging.system: kafka
```

Because operation recognition is frozen, the exact span SHALL remain silently unrecognized:

```text
Topic nodes = 0
Queue node for fights = 0
SENDS / RECEIVES_FROM derived from fights = 0
```

That regression alone does not prove the new guard. A second synthetic reachability test SHALL use a
currently recognized `messaging.operation.type` with otherwise topic/unresolved destination
evidence and prove that the destination guard refuses it.

The synthetic test MUST NOT assert that the string `kafka` alone means topic. It SHALL either supply
explicit non-Queue destination-kind evidence or prove that the captured missing-kind shape remains
unresolved rather than guessed.

I2 does not claim Kafka support and does not require a live Quarkus rerun.

---

## 31. Frozen Airflow Regression

I2 SHALL retain the exact independently captured Airflow/Celery shape:

```text
service.name: unknown_service
messaging.destination_kind: queue
messaging.destination: default
no recognized messaging operation
no messaging.system
```

Because operation and destination-name recognition are frozen, the exact span SHALL remain silently
unrecognized and produce no messaging fact.

That regression alone does not prove the service guard. A second synthetic reachability test SHALL
combine:

```text
service.name: unknown_service
messaging.operation.type: send (or receive/process)
messaging.destination.name: a declared Queue
```

and prove:

```text
Service minted for unknown_service = 0
messaging facts from the span = 0
reason = placeholder_service_identity
```

The predicate is generic and MUST NOT inspect the word `Airflow`, a role name, or a fixture path.

I2 does not claim Celery support and does not require a live Airflow rerun.

---

## 32. Environment and Qualification Regression

I2 SHALL preserve I1's shared declared-versus-observed qualification semantics.

For accepted messaging evidence:

- the observation environment is copied unchanged into the Evidence and fact candidate;
- evidence observed in one environment does not count as observed in another;
- the existing inclusive observation-window behavior remains unchanged;
- coverage classification remains governed by the I1 kernel.

For refused messaging evidence, there is no Evidence to qualify.

At least one integration test SHALL submit an accepted span in one environment and verify that the
runtime analysis/Architecture Intelligence behavior does not treat it as observed in another. This
may reuse an existing test if it exercises the post-I2 production path.

I2 MUST NOT change canonical Service IDs merely to encode environment isolation.

---

## 33. Mixed HTTP and Messaging Behavior

`adapt` combines HTTP and messaging batches. I2 SHALL prove:

1. a refused messaging span does not suppress valid HTTP facts from the same OTLP batch;
2. a valid messaging span still combines with valid HTTP facts;
3. observed-only entity deduplication remains deterministic when both accepted paths identify the
   same Service;
4. the messaging placeholder rule does not change HTTP service resolution by accident.

A service name refused for messaging MAY continue to behave according to the pre-existing HTTP
resolver contract when present on an HTTP span. I2 does not claim that the same evidence is equally
sufficient for every relation family; the messaging guard exists because messaging correlation can
otherwise invent both endpoints from one span.

---

## 34. Security and Privacy

The guards SHALL fail closed and operate entirely in deterministic application code.

They MUST NOT:

- call an external service;
- expose raw span attributes in reason strings;
- persist refused telemetry as canonical graph data;
- allow configuration to disable refusal;
- use user-controlled strings in Cypher labels or relation types;
- log full telemetry payloads as part of ordinary guard diagnostics.

Existing OTLP transport authentication/deployment assumptions are unchanged by I2.

---

## 35. Public Contract Compatibility

I2 SHALL make no change to:

- the Canonical Model or graph schema;
- public REST response schemas;
- `ArchitectureAnswer<T>` or its `schema_version="0.4"` value;
- the exactly three read-only MCP tools;
- claim IDs, destination resolution in Architecture Intelligence, or qualification vocabulary;
- snapshot identity/revision semantics;
- configuration-file compatibility.

`UnresolvedObservation` remains internal to telemetry adaptation. The new reason strings are not a
new public API response contract.

Normal producer metadata may identify version `0.4.1`; that is not a schema-version change.

---

## 36. Delivery Slices

I2 SHOULD ship as three reviewable increments, each in its own PR.

### I2.1 — Pure Guard Decisions

Deliver:

- destination and service decision types/functions;
- reason constants;
- destination-kind and placeholder normalization;
- direct unit matrices D1–D17 and S1–S16;
- no production caller behavior change.

The code is deliberately unused until I2.2 so semantic review can occur independently of
orchestration edits.

Gate:

```text
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit
```

### I2.2 — Atomic Production Wiring

Wire both guards into `correlate_queue_observations` in one behavioral slice. Deliver:

- destination-first decision ordering;
- delayed entity/evidence/fact recording until both decisions accept;
- composed adapter matrix C1–C17;
- updates to tests that intentionally pinned the unsafe baseline;
- mixed HTTP/messaging regression;
- real-Neo4j positive and refusal persistence tests.

Neither guard SHALL be wired alone as the completed production safety boundary. Both are required
before I2.2 exits.

Gate:

```text
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit
uv run pytest tests/integration
```

### I2.3 — Frozen Qualification and Completion

Deliver:

- exact Quarkus and Airflow frozen-shape regressions;
- synthetic guard-reachability counterparts;
- existing Architecture Answers/evaluation regression;
- ADR 0013 implementation note without superseding the ADR;
- I2 completion record with exact commit/check identity and exit statement.

Gate:

```text
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit
uv run pytest tests/integration
```

Any additional repository-standard evaluation/security checks required before a PR remain required;
the commands above are the minimum semantic gates, not a replacement for CI.

---

## 37. Expected File Surface

The implementation is expected to affect a narrow surface equivalent to:

```text
app/telemetry/<messaging guard module>.py
app/telemetry/adapter.py
app/telemetry/semconv/messaging.py
tests/unit/test_<messaging guard module>.py
tests/unit/test_adapter.py
tests/integration/test_adapter.py and/or test_runtime_api.py
docs/adr/0013-no-topic-family-without-guards.md
docs/specifications/0.4.1/i2-completion-record.md
```

Existing service/queue resolver modules and their tests MAY change only if the implementation can
preserve non-messaging behavior and make the guard boundary clearer. A broad resolver redesign is
not part of I2.

Changes to `app/canonical`, `app/mcp`, public schemas, Architecture Intelligence contracts, or graph
schema require scope re-review before implementation proceeds.

---

## 38. Review Invariants

Every I2 review SHALL verify:

```text
[ ] both guards are reached by the production messaging path
[ ] neither guard is merely a test-only helper
[ ] entities are recorded only after both guards accept
[ ] declared Queue matching cannot override explicit topic semantics
[ ] name/system strings alone cannot authorize a new Queue
[ ] explicit kind=queue can authorize an otherwise safe observed-only Queue
[ ] unknown_service and its SDK-style family are refused for messaging
[ ] a distinctive undeclared service remains allowed
[ ] candidate ordering cannot choose a winner
[ ] invalid aliases cannot claim DECLARED status
[ ] namespace conflicts do not cross-merge
[ ] environment remains evidence context, not canonical Service identity
[ ] operation recognition remains exactly frozen
[ ] HTTP correlation behavior is not unintentionally hardened
[ ] no Topic/Subscription/model family is introduced
[ ] no guard-disabling configuration exists
[ ] no public REST/MCP schema changes
```

---

## 39. Failure Handling During Implementation

If implementation reveals a current supported Queue scenario that lacks both a deterministic
declared Queue match and explicit `queue` kind evidence, it SHALL NOT be grandfathered automatically.
The team SHALL determine whether independent evidence establishes Queue semantics.

The allowed dispositions are:

1. add source-independent positive semantic evidence to the fixture/input;
2. document that the old scenario was an unsafe guess and change its expectation;
3. revise this specification through explicit review if a general safe rule is evidenced.

It is forbidden to add a destination-name or vendor special case merely to preserve a test.

If direct use of `messaging.destination_kind` proves technically unavailable despite the decoder's
attribute preservation, implementation SHALL stop and record the concrete evidence. It MUST NOT
silently weaken the guard to `messaging.system` or destination-name heuristics.

If a global resolver change alters HTTP behavior, that change SHALL be separated or reverted unless
the I2 review explicitly widens scope with corresponding regressions.

---

## 40. Documentation Requirements

I2.3 SHALL update ADR 0013 with an implementation record naming:

- both production guard entry points;
- the exact merged candidate/PR identities;
- the guard-level and persistence-level regression tests;
- the unchanged operation-recognition boundary;
- the continued absence of Topic/Subscription support.

ADR 0013 SHALL remain `Accepted`. It is satisfied, not superseded, by I2. A future Pub/Sub ADR may
supersede its prohibition only after citing the completed guard evidence.

The I2 completion record SHALL document:

- the exact placeholder vocabulary and normalization shipped;
- the exact destination-kind vocabulary shipped;
- the namespace-conflict behavior shipped for both guards;
- all intentional changes to unsafe pre-I2 tests;
- Quarkus/Airflow exact-shape and synthetic-reachability results;
- unit/integration counts and immutable CI identity;
- release blockers and deferred work.

No frozen `v0.3` validation dossier or ground truth SHALL be rewritten. Those records remain the
historical evidence that motivated I2.

---

## 41. Definition of Done

### Destination safety

```text
[ ] one deterministic destination decision exists
[ ] decision is in the production runtime messaging path
[ ] declared Queue is accepted when identity is deterministic and semantics do not conflict
[ ] explicit queue kind can support a safe observed-only Queue
[ ] topic/pubsub/fanout/broadcast kinds are refused
[ ] absent/unknown kind cannot mint an unmatched Queue
[ ] destination name and messaging system alone cannot qualify Queue semantics
[ ] ambiguous candidates and invalid aliases are refused
[ ] namespace conflicts never cross-merge
```

### Service-identity safety

```text
[ ] one deterministic messaging service decision exists
[ ] decision is in the production runtime messaging path
[ ] deterministic declared Service matches remain valid
[ ] distinctive undeclared Services remain OBSERVED_ONLY-capable
[ ] unknown_service placeholder family is refused
[ ] ambiguous candidates and invalid aliases are refused
[ ] conflicting namespaces never cross-merge
[ ] environment remains observation context
[ ] HTTP resolver behavior remains unchanged unless explicitly re-reviewed
```

### Composed safety

```text
[ ] both guards accept before any entity/evidence/fact is recorded
[ ] either refusal yields zero semantic artifacts from that span
[ ] both-fail precedence is deterministic
[ ] positive SENDS/RECEIVES_FROM behavior remains valid
[ ] mixed batches preserve unrelated valid observations
[ ] real-Neo4j tests prove refused artifacts are absent
```

### Scope preservation

```text
[ ] operation recognition is not widened
[ ] exact Quarkus legacy span remains unsupported/zero-fact
[ ] exact Airflow/Celery span remains unsupported/zero-fact
[ ] synthetic counterparts prove both guards are independently reachable
[ ] no Topic or Subscription entity exists
[ ] no new relation family exists
[ ] no new public REST/MCP contract exists
[ ] exactly three read-only MCP tools remain
[ ] I1 qualification semantics remain intact
```

### Completion evidence

```text
[ ] all unit tests pass
[ ] all integration tests pass
[ ] existing Architecture Answers evaluation passes
[ ] lint/format/CI/security gates pass
[ ] ADR 0013 has an implementation record
[ ] I2 completion record binds results to the exact candidate
[ ] release blockers = 0
```

---

## 42. I2 Exit Statement

The canonical I2 exit statement SHALL have this form:

```text
GO — At <commit>, AIP's production runtime messaging path requires both deterministic
Queue-compatible destination semantics and safe service identity before deriving a canonical
SENDS/RECEIVES_FROM observation. Topic-shaped, unresolved, conflicting, ambiguous, and placeholder
inputs produce zero Service/Queue/Evidence/relation artifacts from the refused span, while declared
Queues and explicit unambiguous runtime-only Services preserve valid OBSERVED_ONLY behavior. The
frozen Quarkus Kafka and Airflow/Celery shapes remain unsupported with zero invented messaging facts;
operation recognition, the Canonical Model, public v0.4 schemas, and the exactly three read-only MCP
tools remain unchanged. I2 release blockers = 0.
```

If that statement cannot be supported by executable evidence, I2 is `NO-GO`.

---

## 43. Handoff to I3

I2 makes ADR 0013's two safety prerequisites executable. It does not introduce the Pub/Sub family
that those prerequisites protect.

The handoff is:

```text
I1
qualification consistency

        +

I2
messaging destination guard
+ messaging service guard

        |
        v

I3
full v0.4.1 hardening qualification
+ reproducible read-cost benchmark
+ release qualification and publication
```

I3 SHALL re-run the I2 semantic regressions against the exact release candidate. It SHALL NOT widen
operation recognition, introduce Topic/Subscription, or reinterpret a guard refusal as release
failure merely because the destination remains unsupported.

Generic Pub/Sub modeling and broader messaging recognition remain `v0.5.0` work governed by a new
ADR that cites the completed I2 evidence.
