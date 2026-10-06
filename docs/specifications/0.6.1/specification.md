# AIP v0.6.1 — Broker Semantic Completion

**Status:** Draft — for owner review  
**Target:** `v0.6.1`  
**Baseline:** Published and post-release-verified `v0.6.0`  
**Scope authority:** [ROADMAP.md — v0.6.1](../../../ROADMAP.md)

## 1. Promise and product question

> **Which messaging infrastructure does this service use, and how far can the available evidence safely resolve that relationship?**

v0.6.1 is a lightweight semantic completion of the messaging capability already shipped in v0.5/v0.6. It makes **Broker** identity and service-to-broker use first-class Architecture Knowledge when the source evidence is strong enough.

The concrete developer question is:

> **"Before changing this service's messaging integration, which broker is it evidenced to use, and what can I safely infer — or not infer — about queues, topics, subscriptions and messages?"**

The release does **not** add a new architecture-question class. It fills the broker-level gap underneath the existing messaging/dependency question.

## 2. Constraints

- This is a **patch release** under the ROADMAP's semantic-completion rule. It must not widen into a new Current-State capability.
- Add exactly one canonical entity kind, `Broker`, and one typed relation, `USES_BROKER` (`Service -> Broker`).
- `USES_BROKER` is **not** `SENDS`, `PUBLISHES_TO`, `RECEIVES_FROM`, `SUBSCRIPTION_OF` or a generic dependency edge. A Broker claim never creates or implies a Queue, Topic, Subscription, Message, producer or consumer claim.
- Do **not** add a generic `CONNECTED_TO` relation.
- Do **not** add a live broker adapter or broker discovery against Kafka, Redis, Azure Service Bus, Google Pub/Sub, RabbitMQ or another broker.
- Do **not** add a CALM adapter. FINOS FluxNova/CALM is qualification evidence, not a new source family.
- Keep exactly the existing four MCP tools. No fifth Broker tool.
- Runtime telemetry does not mint a Broker or `USES_BROKER` in this release. Existing OTel messaging evidence continues to qualify the already-supported Queue/Topic/Subscription relations only.
- Existing v0.6.0 locality semantics, scoped-evidence semantics and C1/C2 rules remain unchanged.
- Existing unsupported or unresolved messaging cases remain unsupported or unresolved unless Broker evidence alone answers the narrower Broker question.
- **No increment specs.** Each increment is implemented against its section in this document, with the reviewed implementation plan retained in the PR description, as in v0.5.1.

## 3. Evidence basis

The semantic boundary is already visible in three independent systems.

### Quarkus Super Heroes — positive explicit Broker identity

The existing v0.5.1 demo overlays
[`rest-fights/asyncapi.yaml`](../../../examples/quarkus-super-heroes-demo/overlay/rest-fights/asyncapi.yaml)
and
[`event-statistics/asyncapi.yaml`](../../../examples/quarkus-super-heroes-demo/overlay/event-statistics/asyncapi.yaml)
both declare `x-aip-broker-id: kafka:fights-kafka`. Those files remain the frozen qualification input unless deliberately re-pinned.

That is sufficient evidence that both Services use the same Broker. It is **not** sufficient to invent a Subscription when the existing Subscription identity rules do not resolve one.

### FINOS FluxNova / CALM — positive Broker-only connectivity

Freeze the existing FINOS FluxNova fixture at commit
`c8c2811d28e10c12d0bf96be9434398585bb7d0e`.

Its authored CALM model contains:

- `ms-payment-worker -> ms-message-broker` over AMQP, relationship `ms-payment-worker-to-broker`;
- `ms-notification-worker -> ms-message-broker` over AMQP, relationship `ms-notification-worker-to-broker`.

The fixture identifies a broker-level connection but does not identify a Queue, Topic, Subscription or Message. That is the exact positive case this release must preserve: **Broker use is answerable while richer messaging topology is not.**

Qualification uses a small, disclosed transcription package prepared from the pinned fixture:

1. two identity-only OpenAPI declarations, with explicit `x-aip-service-id`, `paths: {}`, and no invented Operations, establish the existing phase-0 Service identities for Payment Worker and Notification Worker;
2. one Architecture Manifest transcription carries only their two Broker uses;
3. the stable broker id is derived from the source-native CALM identity, not its display name:
   `calm:finos-fluxnova:ms-message-broker`;
4. a companion `PROVENANCE.md` records the pinned CALM commit, fixture path, broker node id and the two relationship ids. Those CALM ids are qualification provenance; they are not added as new canonical Evidence fields.

The exact transcription commit is recorded later in the I3 qualification record. It must already exist before the first AIP qualification run and that run must execute from, or from a descendant of, that frozen transcription commit.

All transcription files are operator-authored qualification inputs, not upstream CALM files and not a general CALM adapter.

### Apache Airflow — negative attribution boundary

The frozen Airflow 3.3.1 dossier establishes `CeleryExecutor`, a Redis broker URL and the `default` task queue at configuration level. It also establishes that scheduler/worker/task-runner process roles have no admitted Service identity.

The qualification includes an explicit negative manifest input that names a stable Redis Broker id but attempts to attribute it to an unadmitted worker Service identity. Because no phase-0 source declares that Service, the manifest must be rejected and emit **zero** Broker/`USES_BROKER` artifacts.

Therefore v0.6.1 must **not** attribute Redis broker use to `service:airflow-apiserver`, accept the attempted worker identity, or mint a Service merely to produce a Broker claim. The existing Queue/Topic/Subscription negatives remain unchanged.

## 4. I1 — Canonical Broker and declared ingestion

### 4.1 Canonical semantics

Add:

```text
Broker
Service -[USES_BROKER]-> Broker
```

`Broker` is an infrastructure endpoint for messaging use. It is not a Service and not a message destination.

A Broker's canonical id is derived only from an explicit stable broker identity:

```text
broker_owner_key = length-delimited(stable broker id)
broker_id        = broker:owned:<sha256(broker_owner_key)>
```

The stable broker id is the same semantic input already used by the existing Queue/Topic/Subscription owner-scoped identities.

**Namespace is not Broker identity.** Two AMQP virtual hosts/namespaces under the same stable broker id resolve to the same Broker; namespace continues to distinguish the existing destination identities where their rules require it.

The following never establish Broker identity by themselves:

```text
server name
URL / hostname / port
protocol or vendor
TLS identity
messaging.system
namespace / virtualHost
Queue / Topic / Subscription name
display-name equality
```

A configured Topic/Queue/Subscription mapping that yields only the destination's canonical id, with no stable broker id, does **not** imply a Broker.

Conflicting or ambiguous identities for one broker reference remain unresolved. Do not choose one by precedence. This rule does not prohibit a Service from legitimately using multiple independently evidenced Brokers.

### 4.2 AsyncAPI

Reuse the broker-identity path that actually ships today:

- explicit `x-aip-broker-id` on the selected server.

`destinationBrokerMappings` remains the existing reserved, empty mapping-context category in v0.6.1. This release does **not** introduce a configured broker/server identity mapping surface.

An accepted messaging declaration may emit one Broker and one deduplicated `USES_BROKER` relation for each resolved Service/Broker pair when an admitted channel operation uses that server.

A bare server declaration with no admitted channel operation does not create `USES_BROKER`.

If selected servers disagree on broker identity, or only a subset carries the required identity so the existing server selection is ambiguous, emit **no Broker and no `USES_BROKER` for that construct**. Do not let a Queue/Topic mapping paper over that ambiguity.

The existing Queue/Topic/Subscription mapping remains independent. In particular:

- resolving a Broker does not resolve a destination kind;
- a Topic without Subscription identity remains a Topic-only result;
- once the channel has resolved to a Queue or Topic, an unresolved richer layer (a Subscription or consumer identity) does not remove a Broker claim whose Broker and Service identities are independently established. A channel that never resolved to a Queue or Topic is not admitted and yields no Broker claim;
- a destination resolved only by `queueMappings`/`topicMappings`/`subscriptionMappings`, without stable broker identity, produces no Broker claim.

Existing Queue/Topic/Subscription mappings remain destination mappings only. They do not establish Broker identity, and `destinationBrokerMappings` stays empty/unimplemented in v0.6.1. Existing inputs without explicit `x-aip-broker-id` or an explicit Architecture Manifest `brokers[].brokerId` remain Broker-free.

### 4.3 Architecture Manifest

Extend the existing minimal `architecture.yaml` format with an optional explicit Broker-use block:

```yaml
service: <service identity input>
x-aip-service-id: service:example
brokers:
  - brokerId: kafka:cluster-a
```

The manifest continues to mint no Service. If `brokers` is non-empty, its Service must resolve to a Service already declared by a phase-0 source, exactly as for `calls`. Failure rejects the **whole manifest document** with the existing `MANIFEST_CALL_SOURCE_UNRESOLVED` diagnostic (the manifest's own Service source is unresolved; the frozen v0.5 import-report code vocabulary is not widened): its `calls` and `brokers` contributions are both discarded, and it emits zero canonical artifacts.

`brokerId` is an explicit stable broker id. It is not inferred from a host, protocol or display name.

This block exists for independently authored coarse architecture evidence. For FluxNova qualification, the technical phase-0 Service declarations and Broker transcription are disclosed harness inputs (§3). The source-native CALM ids are recorded in the companion `PROVENANCE.md`; the frozen transcription commit is recorded in the I3 qualification record before the first AIP run.

### 4.4 Evidence, reconciliation and graph

- `Broker` and `USES_BROKER` carry normal declared evidence and source provenance.
- Re-import and deletion follow the existing source inventory/reconciliation rules.
- Equal canonical Broker ids reconcile; different ids never merge by name, protocol or endpoint.
- Multiple different Broker ids for one Service are valid when each is independently evidenced: emit multiple `USES_BROKER` facts. A conflict exists only when one source construct gives incompatible explicit identities for the same broker reference.
- Add only the graph triple `Service -[USES_BROKER]-> Broker`.
- Do not add Broker-to-Queue/Topic/Subscription graph relations in v0.6.1. Destination identities already carry their broker identity inputs internally; this release does not materialize ownership topology merely because Broker is now first-class.

## 5. I2 — Architecture Intelligence surface

Expose Broker knowledge through the existing `ArchitectureIntelligenceService` rather than adding a new tool.

### 5.1 Broker claim

Add a `BrokerClaim` alongside the existing dependency and deployment claims:

```text
subject   = Service
predicate = USES_BROKER
object    = Broker
evidence_refs = non-empty, sorted, deduplicated
```

A Broker claim is **not** a `DependencyClaim`:

- no `DeliveryKind`;
- no `CALLS`/`SENDS`/`PUBLISHES_TO` relation type;
- no `CONFIRMED`/`OBSERVED_ONLY`/`NOT_OBSERVED_IN_WINDOW` runtime qualification;
- no coverage or destination-resolution fields.

`BrokerClaim.object` is a bounded `BrokerRef` (`id` = the canonical Broker id, `type` = `BROKER`, `name` = the explicit stable broker id the source declared); it is deliberately not an `EntityRef`, so the released v0.5 entity-type set is not widened.

**Claim identity.** `claim_id = aip:claim:v1:<sha256(canonical-json({"predicate": "USES_BROKER", "service_id": <canonical Service id>, "broker_id": <canonical Broker id>}))>`, using the same canonical-JSON and `aip:claim:v1` prefix rules as every other claim id. Evidence ids, the snapshot id and display names are excluded, so the identity follows the Service/Broker pair and not the evidence that currently supports it (the dependency-claim rule). The predicate is a hashed field so a Broker claim id never collides with another claim kind's.

**Evidence.** A BrokerClaim's `evidence_refs` are the union of the evidence ids of every `USES_BROKER` relation for the pair, kept to those that resolve in the snapshot (membership of each specific id, not mere presence). A Broker with no resolvable evidence yields no claim and one `INSUFFICIENT_EVIDENCE` limitation, the same rule a dependency with no usable evidence follows. Every ref on a BrokerClaim resolves through `get_evidence` at the same snapshot to a v0.6 record whose `supports` contain exactly that `(USES_BROKER, Service, Broker)` fact.

**Ordering and refusals.** Claims keep the existing cross-type order `(object.id, predicate, delivery.kind, delivery.via.id, claim_id)`, with an empty delivery part for a BrokerClaim. A refusal (`NOT_ANSWERED`) is always the v0.5 shape.

In the Broker-aware v0.6 answer, `ServiceDependenciesData` gains `broker_claim_ids` as a sibling of `dependency_claim_ids` and `deployment_claim_ids`.

### 5.2 REST, MCP, evidence and schema versioning

- `get_service_dependencies` and its REST equivalent return Broker claims for the requested Service.
- `get_evidence` can resolve `USES_BROKER` evidence and exposes `BROKER` as an entity type: a Broker-aware supported fact carries a `broker` object (`BrokerRef`).
- The REST-only deployments view (`GET /api/services/{id}/deployments`) is derived from the dependency answer of either version, carries no Broker information, and keeps `schema_version = "0.5"`; the dependency envelope's `"0.6"` is not propagated into it.
- `get_architecture_drift` is unchanged; Broker use has no runtime drift classification in this release.
- `get_service_dependencies_by_locality` is unchanged; Broker use is not locality-qualified in v0.6.1.
- MCP still advertises exactly four tools in the existing deterministic order.

The released v0.5 dependency/evidence schemas are immutable. Publish:

```text
schemas/architecture_intelligence/v0.6/architecture-answer.schema.json
schemas/architecture_intelligence/v0.6/evidence-answer.schema.json
```

alongside the existing v0.6 locality schemas. Do not create a `v0.6.1` schema directory.

Compatibility is explicit and deterministic:

- A `get_service_dependencies` answer with **no BrokerClaim** retains the legacy v0.5 answer shape and `schema_version = "0.5"`; no empty `broker_claim_ids` field is added.
- An answer containing one or more BrokerClaims uses the v0.6 dependency schema and `schema_version = "0.6"`.
- A `get_evidence` answer that resolves no Broker/`USES_BROKER` support retains the v0.5 evidence shape/version. A Broker-aware evidence answer uses the v0.6 evidence schema/version.
- `get_architecture_drift` remains v0.5. The locality tool keeps its existing locality-specific v0.6 contract.
- The MCP-advertised output schema for dependencies/evidence is a `oneOf` discriminated by `schema_version`, accepting the unchanged v0.5 branch and the new v0.6 branch. An existing client validating a Broker-free response against the frozen v0.5 schema therefore continues to succeed.
- Tests must prove both branches and prohibit a v0.5-labelled response from carrying Broker fields/entities/relations.

Producer package version and public schema version remain separate concepts.

Release notes must state the data-dependent contract transition explicitly: after a Service gains its first qualified Broker claim, its dependency answer changes from the v0.5 branch to the v0.6 branch. This is deterministic behavior, not an opt-in compatibility mode.

### 5.3 Snapshot and compatibility

Broker entities and `USES_BROKER` participate in the canonical snapshot when present.

With identical inputs/configuration that contain neither explicit AsyncAPI `x-aip-broker-id` nor Architecture Manifest `brokers[].brokerId`, the canonical Broker entity/relation set remains empty. `destinationBrokerMappings` remains empty/unimplemented and therefore cannot change Broker output or snapshot identity in v0.6.1.

Do not require full serialized answer byte identity across product releases: `producer.version` and build revision legitimately change. The compatibility requirement is that Broker-free answers remain valid against the frozen v0.5 public schemas and preserve their existing semantic claims.

Broker-containing golden fixtures may be deliberately re-pinned with evidence showing exactly why they changed.

## 6. I3 — Qualification and lightweight release

### 6.1 Deterministic semantic qualification

Extend the existing Azure Service Bus, Google Pub/Sub and Kafka broker-semantic fixtures to assert:

- the expected Broker entity;
- the expected Service -> Broker `USES_BROKER` facts;
- no additional Queue/Topic/Subscription/Message semantics beyond what each fixture already establishes;
- deterministic evidence refs and byte-identical repeated semantic output.

Add negative cases for:

- missing broker identity;
- conflicting explicit broker identities for one selected-server construct;
- ambiguous multi-server selection;
- destination mapping with no stable broker identity;
- unresolved manifest Service identity;
- two independently evidenced Brokers for one Service, which is **valid** and must not be collapsed into a false conflict.

### 6.2 Cross-system qualification

Run the bounded Broker question against the three frozen references:

| System | Expected Broker result | Richer messaging result |
|---|---|---|
| Quarkus Super Heroes | `rest-fights` and `event-statistics` use the same `kafka:fights-kafka` Broker from the frozen overlay files (§3) | Preserve the existing Topic/Subscription resolution limits |
| FINOS FluxNova/CALM | The disclosed transcription produces Payment Worker and Notification Worker -> `calm:finos-fluxnova:ms-message-broker` | No Queue, Topic, Subscription, Message or HTTP operation invented from CALM `connects` |
| Apache Airflow 3.3.1 | The explicit negative Redis-Broker manifest is rejected because its worker Service identity has no phase-0 declaration; zero Broker/`USES_BROKER` artifacts | Existing messaging negatives remain unchanged; no attribution to `service:airflow-apiserver` |

The comparison is against frozen source evidence and independently authored expectations, not AIP-generated expectations. The Airflow row is a real-system confirmation of the same unresolved-manifest-Service guard exercised deterministically in §6.1, not a separate semantic rule.

### 6.3 Developer-facing demonstration

Update the existing Quarkus task-led demo/question ladder with one additional question:

> **Which broker does `rest-fights` use, and what does that tell me about the messaging topology?**

The real-transport smoke test must assert both sides of the answer:

1. exactly one Broker claim for `rest-fights`, backed by the overlay's `kafka:fights-kafka` evidence;
2. the existing `PUBLISHES_TO Topic:fights` path still does **not** resolve a Subscription/consumer: the answer remains `PARTIAL` with the existing `UNRESOLVED_IDENTITY` limitation and no invented Subscription claim/entity.

No separate demo stack is added.

### 6.4 Release path

Use the same lightweight release pattern as v0.5.1:

1. one release-prep PR containing the completed v0.6.1 change, version bump, release notes and required golden re-pins;
2. exact merged SHA becomes the release candidate;
3. require green exact-SHA CI/CodeQL and the full repository gate;
4. run the targeted Broker qualification, the existing v0.6 release golden path and the updated Quarkus demo against a clean candidate image;
5. review HIGH/CRITICAL security findings and obtain the owner's explicit GO;
6. publish `v0.6.1` directly — no RC tag unless qualification actually finds a reason to prepare a new candidate;
7. anonymously pull and verify the published immutable image, rerun the release golden path, and record the result in one `v0.6.1-release-record.md`.

Do not reproduce the multi-record v0.6.0 I6 ceremony for this patch release unless a real release blocker requires a new candidate/disposition trail.

## 7. Done

A developer asks which messaging infrastructure a Service uses.

For `rest-fights`, AIP can answer that the Service uses the evidenced Kafka Broker and show why, without upgrading that fact into a resolved consumer or Subscription.

For the frozen FluxNova case, AIP can preserve useful Broker-level connectivity even though the source does not identify a Queue, Topic or Subscription.

For Airflow, an explicit attempted Redis-Broker attribution to the unresolved worker role is rejected rather than silently attached to the API Service or promoted into a new Service identity.

The result is deterministic, evidence-backed and available through the existing Architecture Intelligence surfaces. Broker-free answers remain valid against the frozen v0.5 public schemas; Broker-aware dependency/evidence answers use the explicit v0.6 contract. The four-tool MCP contract remains intact, no live broker discovery is introduced, and no generic connectivity relation has been added.
