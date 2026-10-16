# AIP v0.7.1 Release Specification — Broker-Mediated Consumer Attribution

**Status:** Draft parent release specification  
**Target release:** v0.7.1  
**Release theme:** Broker-Mediated Consumer Attribution  
**Entry baseline:** the published and post-release-verified v0.7.0 release  
**Primary outcome:** AIP can evidence-qualify which application Services are consumers of a broker-mediated destination in an explicit environment/context, without collapsing broker-native consumer identities into Services, Queues, Topics, Subscriptions, or one generic broker abstraction.  
**Governing inputs:** [ROADMAP.md](../../../ROADMAP.md), the v0.7.0 Current-State contracts, the Round 5 broker-gap validation, and the completed consumer-attribution evidence capture.

---

## 1. Release Promise

v0.7.1 completes one bounded Current-State question already identified by the real-system validation work:

> **For destination D in environment E, which Services can the available evidence safely attribute as consumers, and with what qualification?**

The release SHALL prove that Service-level consumer attribution can be derived from **two independent claims**:

~~~text
broker evidence:
broker-native consumer identity G is attached to destination D
        +
mapping evidence:
Service S uses broker-native consumer identity G
        ↓
qualified reconciliation
        ↓
Service S is attributable as a consumer of D
~~~

The two claims remain distinct. AIP MUST NOT infer either one from the other.

The governing rule is:

> **Broker attachment does not establish Service identity. Service configuration does not establish live broker attachment. Only their qualified combination may establish Service-level consumer attribution.**

The initial evidence path is Kafka, where broker-held consumer-group/member state can establish attachment to a Topic and separate source/config/runtime evidence can map the consumer-group identity to a Service.

v0.7.1 SHALL preserve enough source-native meaning that a Kafka consumer group is never silently re-described as an AIP Subscription merely because both participate in consumption.

## 2. Why This Is Product Work

The existing real-system validation found the same investigation question across multiple Kafka and RabbitMQ systems:

> **Which Services actually consume this destination?**

Repository/source analysis can often identify configured consumers. The missing AIP value is independent qualification from broker-held state in the selected environment.

The completed Kafka evidence capture demonstrated a supported path:

1. broker-held state independently identified consumer groups attached to Topics;
2. separate configuration/runtime evidence mapped those group identities to Services;
3. the mapping did not depend on name equality;
4. no message-processing claim was made merely from group membership.

That is enough to justify semantic completion, but **not** enough to assume that Kafka groups, RabbitMQ queues/bindings, and Service Bus subscriptions are the same concept.

## 3. Preserved Baseline

v0.7.1 SHALL preserve all accepted Current-State contracts from v0.7.0, including:

- evidence-qualified, deterministic Current State;
- explicit source identity, revision, environment/context and provenance;
- declared, observed, configured and derived meanings remain distinguishable;
- unresolved, ambiguous and conflicting identity/reconciliation outcomes stay explicit;
- snapshot/revision fencing and same-snapshot evidence resolution;
- REST and negotiated MCP as adapters over one semantic service;
- read-only public Architecture Intelligence;
- no LLM required for deterministic execution or qualification;
- Service, Queue, Topic, Subscription and Broker identities remain distinct;
- broker connectivity, declaration, attachment and actual message processing are different facts;
- missing broker evidence does not become “not consuming”;
- no Current-State fact is upgraded into authorization, ownership, policy or Intent.

v0.7.1 MUST NOT change the meaning of the five v0.7.0 MCP tools.

## 4. Semantic Boundary

The parent release freezes the following semantic distinctions, while exact type names and public schema vocabulary are deferred to reviewed increment specifications.

### 4.1 Destination

A **destination** is the already-supported broker-facing message destination relevant to the question, such as an existing AIP Topic, Queue, or Subscription.

v0.7.1 SHALL NOT introduce a generic destination entity solely to make the attribution model uniform.

Routing keys, exchange predicates, partitions, offsets and other broker-specific addressing details are not promoted to destination entities by this release.

### 4.2 Broker-native consumer identity

A **broker-native consumer identity** is the source-native identity through which broker state expresses consumption attachment.

Examples include:

- Kafka consumer group;
- RabbitMQ consumer endpoint / queue-bound consumer shape;
- Service Bus Subscription where that source-native object already is the consumer-facing routed identity.

These examples are **not declared equivalent**.

I0 SHALL freeze the smallest source-independent carrier needed for reconciliation while preserving the original source-native kind and identity.

### 4.3 Broker attachment

Broker attachment means available broker-held evidence establishes that broker-native consumer identity **G** is attached to destination **D** in a bounded context.

Attachment MUST preserve:

- source and source revision;
- broker/environment identity;
- observation/capture time or window actually supported by the source;
- native consumer kind and id;
- destination identity;
- qualification/coverage limits.

Attachment does **not** by itself establish:

- the application Service using G;
- that a message was processed;
- lag, offset or delivery state;
- authorization;
- ownership;
- desired architecture.

### 4.4 Service mapping

Service mapping means independent evidence establishes that application Service **S** uses broker-native consumer identity **G** in the relevant context.

The mapping MAY come from configuration, deployment-resolved configuration, runtime identity evidence, or another reviewed source.

Name equality alone is insufficient.

The mapping MUST remain separately attributable and separately qualified from broker attachment.

### 4.5 Derived Service-level attribution

A Service-level consumer attribution may be established only when:

1. broker attachment G → D is established;
2. Service mapping S → G is established;
3. environment/context constraints are compatible;
4. reconciliation identifies one defensible combination;
5. no stronger conflict or ambiguity invalidates the combination.

The derived result SHALL retain references to both evidence paths.

A derived attribution MUST NOT manufacture a new source fact or rewrite G as S.

## 5. Qualification Semantics

Exact public outcome names SHALL be frozen in I2, but the semantic cases are mandatory.

At minimum the qualifier SHALL distinguish:

1. **attributed consumer** — attachment and Service mapping both established;
2. **attached consumer identity, Service unresolved** — broker attachment exists but Service mapping cannot be established;
3. **Service mapping, attachment unestablished** — source/config says the Service uses the identity but selected broker evidence does not establish attachment;
4. **ambiguous mapping** — more than one Service or broker-native identity remains plausible;
5. **conflicting mapping** — independently authoritative evidence disagrees;
6. **insufficient broker coverage/context** — absence cannot be interpreted;
7. **source/object unsupported** — evidence shape cannot be represented safely.

A negative result MUST NOT mean “this Service does not consume” unless the selected source and coverage support an explicit closed-world rule reviewed in I2.

No such closed-world negative rule is assumed by this parent specification.

## 6. Source Strategy

### 6.1 Primary production path: Kafka

The first production ingestion path SHALL use Kafka broker-held consumer state because the evidence path has already been demonstrated on a real system.

The source contract SHALL prefer structured broker/admin data if practical. Human-formatted CLI output may remain qualification evidence, but production ingestion SHALL NOT depend on brittle display text without an explicit reviewed parser contract.

The Kafka source contract SHALL preserve at least:

- broker/environment identity;
- consumer-group identity;
- destination/topic identity;
- group/member state needed to establish the bounded attachment claim;
- capture/revision/time identity supported by the source.

Lag, offsets, rebalancing history and assignment internals are out of scope unless required purely as provenance for the attachment fact.

### 6.2 Required contrasting shape: RabbitMQ

Before the source-independent carrier is frozen, I0 SHALL evaluate at least one concrete RabbitMQ consumer/binding shape.

The purpose is **semantic falsification**, not to require a second production adapter.

The cross-check asks:

> Can the proposed carrier preserve the distinction between Kafka consumer-group attachment and the RabbitMQ consumer/queue/binding shape without pretending the native objects mean the same thing?

If not, I0 SHALL either:

- revise the source-independent carrier;
- keep the distinction source-specific and explicit; or
- record a model gap and narrow v0.7.1 scope.

A second production adapter is not required solely for symmetry.

### 6.3 Service-mapping source

The release SHALL qualify at least one real Service-mapping path where name equality is not the authority.

The existing Kafka evidence capture may be reused if its source/config/runtime mapping remains pinned and reproducible.

## 7. Canonical and Persistence Constraints

v0.7.1 SHALL add only the minimum Architecture Knowledge needed to answer the product question.

The design SHOULD prefer:

- one explicit source-native consumer-identity carrier;
- one attachment fact;
- one independently evidenced Service↔consumer-identity mapping;
- one derived attribution in the Architecture Intelligence projection.

It SHOULD NOT add a broad broker-topology model.

Any new canonical identity or relation MUST have:

- deterministic id rules;
- source ownership and authoritative-removal semantics;
- replay/idempotency behavior;
- provenance/evidence linkage;
- explicit conflict/reconciliation behavior;
- snapshot serialization rules;
- backwards-compatible absence when no new source is configured.

Broker-native identity nodes, if introduced, are not public proof that a corresponding Service exists.

## 8. Public Architecture Intelligence

v0.7.1 SHALL answer the product question through the shared semantic service and at least REST + negotiated MCP.

I3 SHALL decide whether the best product surface is:

- an extension of an existing messaging/current-state answer, or
- one new bounded question-specific tool/endpoint.

The parent spec does **not** pre-authorize a sixth MCP tool.

The public answer SHALL:

- require a bounded destination and environment/context;
- expose Service-level attribution only when qualified;
- preserve the broker-native identity supporting the attribution;
- distinguish attachment from message processing;
- surface unresolved/ambiguous/conflicting cases;
- include evidence refs for broker attachment and Service mapping;
- preserve same-snapshot/revision guarantees;
- remain deterministic and read-only.

The public answer MUST NOT expose credential secrets, broker administrative secrets, or raw sensitive client metadata merely because the broker source contains them.

## 9. Deterministic Qualification

Qualification SHALL be expectation-driven and independent of implementation output.

At minimum the frozen matrix SHALL include:

- Kafka group attached to Topic + defensible Service mapping → attributed;
- Kafka group attached + no defensible Service mapping → unresolved Service;
- Service configured for group + broker attachment absent/insufficient → not upgraded to a negative;
- two plausible Services for one group → ambiguous;
- conflicting authoritative mappings → conflict;
- broker evidence from wrong environment/context → not combined;
- multiple members in one consumer group → does not create multiple Services without mapping evidence;
- one Service using one group across multiple Topics → distinct destination attributions;
- broker-native identity not coerced to Subscription;
- no message-processing claim from attachment alone;
- replay unchanged → byte-identical result;
- authoritative source revision/removal removes stale attachment/mapping facts;
- legacy v0.7.0 snapshots and five public tools unchanged when the new source is absent.

A/B deterministic runs on the exact candidate are required before release.

## 10. Real-System Qualification

The release SHALL include:

1. the already captured/pinned Kafka real-system evidence path or an equally strong refreshed capture;
2. at least one contrasting RabbitMQ semantic shape;
3. one end-to-end candidate run proving broker evidence + independent Service mapping + public answer;
4. at least one unresolved/insufficient real or realistic case;
5. replay/removal behavior across two source revisions or captures if the selected source supports authoritative revision/removal.

Qualification SHALL explicitly state what the source establishes and what remains unmeasured.

In particular, a stable consumer group attached to a Topic is not evidence that an application message was processed during the observation.

## 11. Product-Value Check

v0.7.1 is a semantic-completion release, not a broad research release.

The product check is therefore narrow:

> **Does independent broker evidence materially improve the answer to “which Services consume this destination?” compared with repository/configuration analysis alone?**

Record at least:

- how much mapping remains manual;
- how often broker identities resolve to Services;
- unresolved/ambiguous rate;
- source setup/capture effort;
- whether broker evidence changes or strengthens the coding-agent investigation boundary.

The result SHALL end with one owner-reviewed disposition:

~~~text
CONTINUE
NARROW
DEFER
STOP
~~~

No user-research claim is required.

## 12. Explicitly Out of Scope

v0.7.1 does not require:

- general broker-topology modelling;
- routing predicates or RabbitMQ header/exchange semantics;
- lag/offset analytics;
- rebalance history;
- partition ownership analysis;
- DLQ/retry topology;
- framework-generated destination discovery;
- message-level processing confirmation unless already independently evidenced;
- generic “consumer endpoint” equivalence across all brokers;
- a second production broker adapter merely for cross-source symmetry;
- authorization, ownership, policy, Intent or compliance assessment;
- historical architecture trajectories;
- v0.8 cross-boundary System/Component composition.

## 13. Increment Plan

### I0 — Consumer Attribution Semantic Freeze

Freeze:

- source-independent carrier or explicitly source-specific boundary;
- Kafka and RabbitMQ distinction;
- identity/reconciliation rules;
- exact meaning of broker attachment;
- exact meaning of Service mapping;
- derived-attribution rule;
- required real-source fixtures and negative cases.

I0 MUST close the currently open cross-broker abstraction question before implementation depends on a common model.

### I1 — Selected Broker Evidence Source

Implement the smallest production Kafka source needed for broker attachment:

- acquisition/capture contract;
- revision/time/environment identity;
- ingestion and removal/replay;
- sanitized provenance;
- deterministic vectors;
- real-source replay.

No public answer is required yet.

### I2 — Service Mapping and Attribution Qualification

Implement/freeze:

- Service↔broker-native-identity mapping input;
- reconciliation;
- ambiguity/conflict behavior;
- derived Service-level consumer attribution;
- qualification matrix and independent oracle.

### I3 — Public Consumer-Attribution Answer

Expose the bounded product question through Architecture Intelligence:

- shared semantic service;
- REST;
- negotiated MCP;
- evidence drill-down;
- deterministic ordering/bounded enumeration;
- refusal/limitation behavior.

I3 decides whether an existing tool is extended or a new tool is justified.

### I4 — Real-System and Product Qualification

Run:

- deterministic A/B qualification;
- Kafka real-system replay;
- RabbitMQ semantic cross-check;
- candidate public-surface parity;
- product-value check;
- cost/operability evidence;
- completion/handoff.

### I5 — Release Candidate, Publication, Verification

Use the established exact-candidate release discipline from v0.7.0:

- release-content freeze;
- exact-SHA qualification;
- candidate-image verification;
- owner publication decision;
- immutable artifact publication;
- post-release verification by digest.

## 14. Release Exit Criteria

v0.7.1 is complete only when all of the following hold:

1. broker-native consumer identity remains distinct from Service and existing messaging entities;
2. broker attachment and Service mapping are independently evidenced;
3. Service-level attribution is derived only from their qualified combination;
4. Kafka production ingestion is deterministic, replayable and revision/context bounded;
5. the proposed source-independent semantics survive a concrete RabbitMQ contrast or the scope is explicitly narrowed;
6. ambiguous, conflicting and insufficient cases remain explicit;
7. attachment is not presented as proof of message processing;
8. the public answer is deterministic, evidence-linked and read-only;
9. no new source configured => v0.7.0 behavior remains unchanged;
10. exact-candidate A/B and real-system qualification pass;
11. the product-value check has an explicit disposition;
12. release publication and published-artifact verification complete successfully.

## 15. Permitted Release Claim

Only after qualification:

> **AIP v0.7.1 can evidence-qualify which application Services are attributable as consumers of broker-mediated destinations for the supported broker source by combining broker-held consumer attachment with independently evidenced Service mapping, while preserving broker-native identity, provenance, context and unresolved ambiguity. It does not equate broker-native consumer concepts, infer message processing from attachment, or turn Current State into authorization, ownership, policy or Intent.**
