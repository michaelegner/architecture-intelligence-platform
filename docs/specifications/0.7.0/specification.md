# AIP v0.7.0 Release Specification — API-Aware Current State

**Status:** Accepted parent release specification — normative v0.7.0 scope and acceptance contract; implementation-specific decisions identified below SHALL be frozen in reviewed increment specifications before implementation depends on them.

**Target release:** v0.7.0  
**Release theme:** API-Aware Current State  
**Entry baseline:** v0.7.0 SHALL derive from the published and post-release-verified v0.6.3 baseline.  
**Primary outcome:** AIP can establish how an API is evidenced as exposed to configured consumers and how independently observed, consumer-attributed usage relates to those configured relationships in an explicit environment and observation window, without collapsing gateway objects, API contracts/operations, application services, consumers, access entitlements, runtime interactions, business concepts, authorization policy, or architectural Intent.  
**Governing inputs:** [Product Doctrine and Strategic Direction](../../product-doctrine-and-strategic-direction.md), [ROADMAP.md](../../../ROADMAP.md), [Research Landscape](../../landscape.md), and the [v0.6.0 parent specification](../0.6.0/specification.md).

---

## 1. Release Promise

v0.5.0 broadened Current-State discovery. v0.6.0 made supported Current-State relationships locality-aware. v0.6.1 completed broker semantics for the existing messaging question. v0.6.2 established the hosted live demo without creating a new architecture-question class.

v0.7.0 SHALL add one materially new class of evidence-qualified architecture question:

> **How are APIs exposed and consumed, and what can the available evidence establish about those relationships?**

The first bounded validation question is:

> **Which configured consumer/API relationships have matching observed runtime usage in a selected environment and observation window, and which remain unestablished from the available evidence?**

The release SHALL prove:

> **Given a stable Current-State snapshot, an explicit environment and observation window, gateway configuration that establishes a source-specific configured access relationship, and independent consumer-attributed request measurements, AIP can deterministically relate API exposure, configured consumers and observed usage while preserving source meaning, identity uncertainty, evidence provenance, qualification, coverage and limitations. Missing or unattributed measurements remain unresolved; they do not become zero usage, denied access, non-use, policy failure or architectural Intent.**

The governing semantic path is:

~~~text
API contract / operation evidence
        +
Gateway route/service configuration
        +
Consumer identity + configured-access evidence
        +
Consumer-attributed request measurements
        ↓
Source-specific normalization
        ↓
Identity / association reconciliation
        ↓
Configured-access assessment
        +
Observed-usage assessment
        ↓
Deterministic API-aware Current-State projection
        ↓
Evidence-qualified answer
~~~

The non-negotiable invariants are:

~~~text
gateway route/service != application Service != API contract/operation
configured access != observed consumer-attributed usage
ACL/entitlement != formal product subscription
consumer identity != credential secret
unattributed request != request by a particular consumer
association != entity equivalence
API endpoint != application, domain, business capability, owner or authorization boundary
gateway presence != system-wide integration style
missing measurement != zero usage
observed usage != approved or intended usage
configured access != architectural Intent
Current State != policy/compliance assessment
consumer projection != new source of Architecture Knowledge
~~~

AIP remains advisory and read-only on its public Architecture Intelligence surface. Agents, LLMs, gateway UIs, demos and external tools never establish or strengthen canonical architectural truth.

## 2. Normative Language

**MUST**, **MUST NOT**, **REQUIRED**, **SHALL**, **SHALL NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

Examples, conceptual types, candidate entity names and suggested endpoint/tool names in this parent specification are not frozen public contracts unless explicitly stated. I0–I3 increment specifications SHALL freeze the actual semantic vocabulary, schema, identifiers, source mapping and public answer contracts before fixtures or downstream clients depend on them.

Independent expected results, not output copied from AIP, a gateway product or an agent interpretation, constitute qualification evidence. Source documentation describes source semantics but is not semantic authority for AIP.

## 3. Entry Conditions and Preserved Baseline

The release SHALL preserve the accepted Current-State contracts from v0.5–v0.6:

- one Canonical Model mapping target; source adapters do not write arbitrary persistence structures;
- deterministic source inventory, revision, authoritative-removal, atomic import and replay rules;
- distinct declared, observed and infrastructure-derived evidence modes;
- bounded identity reconciliation with explicit unresolved, ambiguous and conflicting outcomes;
- one qualification owner for each public semantic question;
- snapshot/revision fencing, same-snapshot evidence resolution, sanitized provenance and deterministic answers;
- environment and observation-window semantics, including the v0.6 locality distinction between supported local knowledge and universal claims;
- Service, Workload, Pod, Queue, Topic, Subscription and Broker distinctions already accepted;
- REST and negotiated MCP as supported public adapters over the shared semantic service;
- no generic graph/Cypher correctness path;
- no LLM required for deterministic execution or qualification;
- read-only public Architecture Intelligence;
- runtime ingestion that requires serialization remains serialized without blocking the FastAPI event loop for the duration of synchronous ingestion work;
- unsupported per-source canonicalization failures become deterministic source rejections while preserving the existing discovery-run commit gate (`PARTIAL` / `FAILED` runs commit nothing).

These are preserved baseline invariants, not part of the v0.7 capability scope. A v0.7 increment SHALL not re-specify or broaden them unless it introduces a materially different ingestion or source-import path that requires independent qualification.

## 4. Fixed Scope Budget

### 4.1 In scope

v0.7.0 SHALL deliver:

1. A bounded **gateway source-capability survey and semantic freeze** across Kong, Gravitee, Apache APISIX and Tyk, followed by selection of exactly one initial real gateway for implementation and qualification.
2. A small **platform-independent API-aware Current-State vocabulary** that preserves native source distinctions rather than normalizing everything into a subscription.
3. Deterministic ingestion of one selected gateway's **configuration/inventory evidence**, including source identity, revision, authoritative-removal and provenance semantics.
4. Deterministic acquisition or replay of **consumer-attributed request measurements** with explicit environment/window, attribution meaning and telemetry coverage.
5. Bounded **identity/association reconciliation** between API contracts/operations, gateway routes/services, application Services and gateway consumers, including unresolved, ambiguous and conflicting cases.
6. Independent qualification of **configured access** and **observed usage**, followed by one bounded API-aware Current-State projection that does not convert either into Intent, policy or authorization judgment.
7. One deterministic, question-specific Architecture Intelligence answer through the shared semantic service, REST and negotiated MCP, with same-snapshot evidence drill-down, bounded enumeration, limitations and deterministic ordering.
8. Independent positive/negative semantic qualification and at least one real-source end-to-end qualification using the selected gateway.
9. A product-value pilot that records useful answer coverage and the cost of setup, synchronization, attribution and identity mapping, with an explicit continue/narrow/defer/stop disposition.
10. Exact-candidate release qualification, owner-authorized publication if granted and post-publication verification.

### 4.2 Explicitly out of scope

~~~text
four production gateway adapters merely to compare vendors
complete enterprise API inventory or API-product catalog
business-capability classification
automatic domain or organizational-owner inference
automatic authorization-boundary inference
security-policy or compliance assessment
formal API product / plan / subscription semantics unless the selected source explicitly establishes them
turning ACL membership, key policy or consumer restriction into a generic "subscription"
generic API analytics/dashboarding
system-wide integration-style classification inferred from gateway presence
complete consumer population or usage completeness without explicit coverage
historical architecture reconstruction
architecture trajectories
explicit Architecture Intent, promises, requirements or authority evaluation (v0.8)
Current-State ↔ Intent assessment (v0.9)
approval workflows or remediation
multiple gateway integrations as a release gate
new generic graph/Cypher public API
agent/LLM-derived identity, access, usage, ownership or qualification
~~~

OpenAPI/AsyncAPI, repository, CI/CD, catalog and architecture-model sources MAY contribute only where a reviewed increment explicitly states the bounded question they help answer. They do not enter v0.7 merely because they contain API-related metadata.

## 5. Increment Contract and Dependency Order

| Increment | Title | Required outcome |
|---|---|---|
| I0 | Gateway Capability Survey and Semantic Freeze | Survey Kong, Gravitee, APISIX and Tyk; freeze source-neutral distinctions and select one real gateway for the first implementation based on evidence capability, replayability and mapping burden. |
| I1 | Selected Gateway Configuration Source | Ingest the selected gateway's real configuration/inventory evidence with deterministic identity, revision, provenance, authoritative-removal and replay behavior. |
| I2 | Consumer Attribution and Configured-vs-Observed Qualification | Acquire/replay consumer-attributed request measurements, reconcile identities/associations and independently qualify configured access and observed usage. |
| I3 | API-Aware Current-State Projection and Public Answer | Expose one deterministic question-specific answer through service, REST and negotiated MCP with evidence drill-down and bounded limitations. |
| I4 | Deterministic, Real-System and Product-Value Qualification | Independently authored truth tables, negative cases, repeatability, real-source replay, cross-source semantic checks and the product-value pilot qualify the release capability. |
| I5 | Release Candidate, Publication and Verification | One exact candidate reaches a recorded release-ready or verified-published outcome. |

~~~text
I0 → I1 → I2 → I3 → I4 → I5
~~~

I0–I3 MAY be internally sliced. A material semantic ambiguity SHALL stop the affected implementation until resolved in a reviewed specification amendment. Increment specifications may narrow the parent scope or freeze deferred details; they MUST NOT silently expand the release into API management, governance or Intent.

---

# Part I — Source Capability and Semantic Freeze

## 6. I0 Gateway Capability Survey

I0 SHALL survey all four currently identified gateway families:

- Kong;
- Gravitee;
- Apache APISIX;
- Tyk.

The survey is intentionally bounded. It SHALL answer, for each candidate:

1. **What exact configured relationship can the source establish?** Examples include Consumer plus ACL membership, application plus plan plus subscription, consumer restriction, or key plus access policy. These are not assumed equivalent.
2. **What stable consumer identity exists?** The survey SHALL distinguish logical consumer/application identity from credentials or secrets.
3. **Can runtime usage be attributed to that same consumer deterministically?** Request-derived measurement is required. A dashboard total without stable consumer attribution is insufficient.
4. **What environment/window and telemetry coverage can be established?** Missing metrics or unknown coverage must not become zero usage.
5. **Can the source be captured and replayed locally or from a pinned immutable fixture?** Real source configuration and request-derived measurements SHALL be preservable for deterministic qualification.
6. **Which required capabilities are OSS/self-hosted versus proprietary/paid?** The release SHALL not accidentally depend on a commercial feature while presenting the source as an OSS qualification path.
7. **What identity-mapping burden exists?** The survey SHALL record which associations are explicit, which require user-authored mapping, and which remain unresolved.
8. **What native distinctions would be lost by a naïve common model?** The survey SHALL identify semantics that must remain source-specific or explicitly qualified.

I0 produces a reviewed support matrix and a source-selection decision. It does **not** implement four adapters.

## 7. Source-Selection Rule

Exactly one gateway SHALL be selected for the initial production adapter and end-to-end real-source qualification.

Selection SHALL be based on the ability to prove the first bounded question, not popularity or similarity to AIP's preferred model. The selected gateway must support:

~~~text
real configured consumer/API relationship
+
stable consumer attribution
+
request-derived usage evidence
+
bounded environment/window semantics
+
deterministic capture/replay
+
acceptable setup/synchronization/mapping cost
~~~

Kong remains the roadmap's proposed reference, not the presumed winner.

The current research hypothesis is that APISIX and Tyk may offer particularly clean first-slice evidence shapes, while Gravitee provides a useful richer semantic comparison and Kong remains a mature baseline. **This is not a selection decision.** I0 SHALL decide from the evidence.

## 8. I0 Exit Criteria

I0 is complete only when:

- all four candidates have one comparable capability row grounded in current source documentation or direct inspection;
- the semantic distinctions in §9 are reviewed and sufficient to describe all four without renaming their native relationship into a generic subscription;
- one gateway is selected with recorded reasons;
- the selected gateway has a concrete acquisition/replay plan for configuration and request-derived measurements;
- at least one independently different candidate is retained as a later semantic cross-check;
- unsupported or proprietary-only capabilities needed by the first question are explicit;
- no schema or canonical extension has been implemented merely to fit a preferred vendor.

---

# Part II — API-Aware Current-State Semantics

## 9. Minimum Source-Neutral Vocabulary

The exact canonical/public names are an I0 freeze decision, but the model SHALL preserve at least these distinct meanings:

~~~text
API Contract
API Contract Version
API Operation
Gateway Service
Gateway Route
Application Service
Gateway Consumer / Consumer Application
Configured Access Relationship
Observed Consumer Interaction
~~~

A source MAY establish richer concepts such as API Product, Plan, Subscription, organization, owner or authorization rule. Such a concept is admitted only if:

1. the source explicitly establishes it;
2. its semantics are preserved;
3. it is required by the bounded architecture question or retained as source evidence;
4. AIP does not infer the same concept for sources that lack it.

A common AIP relationship MUST represent common meaning, not merely similar graph shape.

## 10. Distinct Identity Domains

The following identities SHALL remain distinct unless explicit evidence or mapping establishes an association:

~~~text
API contract/version identity
API operation identity
gateway service identity
gateway route identity
application Service identity
gateway consumer/application identity
credential/key identity
runtime request attribution identity
~~~

Association does not imply equivalence.

Examples:

- a gateway Route may expose an API Operation but is not that Operation;
- a gateway Service may forward to an application Service but is not automatically the same entity;
- a Consumer may authenticate with multiple credentials; the credential secret is not the consumer identity;
- a route path matching an OpenAPI path is not enough to establish operation equivalence when method, version or base-path resolution is ambiguous.

I0/I2 SHALL freeze deterministic mapping rules and explicit unresolved, ambiguous and conflicting outcomes.

## 11. Integration Style, Interaction Pattern and Runtime Component

AIP SHALL preserve this distinction:

~~~text
integration style
        !=
specific configured interaction/access relationship
        !=
runtime component or gateway object
~~~

Gateway configuration and traffic may establish bounded API exposure, access and observed usage. They do not establish that the whole system is "API-first", "REST architecture", "gateway-mediated", "synchronous", "public", "internal", or any other broad architectural classification unless separately evidenced and explicitly in scope.

---

# Part III — Configuration Evidence and Source Lifecycle

## 12. Gateway Configuration as Current-State Evidence

The selected gateway adapter SHALL ingest the smallest source surface required to answer the first question.

At minimum, the adapter SHALL preserve:

- source-native entity identity;
- source-native relationship kind;
- source revision/capture identity;
- configuration fields required for routing/access semantics;
- provenance sufficient to explain the normalized claim;
- source authority/removal scope;
- unsupported or discarded fields relevant to semantic interpretation.

Secrets, credential material and tokens SHALL NOT be persisted as architecture evidence. A stable credential identifier MAY be retained only where needed for deterministic consumer attribution and only if it is safe to expose under AIP's evidence/provenance rules.

## 13. Inventory, Revision and Authoritative Removal

The selected gateway source SHALL reuse AIP's established source lifecycle:

~~~text
source inventory
revision identity
atomic import
authoritative removal within owned scope
replay/idempotence
provenance lineage
snapshot fencing
~~~

A failed or partial source acquisition MUST NOT erase previously accepted source state unless the established source rules explicitly authorize that transition.

A failure in one gateway/source import MUST be converted into that source's deterministic rejected outcome rather than escaping as an unhandled exception. Other discovered sources SHALL still be evaluated and reported according to the existing per-source rules, but v0.7 SHALL preserve the inherited commit gate: if any source rejection makes the run `PARTIAL`, **nothing from that run commits** and previously accepted state remains unchanged. v0.7 source adapters SHALL NOT reinterpret this baseline containment guarantee as permission for partial commits.

Gateway configuration "latest" is not automatically authoritative over API contracts or application-service identity. Source authority is bounded by what the source actually owns.

---

# Part IV — Observed Consumer Usage

## 14. Request-Derived Measurement Contract

The first positive observed-usage case SHALL use real or captured request-derived measurements attributable to a consumer in an explicit environment and observation window.

The measurement contract SHALL state:

- measurement source and version;
- consumer attribution field and its meaning;
- API/gateway target attribution fields;
- environment identity;
- timestamp/window semantics;
- aggregation granularity;
- known sampling, retention or export behavior;
- coverage limitations;
- whether zero means measured zero or merely absent data.

The rule is:

> **No applicable measurement is not evidence of zero requests.**

An unattributed request may establish that a route/API was used, if independently resolvable, but SHALL NOT establish use by a specific consumer.

AIP SHALL not infer authorization success, policy correctness, business use, owner approval or architectural Intent merely because a request was accepted and measured.

Any new runtime measurement-ingestion path introduced by v0.7 SHALL preserve the baseline ingestion-concurrency contract: blocking work must not occupy the FastAPI event loop while ingestion semantics that require serialization remain serialized. A reviewed increment MAY define a materially different path only if it independently qualifies that path.

---

# Part V — Reconciliation and Qualification

## 15. Identity and Association Reconciliation

I2 SHALL freeze a deterministic reconciliation pipeline for:

~~~text
Gateway Consumer
        ↔ runtime attribution identity

Gateway Route/Service
        ↔ API Contract/Version/Operation

Gateway upstream/target
        ↔ application Service
~~~

Each mapping SHALL have a provenance-bearing basis such as:

- exact stable source identity;
- explicit configuration reference;
- explicit user-authored mapping admitted by the spec;
- independently supported deterministic normalization.

Similarity of names, URLs, hosts, paths or graph proximity alone is insufficient when ambiguity exists.

Required outcomes include at least:

~~~text
RESOLVED
UNRESOLVED
AMBIGUOUS
CONFLICTING
UNSUPPORTED
~~~

Exact public vocabulary is deferred to I2.

## 16. Configured Access and Observed Usage Are Independent Assessments

AIP SHALL assess at least two independent propositions:

~~~text
ConfiguredAccess(C, A, S)
ObservedUsage(C, A, E, W, S)
~~~

where:

- C is the resolved consumer identity;
- A is the resolved API exposure/operation scope;
- E is the environment;
- W is the observation window;
- S is the selected canonical snapshot.

Configured access establishes only that the selected source configuration permits, registers or associates the consumer according to the source-specific rule.

Observed usage establishes only that applicable request-derived evidence attributes matching usage to the consumer/API relation in the selected context.

Neither proposition silently strengthens the other.

## 17. Minimum Qualification Matrix

I2 SHALL freeze a truth table at least covering:

| Configured relationship | Applicable attributed measurement | Required interpretation |
|---|---|---|
| yes | matching requests | configured relationship with established observed usage |
| yes | measured zero under explicitly complete supported coverage | configured relationship with no observed usage in that qualified window; exact wording must preserve the coverage premise |
| yes | no applicable measurement / unknown coverage | configured relationship; usage unestablished |
| no | matching attributed requests | observed interaction without matching configured-access evidence; do not invent entitlement or policy failure |
| no | no applicable measurement | neither proposition established |
| ambiguous/unresolved | any | preserve ambiguity/unresolved mapping; do not force a joined answer |
| conflicting source evidence | any | preserve conflict and lineage |

The final vocabulary MUST NOT reduce all cases to generic CONFIRMED / NOT_CONFIRMED if that would erase whether the proposition is configuration, usage, identity or coverage.

## 18. Bounded API-Aware Current-State Projection

The projection SHALL be question-specific and bounded. It SHALL not expose arbitrary graph neighborhoods.

For a selected API exposure or application service, the answer SHOULD enumerate:

- resolved API contract/version/operations where applicable;
- gateway service/route exposure used for the answer;
- configured consumers/access relationships;
- independently observed consumer-attributed usage assessments;
- unresolved, ambiguous or conflicting associations;
- measurement coverage and applicability;
- evidence references;
- limitations;
- snapshot and observation context.

Enumeration SHALL be bounded with deterministic ordering and explicit truncation/cursor semantics where necessary.

---

# Part VI — Public Architecture Intelligence

## 19. Shared Semantic Owner

ArchitectureIntelligenceService or its reviewed successor remains the sole semantic owner for the public API-aware question.

v0.7 SHALL NOT simply add another large inline projection branch if doing so materially worsens the semantic service's role as a coordination hub. I3 MAY extract a dedicated API-aware projection component/repository as touch-driven refactoring, provided the semantic service remains the public owner and behavior is independently tested.

This is not authorization for broad architectural cleanup.

## 20. REST and MCP Surface

I3 SHALL expose one question-specific public answer through:

1. the semantic service;
2. REST;
3. negotiated MCP.

The public answer SHALL support same-snapshot evidence resolution through the existing evidence capability or a reviewed compatible extension.

The exact REST path and MCP tool name are deferred to I3. A likely shape is conceptually equivalent to:

~~~text
get_api_consumer_usage(
    service_or_api,
    environment,
    observation_window,
    optional_consumer_filter
)
~~~

but the name and request schema are not frozen by this parent draft.

No generic gateway-query tool and no generic Cypher/graph tool shall be introduced.

## 21. Public Answer Guarantees

Every answer SHALL include enough information to establish:

- the snapshot used;
- the explicit environment/window;
- which configured source revision or revisions were applicable;
- which measurement source or sources were applicable;
- identity/reconciliation outcomes;
- configured-access qualification;
- observed-usage qualification;
- evidence references;
- coverage/attribution limitations;
- bounded enumeration/truncation state.

The same semantic request over the same frozen input state SHALL be deterministic.

---

# Part VII — Qualification

## 22. Deterministic Semantic Qualification

I4 SHALL include independently authored positive and negative cases that cover at minimum:

1. configured plus observed;
2. configured plus no applicable measurement;
3. configured plus explicit measured-zero case if the selected source can establish complete bounded coverage;
4. observed plus no matching configured access;
5. unattributed request;
6. ambiguous consumer identity;
7. ambiguous route/operation mapping;
8. gateway object distinct from application Service;
9. source revision removal/update;
10. same-snapshot evidence resolution;
11. deterministic ordering/replay;
12. regression of v0.5/v0.6 dependency, locality, messaging and evidence answers.

Expected outputs SHALL be authored independently from AIP execution.

## 23. Real-Source Qualification

At least one real gateway SHALL be qualified end-to-end from captured configuration and request-derived measurements.

The fixture or replay SHALL be:

- independently inspectable;
- pinned to explicit source/product versions;
- reproducible without relying on an uncontrolled external SaaS state;
- free of real secrets;
- capable of reproducing both positive and negative/insufficient cases.

If the selected source's real analytics cannot be replayed deterministically, I0 SHALL reconsider the source selection rather than replacing the missing evidence with synthetic semantics.

## 24. Cross-Source Semantic Check

The release SHALL NOT implement a second production adapter solely for validation, but I4 SHALL perform at least one independent semantic cross-check against a differently shaped gateway source from the I0 survey.

The purpose is to test:

> **Can the frozen AIP vocabulary represent the second source without pretending its native access concept is the same as the selected source's concept?**

A documentation/capture-based mapping dossier is sufficient if it uses real source semantics and does not claim adapter qualification.

If the second source exposes a distinction the model cannot preserve safely, the issue is either:

- a justified source-neutral model gap requiring reviewed amendment; or
- a source-specific semantic that remains explicit and unnormalized.

It is not permission to collapse semantics for convenience.

## 25. Product-Value Pilot

v0.7 SHALL include a bounded product-value pilot, not only semantic correctness.

The pilot SHALL record:

~~~text
useful answer coverage
setup effort
source synchronization effort
consumer attribution effort
identity mapping effort
unresolved/ambiguous rate
manual input required
time/cost to keep evidence current
value to a realistic coding-agent task
~~~

The pilot SHALL end with one explicit disposition:

~~~text
CONTINUE
NARROW
DEFER
STOP
~~~

A semantically correct capability that requires disproportionate ongoing manual mapping may fail the product-value gate.

The pilot does not change semantic truth. Product usefulness and Architecture Knowledge correctness remain separate judgments.

---

# Part VIII — Release Qualification and Publication

## 26. Release Candidate Gate

Before candidate freeze:

- all I0–I4 completion criteria are recorded;
- the required entry baseline is present and post-release verified;
- the selected gateway source/version and replay assets are pinned;
- the public schema/tool surface is frozen;
- deterministic evaluation passes twice from clean state with semantically identical output;
- full unit, integration and demo suites pass;
- CodeQL, dependency and secret/security checks pass under the repository's current release policy;
- the existing golden path remains valid or is intentionally versioned with reviewed justification;
- release-version consistency, documentation and examples are updated;
- known limitations and unsupported source semantics are explicit;
- no host credential, consumer credential or real gateway secret is committed.

## 27. Publication

Publication follows the repository's standard owner-authorized release workflow.

No release tag may move. Published container/source identities SHALL bind to the exact accepted candidate. MCP Registry metadata SHALL be version-consistent with the release and published only under explicit owner authorization.

## 28. Post-Release Verification

Post-release verification SHALL independently check:

- tagged source identity;
- published image identity;
- version metadata;
- REST/MCP public answer availability;
- evidence drill-down;
- deterministic replay of the selected real-source qualification;
- preservation of the v0.6 locality/messaging golden paths;
- MCP Registry entry if publication is part of the release workflow.

The terminal outcome SHALL distinguish at least release-ready, published and post-release-verified states according to existing AIP release discipline.

---

# Part IX — Security, Privacy and Operational Boundaries

## 29. Gateway Credentials and Consumer Identity

AIP SHALL never require gateway credential secrets as architecture evidence.

Configuration adapters SHALL redact or omit secrets before canonicalization/provenance storage. Stable non-secret identifiers may be retained when required for deterministic reconciliation.

Consumer-attributed usage may itself be sensitive operational metadata. The selected source specification SHALL identify which identifiers can be exposed through public Architecture Intelligence and which must be transformed, redacted or withheld.

## 30. Authorization Semantics

v0.7 does not answer:

~~~text
"Is this consumer authorized correctly?"
"Should this consumer have access?"
"Is this request compliant?"
"Who owns this API?"
"Is this usage approved?"
~~~

A source may provide ACLs, policies or subscription state as **configured Current-State evidence**. AIP does not convert that evidence into architectural Intent or policy judgment.

## 31. Coverage and Non-Observation

Negative usage statements require explicit coverage semantics.

Without a reviewed closed-world rule for the exact source/environment/window:

~~~text
no metric
!=
zero requests
!=
consumer did not use API
!=
consumer cannot use API
~~~

The release SHALL prefer unresolved/insufficient evidence over false absence.

---

# Part X — Documentation and Demonstration

## 32. Required Documentation

Before release, documentation SHALL explain:

- the v0.7 product question;
- the selected gateway and why it was selected;
- the I0 four-gateway capability survey;
- source-native configured-access meaning;
- consumer attribution semantics;
- configured versus observed qualification;
- identity/association rules;
- measurement coverage;
- API contract/operation vs gateway route/service vs application Service;
- why subscription/product/owner/authorization/Intent are not inferred;
- REST/MCP examples;
- evidence drill-down;
- limitations and unsupported cases;
- replay/qualification procedure;
- product-value pilot result.

The research landscape remains an input, not release evidence.

## 33. Demonstration

The demonstration SHALL be task-oriented, not dashboard-oriented.

A preferred developer task is one where an agent proposes changing an API contract or operation and asks AIP:

> **Which configured consumers are related to this API exposure, which of them have independently observed usage in the selected completed window, and what remains unresolved or unsupported?**

AIP may identify relationships to inspect. It SHALL NOT claim which consumers depend on a particular payload field unless evidence independently establishes that fact.

The hosted Pitstop demo MAY be extended if it provides a suitable API/gateway scenario, but reusing Pitstop is not a release requirement and SHALL NOT distort source selection.

---

# Part XI — Decision Register

## 34. Decisions already made

| ID | Decision | Status |
|---|---|---|
| D1 | v0.7 remains **API-Aware Current State**, not Intent. | Accepted |
| D2 | First bounded question compares configured consumer/API relationships with independently observed consumer-attributed usage in environment/window. | Accepted |
| D3 | Survey Kong, Gravitee, APISIX and Tyk in I0; implement/qualify exactly one initial gateway. | Accepted |
| D4 | Gateway/source terminology does not become canonical AIP terminology. | Accepted |
| D5 | Configured access and observed usage are separate propositions. | Accepted |
| D6 | Missing/unattributed measurements do not become zero or consumer usage. | Accepted |
| D7 | Formal Intent remains v0.8; Current↔Intent assessment remains v0.9. | Accepted |
| D8 | Product-value qualification is a release gate alongside semantic correctness. | Accepted |

## 35. Decisions I0 must freeze

| ID | Decision | Required before |
|---|---|---|
| O1 | Selected initial gateway. | I1 implementation |
| O2 | Exact source-neutral entity/relation vocabulary. | I1 schema/fixtures |
| O3 | Source-specific configured-access mapping for selected gateway. | I1 |
| O4 | Consumer identity and safe stable identifier policy. | I1/I2 |
| O5 | Runtime measurement source, attribution semantics and coverage model. | I2 |
| O6 | Route/service ↔ API contract/operation association rules. | I2 |
| O7 | Gateway target ↔ application Service association rules. | I2 |
| O8 | Exact qualification vocabulary/truth table. | I2 fixtures |
| O9 | Bounded enumeration and truncation limits. | I3 |
| O10 | Public REST path, MCP tool name and versioned request/response schema. | I3 |
| O11 | Real-source replay packaging and independent semantic cross-check source. | I4 |

## 36. Parent Specification Definition of Done

This parent specification is ready for implementation planning when:

1. the architecture question is narrow enough to justify a capability release;
2. I0 can select a source without predetermining the canonical model;
3. the minimum semantic distinctions are sufficient to prevent subscription/product/authorization/Intent collapse;
4. configured and observed propositions can be qualified independently;
5. the selected source can provide real consumer-attributed request measurements with bounded coverage semantics;
6. the public answer remains question-specific and evidence-resolvable;
7. the product-value gate is measurable;
8. no unresolved decision above is being silently assumed by implementation.

---

## 37. Summary

v0.7.0 is not an API-management release. It is an Architecture Intelligence release about one new Current-State question:

> **How are APIs exposed and consumed, and what can the available evidence establish about those relationships?**

Its distinguishing requirement is to preserve what each source can actually prove:

~~~text
configured access
        !=
observed usage
        !=
authorization judgment
        !=
architectural Intent
~~~

The first implementation SHALL be grounded in one real gateway selected only after a bounded four-source survey. The release succeeds only if the resulting knowledge is semantically correct, deterministically evidence-qualified, usable through AIP's public Architecture Intelligence surface, and valuable enough to justify the source synchronization and identity-mapping cost.
