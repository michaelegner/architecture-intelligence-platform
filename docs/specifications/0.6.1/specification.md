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
- **No increment specs.** Each increment is implemented against its section in this document, with the implementation plan retained in the PR description.

## 3. Evidence basis

The semantic boundary is already visible in three independent systems.

### Quarkus Super Heroes — positive explicit Broker identity

The v0.5.1 demo overlay declares Kafka `fights` through AsyncAPI and uses the same explicit
`x-aip-broker-id: kafka:fights-kafka` for `rest-fights` and `event-statistics`.

That is sufficient evidence that both Services use the same Broker. It is **not** sufficient to invent a Subscription when the existing Subscription identity rules do not resolve one.

### FINOS FluxNova / CALM — positive Broker-only connectivity

Freeze the existing FINOS FluxNova fixture at commit
`c8c2811d28e10c12d0bf96be9434398585bb7d0e`.

Its authored CALM model contains:

- `Payment Worker -> Message Broker` over AMQP;
- `Notification Worker -> Message Broker` over AMQP.

The fixture identifies a broker-level connection but does not identify a Queue, Topic, Subscription or Message. That is the exact positive case this release must preserve: **Broker use is answerable while richer messaging topology is not.**

Qualification may use a small, disclosed Architecture Manifest transcription of only those two frozen broker links. The transcription must be prepared from the pinned fixture before the AIP run and retain the CALM node/relationship ids in provenance. It is not a general CALM adapter.

### Apache Airflow — negative attribution boundary

The frozen Airflow 3.3.1 dossier establishes `CeleryExecutor`, a Redis broker URL and the `default` task queue at configuration level. It also establishes that scheduler/worker/task-runner process roles have no admitted Service identity.

Therefore v0.6.1 must **not** attribute Redis broker use to `service:airflow-apiserver` or mint a Service for an unresolved process role merely to produce a Broker claim. The existing Queue/Topic/Subscription negatives remain unchanged.

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

The following never establish Broker identity by themselves:

```text
server name
URL / hostname / port
protocol or vendor
TLS identity
messaging.system
Queue / Topic / Subscription name
display-name equality
```

Conflicting or ambiguous broker identities remain unresolved. Do not choose one by precedence.

### 4.2 AsyncAPI

Reuse the existing broker-identity rule:

- explicit `x-aip-broker-id` on the selected server; or
- the existing versioned configured server/broker identity mapping.

An accepted messaging declaration may emit one Broker and one deduplicated `USES_BROKER` relation for its resolved Service/Broker pair when the declaration actually uses that selected server.

A bare server declaration with no admitted messaging declaration does not create `USES_BROKER`.

The existing Queue/Topic/Subscription mapping remains independent. In particular:

- resolving a Broker does not resolve a destination kind;
- a Topic without Subscription identity remains a Topic-only result;
- an unresolved richer messaging path may still retain a valid Broker claim if Broker identity and Service identity are independently established.

### 4.3 Architecture Manifest

Extend the existing minimal `architecture.yaml` format with an optional explicit Broker-use block:

```yaml
service: <service identity input>
x-aip-service-id: service:example
brokers:
  - brokerId: kafka:cluster-a
```

The manifest continues to mint no Service. Its Service must resolve to a Service already declared by a phase-0 source, exactly as for `calls`.

`brokerId` is an explicit stable broker id. It is not inferred from a host, protocol or display name.

This block exists for independently authored coarse architecture evidence such as the frozen FluxNova Broker links. It must not be added after inspecting AIP output merely to improve an answer.

### 4.4 Evidence, reconciliation and graph

- `Broker` and `USES_BROKER` carry normal declared evidence and source provenance.
- Re-import and deletion follow the existing source inventory/reconciliation rules.
- Equal canonical Broker ids reconcile; different ids do not merge by name, protocol or endpoint.
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

`ServiceDependenciesData` gains `broker_claim_ids` as a sibling of `dependency_claim_ids` and `deployment_claim_ids`.

### 5.2 REST, MCP and evidence

- `get_service_dependencies` and its REST equivalent return Broker claims for the requested Service.
- `get_evidence` can resolve `USES_BROKER` evidence and exposes `BROKER` as an entity type.
- `get_architecture_drift` is unchanged; Broker use has no runtime drift classification in this release.
- `get_service_dependencies_by_locality` is unchanged; Broker use is not locality-qualified in v0.6.1.
- MCP still advertises exactly four tools in the existing deterministic order.

Publish the smallest additive v0.6 contract needed for the Broker-aware dependency/evidence answer. Existing v0.5 schema files remain immutable; do not introduce a `0.6.1` schema-number convention solely because the product version is 0.6.1.

### 5.3 Snapshot and compatibility

Broker entities and `USES_BROKER` participate in the canonical snapshot when present.

Only inputs with qualified Broker evidence should change because of this release. OpenAPI-only and other Broker-free fixtures remain byte-identical. Broker-containing golden fixtures may be deliberately re-pinned with evidence showing exactly why they changed.

## 6. I3 — Qualification and lightweight release

### 6.1 Deterministic semantic qualification

Extend the existing Azure Service Bus, Google Pub/Sub and Kafka broker-semantic fixtures to assert:

- the expected Broker entity;
- the expected Service -> Broker `USES_BROKER` facts;
- no additional Queue/Topic/Subscription/Message semantics beyond what each fixture already establishes;
- deterministic evidence refs and byte-identical repeated output.

Add negative cases for missing, conflicting and ambiguous broker identity.

### 6.2 Cross-system qualification

Run the bounded Broker question against the three frozen references:

| System | Expected Broker result | Richer messaging result |
|---|---|---|
| Quarkus Super Heroes | `rest-fights` and `event-statistics` use the same `kafka:fights-kafka` Broker | Preserve the existing Topic/Subscription resolution limits |
| FINOS FluxNova/CALM | Payment Worker and Notification Worker use the frozen Message Broker | No Queue, Topic, Subscription, Message or HTTP operation invented from CALM `connects` |
| Apache Airflow 3.3.1 | No Service-level Broker claim from the frozen dossier because the relevant process-role identity is unresolved | Existing messaging negatives remain unchanged |

The comparison is against frozen source evidence, not AIP-generated expectations.

### 6.3 Developer-facing demonstration

Update the existing Quarkus task-led demo/question ladder with one additional question:

> **Which broker does `rest-fights` use, and what does that tell me about the messaging topology?**

The answer must show the Broker claim and its evidence, then explicitly preserve the existing limit: knowing the Broker does not resolve the missing Subscription/consumer identity.

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

For Airflow, AIP continues to refuse Service-level broker attribution when the relevant process-role identity is unresolved.

The result is deterministic, evidence-backed and available through the existing Architecture Intelligence surfaces. The four-tool MCP contract remains intact, no live broker discovery is introduced, and no generic connectivity relation has been added.
