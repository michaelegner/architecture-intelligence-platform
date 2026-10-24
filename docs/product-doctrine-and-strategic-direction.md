# AIP Product Doctrine and Strategic Direction

**Status:** Working product strategy  
**Project:** Architecture Intelligence Platform (AIP)  
**Distributed focus:** architecture across autonomous service/component boundaries  
**Revision:** 2026-10-24 — pivot to the binding picture: promises and qualified Current State across autonomous boundaries, and their assessment (see [Pivot status](#pivot-status))  
**Scope:** release-independent product doctrine and strategic direction  
**Roadmap authority:** release sequencing and shipped/planned status remain in [ROADMAP.md](../ROADMAP.md)

---

## 1. Product Thesis

AIP's mission remains:

> **Build architecture intelligence that agents can consume and humans can inspect, challenge, and understand.**

**dAIP — distributed Architecture Intelligence Platform** names AIP's distributed-system focus:
evidence-qualified architecture across autonomous service/component boundaries. It covers the
distributed relationships that currently exist, the promises that autonomous participants make about
them, and local assessments of the two.

The product and project name remains **AIP** throughout this document. **dAIP** is used only when the
distributed-system boundary itself is the point being emphasized.

The customer value proposition is:

> **Show who relies on what across autonomous boundaries, whether it is promised, and what the
> evidence shows, so that teams, architects and the agents that act for them can use, change or
> move a capability without reconstructing its bindings from repositories, configuration, runtime
> evidence, catalogs and people.**

The product core is the **binding picture**: for each binding across an autonomous boundary, the
promises of both sides (Intent), what the evidence establishes (Current State), and the Assessment of
the two (§4.3), with locality and time.

The central doctrine is:

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> AIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

None of the three views manufactures another. AIP composes local knowledge **only as far as needed to
answer a concrete distributed-architecture question**. It does not aim to construct or own a complete
enterprise architecture model.

The product should be judged by whether the binding picture changes a useful decision before a team
or an agent uses, changes or moves a capability across a boundary.

### Pivot status

This revision moves AIP from "distributed context for coding agents beyond source analysis" to the
binding picture. The reason is two negative results: the
[v0.7.2 checkpoint](specifications/0.7.2/i3-comparison-record.md#owner-checkpoint-i4-defer) (DEFER)
and the [v0.8 Round 7 screen](real-world-validation/v0.8.0/round7-result.md) (NOT FOUND). Both
measured whether AIP's evidence establishes relationships that source analysis cannot. Neither tested
whether a binding is promised and whether the promises and the evidence agree.

The binding picture is a working position, not proof. It must be validated with a target customer
(§8).

---

## 2. Primary Customer Job

The driver is **AI enterprise transformation**: AI-assisted modernisation (agents do migration work)
and the AI enablement of capabilities (systems are made usable by agents). Both change many
components quickly and across team boundaries. Human developers covered missing binding knowledge
with informal knowledge; agents cannot.

The users are provider teams, consumer teams, architects, and the coding agents that act for them.
Their jobs are:

> **Consumer:** Before I rely on this capability, what does its provider promise, under which
> conditions, and does the evidence show that the promise holds?

> **Provider:** Who relies on what I promised, and who relies on something I never promised?

> **Change:** Before I change or move this component, which bindings cross its boundary, what is
> promised for each, and what does the evidence show?

A coding agent is already strong at source it can inspect and behavior it can execute in its own
loop. AIP adds the attributable promises of other participants and independent evidence of the
bindings. If neither exists, AIP leaves the claim unresolved rather than replace missing
verification with plausible narration.

Typical examples include:

- an event consumed by a component in another repository or team;
- a runtime target selected by configuration, service discovery, a gateway or routing;
- an environment-specific relationship, or a declared consumer that is not live here;
- a consumer that relies on another team's data or events with no promise from the owner.

AIP does not own planning, implementation, testing, deployment, or review. It supplies qualified
distributed-architecture premises to those workflows.

---

## 3. Product Boundary: Across Autonomous Components

The core boundary test is:

> **Does this concern interaction across an autonomous service/component boundary?**

If **no**, it is probably not an AIP concern.  
If **yes**, it is potentially an AIP concern when evidence can establish the relevant relationship,
promise, or assessment.

### In scope

AIP may reason about distributed relationships such as:

- REST/HTTP and gRPC interactions;
- events, queues, topics, streams, and broker-mediated relationships;
- gateway and service-discovery relationships;
- deployment and runtime routing;
- environment-specific dependencies;
- cross-repository and cross-component interactions; and
- cross-team interactions where team identity is independently established.

It may also reason about externally visible promises and assessments of those promises when their
ownership has been validated as an AIP product responsibility.

### Out of scope as a product center

AIP should not become the primary tool for:

- classes, packages, modules, and internal layering;
- internal source dependencies or aggregate/domain-model structure;
- repository-local architecture conformance or generic code quality;
- generic enterprise architecture modeling, capability maps, or organization charts;
- generic policy authoring, approval systems, or workflow automation;
- agent orchestration; or
- deployment orchestration.

Strong source and repository architecture tools already address many of these concerns. AIP should
compose with them rather than duplicate them.

### Boundaries are not inferred from relationships

The governing invariant remains:

> **A relationship does not establish a boundary. A boundary does not establish a relationship.**

Repository, namespace, deployment co-location, graph proximity, naming, connectivity, or ownership
must not silently manufacture System/Component membership.

Likewise, membership in the same System/Component does not establish a technical relationship.

Service identity, System/Component membership, deployment locality, team ownership, and DDD Bounded
Context are distinct concepts. They may align in a real system, but that alignment itself requires
evidence or attributable intent appropriate to the claim.

A **Bounded Context** is a group of services owned by one team that share a common language. Its
membership comes from an independent, attributable source, never from who talks to whom.

---

## 4. Three Local Semantic Views

AIP's semantic frame has three distinct local views: **Current State**, **Intent**, and
**Assessment**. Together they form the binding picture. They may be projected together for a
question, but none is allowed to manufacture the others.

### 4.1 Current State is locally observed

Current State answers:

> **What distributed relationships can the available evidence establish in this explicit context?**

"Locally observed" is a product-level statement about the locality and scope of knowledge. It does
**not** collapse AIP's evidence modes. A declared API contract remains declared evidence; runtime
telemetry remains observed evidence; deployment/configuration evidence retains its own semantics.

Current-State evidence may include, where supported:

- runtime observations;
- deployment and topology evidence;
- broker configuration;
- gateway and routing configuration;
- declared API or messaging contracts;
- implementation-derived evidence; and
- explicit identity/reconciliation mappings.

Every supported conclusion remains bound to the locality, environment, observation window, version,
snapshot, and evidence semantics that justify it.

The current-state rule is:

> **An observed or configured dependency must never be promoted into a promise.**

An observed dependency is not a provider promise. A client dependency is not a provider obligation.
The existence of an API is not evidence of an approved integration contract.

A declared contract can be declared evidence (Current State) and, when attributable to its owner, a
candidate promise (Intent). The two readings stay separate.

AIP should prefer unresolved or partial answers over stronger claims that the evidence does not
support.

### 4.2 Intent is locally attributable

For AIP, useful architectural Intent is not general internal design intent.

The relevant Intent is:

> **What does an autonomous service/component explicitly promise to the outside?**

Examples include externally attributable promises about:

- an API or event contract that a component provides;
- a capability that it offers;
- a capability that it accepts or consumes;
- a supported compatibility relationship;
- a required or prohibited external relationship; and
- the scope, conditions, or effective interval of those promises.

Internal layering rules, package rules, class dependencies, repository-local architectural style, and
similar internal intent are outside AIP's product center.

A provider may promise, for example, to provide contract X under conditions Y. A consumer may
separately promise to consume or use contract X. These are distinct promises; one does not
manufacture the other.

The governing rules are:

> **A consumer dependency does not create a provider promise.**

> **Enterprise policy may constrain a distributed relationship; it does not manufacture the
> autonomous participant's promise.**

Intent must remain explicit and attributable. Runtime frequency, naming, co-location, code structure,
or an agent's interpretation cannot become authoritative Intent.

**Promisers are typed.** A Bounded Context promises at contract level: meaning, the published
contract, change and compatibility policy. A service or an intermediary (broker, gateway, platform)
promises at runtime level: availability, routing, delivery.

**Promises are captured, then confirmed.** Carriers such as code, configuration, contracts, catalogs,
ADRs and access approvals yield **candidate promises**; the owning team confirms or declines them.
Code is evidence, never a promise by itself. A guideline is an imposition until a team adopts it. A
decline is an attributable fact. Unconfirmed candidates stay visible as candidates. Meaning across
Bounded Contexts is published or translated through attributable promises, never unified.

Whether AIP should persist and own this Intent domain, or consume it from an adjacent architecture
product, is a product-ownership question. The semantic separation is mandatory either way.

### 4.3 Assessment is locally made

Assessment answers:

> **What does the available evidence support about the relationship between an autonomous
> component's external promises and the distributed interactions that actually occur?**

Assessment is not a universal compliance judgment. It is made for an explicit locality, time,
evidence set, promise set, and assessment rule.

For each binding, Assessment gives one status:

- **promised and observed:** a confirmed promise exists, and qualified evidence that covers the
  binding agrees with it;
- **promised, not observed:** a confirmed promise exists, but the evidence does not show the binding.
  Non-observation is not absence and not a failed promise;
- **contradicted:** qualified evidence contradicts an applicable promise, under an explicit
  closed-world rule only;
- **observed, not promised:** the evidence shows a binding, and the participant's promise side is
  covered but holds no confirmed promise for it, or a decline;
- **unresolved:** the evidence or the promises are insufficient. No promise coverage, or only
  candidates, is unresolved on the promise side.

Each status claims only what its evidence establishes. A consumer group's subscription to a topic,
for example, does not show which event types the consumer handles. Declared promises never fill a
gap in Current State.

DDD **Context Map patterns** describe organisational and design relationships between Bounded
Contexts. Bindings alone do not establish them; a pattern needs attributable promises about the
relationship itself, and it is then a projection, never a stored fact.

A local assessment remains attributable to its inputs and scope. Projecting several local assessments
into one answer does not turn them into universal truth.

The assessment rule is:

> **A promise must never manufacture Current State, and Current State must never manufacture a
> promise. Assessment is downstream of both.**

---

## 5. Bounded Projections

The central product interaction is a **question-specific projection** across the local views relevant
to the question.

AIP does not need a universal enterprise model before it can answer useful questions.

The preferred model starts with local evidence-qualified views, applies a specific
distributed-architecture question, and produces only the bounded projection needed to answer that
question.

Examples:

> **If Catalog Management moves to another broker, which bindings cross its boundary, and what is
> their status?**

> **Who relies on `ProductUpdatedEvent`, and is each of them covered by a promise?**

> **Which bindings between Catalog Management and Storefront are promised, and which are only
> observed?**

A projection may combine several local Current-State views, external promises, and local assessments.
The underlying claims remain local and attributable.

The governing invariant is:

> **Projection may combine local views, but it must not erase their locality, authority, provenance,
> qualification, or uncertainty.**

A projection must not silently strengthen a claim that something was **observed here** into a claim
that it is **true everywhere**. Likewise, evidence that a **consumer uses X** must not be transformed
into a claim that the **provider promised X**.

The product concept **Moldable Architecture Knowledge** is retained in this narrower sense: the same
local knowledge may support different bounded projections when different questions are asked.

Consumers may mold the question, selection, projection, composition, and representation. They may not
mold the underlying evidence, qualification, provenance, or claim meaning.

A shared knowledge store may contain evidence and promises from many systems. That is an
implementation and scale choice, not a requirement to construct a global architecture truth model.

---

## 6. Evidence Qualification Is the Core Domain

AIP's Core Domain is:

> **Establishing and projecting justified distributed architecture knowledge across autonomous
> boundaries while preserving evidence, authority, provenance, and uncertainty.**

The binding picture is the product core, and evidence qualification stays core within it. Current
State is the first and most mature path through this domain. Intent (promises) and Assessment are
distinct knowledge paths with their own attribution and qualification rules. An assessment of a
promise is only as good as the qualified evidence it is assessed against.

The durable differentiation is not the graph, database, MCP transport, or number of source adapters.
It is the ability to say what a particular body of evidence and attributable claims actually
support.

Core capabilities include:

- evidence applicability;
- identity reconciliation;
- relationship qualification;
- conflict-aware reconciliation;
- provenance and derivation lineage;
- locality, time, and observation context;
- bounded uncertainty; and
- question-specific deterministic projection.

The existing implementation concept **Qualified Local Evidence Assessment** remains compatible with
this doctrine: it is one deterministic semantic unit for saying what current-state evidence supports
within an explicit context. It is not a claim that AIP should build a complete global model from all
such assessments.

### Durable epistemic rules

1. **Evidence before inference.**
2. **Correct but incomplete is better than complete-looking but wrong.**
3. **Non-observation is not absence.**
4. **Declared is not observed.**
5. **Observed cooperation is not Intent.**
6. **Current State, Intent, and Assessment remain separate semantic paths.**
7. **An agent may reason from AIP but must not become the source of AIP knowledge.**
8. **A relationship in a graph is not qualified merely because it exists in the graph.**
9. **Locality and connectivity are independent.**
10. **A boundary and a relationship must be established independently.**
11. **Public architectural meaning is a product contract; storage representation is replaceable.**
12. **Unresolved identity, conflicting evidence, partial coverage, and unsupported semantics remain
    visible.**
13. **Question-specific projection must not strengthen its inputs silently.**
14. **AIP remains advisory and read-only by default.**

### Evidence applicability

AIP should ask:

> **What claim kind does this specific evidence, through this explicit mapping/qualification rule,
> in this context, entitle us to support?**

Authority must not be assigned merely because a source belongs to a familiar category such as
OpenTelemetry, Kubernetes, OpenAPI, AsyncAPI, a gateway, or a repository.

### Derivation and replay

For every public conclusion AIP should preserve enough information to inspect:

- the claim meaning;
- evidence references;
- identity/reconciliation decisions;
- context, locality, and time;
- the qualification rule;
- the projection rule where relevant;
- snapshot/version identity; and
- limitations.

Reproducibility is a product property of AIP's reasoning, not a claim that distributed reality itself
is repeatable:

> **Reality may change; AIP's reasoning over the same frozen evidence, context, mappings and rules
> must be reproducible.**

New evidence may establish a different Current State. Replaying an old evidence snapshot does not
prove that its conclusion is still true now; it proves that the recorded conclusion can be inspected
and reproduced from the premises that justified it.

This distinction lets agents and humans reason from the same architectural premises without turning
a transient production observation or a previous agent's narration into timeless truth.

---

## 7. Product Differentiation and Integration

### Repository/source analysis

Repository analysis is strongest at answering questions such as:

- What code depends on this code?
- Which packages, classes, or modules interact?
- Which internal architecture rule is violated?
- Which field is read here?

AIP should not compete with that.

AIP is strongest where the distributed relation is not reducible to a source dependency, for
example:

- a service reaching another service through a gateway;
- a publisher and consumer connected through a broker, topic, or queue;
- a service identity selected by environment-specific configuration;
- a runtime-only dependency;
- a cross-repository consumer; or
- a cross-component deployment relationship.

The product split is:

> **Source analysis establishes what implementations say. Direct execution establishes what the
> coding agent can verify inside its own loop. AIP establishes the binding picture across
> autonomous boundaries: attributable promises, qualified evidence, and their assessment.**

### Coding-agent execution boundary

Direct execution is strongest when the coding agent can run the relevant function, API, test, or
controlled system itself. AIP should not duplicate that verification.

AIP earns a distinct role where an important distributed fact cannot be established safely inside
the agent loop but independent external evidence exists — for example runtime telemetry, deployment
state, broker state, gateway configuration/usage, or another qualified source. Configuration or
plans may be useful partial evidence, but they must not be promoted into deployed or observed reality
without independent support.

If neither direct execution nor qualified external evidence can establish the fact, AIP should keep
it unresolved rather than fill the gap with agent-generated narration.

### Observability systems

Observability systems provide telemetry. AIP's role is to determine which distributed-architecture
claims supported telemetry can establish, with identity, context, qualification, and limitations.

### Catalogs and architecture models

Catalogs and authored architecture models may provide useful identity, composition, or declaration
evidence. They do not become global truth merely because they are curated.

AIP should preserve the semantic mode and provenance of what they contribute.

Catalogs (for example EventCatalog or Backstage), EAM tools, discovery tools and API platforms are
the main **carriers** of candidate promises and Bounded Context membership. AIP integrates with them
and does not replace them. An external integration may carry AIP's assessment back; AIP itself stays
read-only.

### Architecture-conformance tools

Mature tools such as Teamscale can be stronger at repository-internal architecture modeling,
source-code dependencies, and conformance rules.

AIP should integrate rather than duplicate those capabilities.

AIP's strategic question is whether the binding picture changes a useful decision beyond what source
analysis, direct execution, catalogs and discovery tools provide on their own.

The product risk is explicit:

> **If catalogs, platforms or discovery tools give the same binding picture at lower maintenance
> cost, AIP adds too little and should integrate, narrow or stop.**

Conversely, AIP earns a distinct role where it keeps both sides' promises apart from qualified
evidence and assesses each binding against both, across carriers and evidence sources.

### Intent and assessment ownership

The semantic frame includes Current State, Intent, and Assessment because all three matter at
distributed boundaries.

That does **not** imply AIP must own every implementation.

The preferred rule is:

> **Own evidence-qualified distributed semantics where AIP adds distinctive value; integrate where a
> mature adjacent product already owns authoring, policy, approval, or conformance.**

Product validation with a target customer decides whether AIP owns the promise domain and
Assessment, or consumes promises from an adjacent product and assesses them.

---

## 8. Product Validation

The primary validation question has two parts:

> **H1 (value):** With the binding picture, do provider teams, consumer teams and the agents that act
> for them have fewer surprises and less avoidable coordination before a safe use or change than with
> their current means, without more unsupported claims?

> **H2 (sustainability):** Can promises and Bounded Context membership be confirmed and kept current
> at an owner effort lower than the coordination they remove?

A **surprise** is a dependent, condition, owner or binding that is discovered late or after the
change. **Avoidable coordination** is a contact whose answer existed but could not be reached from
the available sources. Either hypothesis can fail, and either failure falsifies the position.

Validation needs a **target customer**: a real organisation with several teams that use each other's
capabilities. Public repositories cannot show the gap, because a binding that can be found in public
source is source-sufficient by construction. A demonstration on a public system shows that AIP can
produce the binding picture; it is not proof of product value.

The evaluation must permit a negative result. Valid outcomes are **continue**, **narrow**,
**integrate**, **defer**, or **stop**.

---

## 9. Strategic Priorities

Prefer work in this order:

1. **Demonstrate the binding picture.** Show on a realistic system that AIP can assess attributable
   promises against qualified evidence across a Bounded Context boundary, and re-establish the
   result after a change.
2. **Validate with a target customer.** Test H1 and H2 (§8) in a real organisation.
3. **Strengthen distributed Current State.** Improve evidence applicability, identity,
   reconciliation, qualification, provenance, and bounded uncertainty for relations across autonomous
   components.
4. **Strengthen promises and Assessment.** Add only the promise, membership and assessment semantics
   that concrete questions need. Integrate with carriers rather than build capture machinery that
   catalogs already own.
5. **Freeze only what survives product validation.** Stable contracts must follow evidence, not
   strategy prose.
6. **Keep historical trajectories and transformation reasoning downstream.**

A new adapter is strategically important only when it enables a materially new class of qualified
distributed relationship, a new carrier of promises, or a recurring question that AIP could not
safely answer before.

Transport, storage, graph layout, protocol libraries, and source APIs should be standardized or
consumed where practical.

---

## 10. Product Decision Filter

For a proposed capability, ask:

1. **Which autonomous boundary does this concern?**
2. **What concrete distributed-architecture question becomes safely answerable?**
3. **What customer decision changes because of the answer?**
4. **Is the output Current State, external Intent, local Assessment, or a bounded projection?**
5. **Which promise and which typed promiser does it concern, and who confirms it?**
6. **What exact evidence can establish it?**
7. **What locality, time, identity, and authority apply?**
8. **What remains unresolved when the evidence or the promises are partial?**
9. **Does it reduce surprises or avoidable coordination for a real user?**
10. **Could repository/source analysis or direct execution inside the coding-agent loop already
    answer this adequately?**
11. **Could a catalog, an EAM tool, an API platform or another adjacent product own this better?**
12. **Can the conclusion be replayed deterministically from frozen evidence, promises, context,
    mappings and rules?**
13. **Does this create a stronger claim than its inputs justify?**
14. **What maintenance cost does it introduce, and who carries it?**

If the autonomous-boundary question or changed customer decision cannot be stated clearly, the work
is probably not a new AIP product capability.

---

## 11. Strategic Risks

The principal risks are now intentionally few.

### Losing the distributed boundary

AIP becomes a generic architecture graph, catalog, source-analysis tool, or enterprise metamodel.

### Reconstructing what mature tools already do

AIP duplicates repository-internal architecture analysis, policy, or conformance instead of
integrating with it.

### Global-truth flattening

Local observations, promises, or assessments are projected into universal conclusions without
preserving locality, authority, evidence, and uncertainty.

### Relationship / boundary conflation

Connectivity manufactures membership, or membership manufactures a relationship.

### Promise / dependency conflation

Observed use, consumer desire, central policy, or a client dependency is promoted into a provider
promise.

### Too much maintenance for too little decision value

Runtime instrumentation, mapping, reconciliation, or architecture-source maintenance costs more than
the product value of the resulting distributed context.

### Promise upkeep and absorption

Confirming promises costs owners more than the coordination it removes, or providers avoid confirming
because a promise creates an obligation. AIP then becomes one more catalog of stale candidates. Or
catalogs, platforms and discovery tools add evidence and assessment themselves, and AIP's role
shrinks to an integration.

### Semantic overreach

AIP claims field-level impact, causal flow, ownership, intent, or compliance that the available
evidence does not establish.

These risks should be tested by product experiments, not only mitigated in design prose.

---

## 12. Semantic Model and Design Lenses

Promise Theory and Semantic Spacetime are the internal semantic model behind the three views.
Bigraphs and Strategic DDD remain design lenses.

### Promise Theory

Autonomous participants make local promises about their own behavior; no central authority
manufactures them. Every promise has a promiser, a promisee or scope, a body, a validity and a
carrier. A provider promise, a consumer's promise to use, an intermediary's promise and an imposition
are distinct. An external promise is not observed cooperation, and a local assessment is not central
compliance truth. Promise Theory treats an observation as an observer's assessment; AIP calls that
qualified assessment Current State and keeps the three view names.

### Semantic Spacetime

Architecture meaning depends on **context, locality, time, and evidence perspective**. Four relation
families organise AIP's model: **LEADSTO** (flow and order), **CONTAINS** (membership and
composition), **EXPRESSES** (properties, for example a capability expressed by an API or event) and
**NEAR** (similarity; SSTorytime's `SIMILARTO`). Every canonical relation is typed and qualified
inside one family; the Canonical Model stays, and the families organise it. A relation is never a
bare edge: it keeps source, time, scope, observer and qualification. NEAR is a typed,
non-authoritative hint, never identity, never established automatically.

### Bigraphs

The useful principle is that **place/composition and link/connectivity are distinct dimensions**.

This reinforces the rule that boundaries and relationships are established independently.

### Strategic DDD

Strategic DDD is useful as a boundary lens because AI makes implementation cheaper without making
domain meaning or autonomous boundaries cheaper.

The **Bounded Context** (§3) is the boundary of the binding picture, and Context Map patterns are
projections (§4.3). DDD and contract vocabulary is the language AIP uses towards users; Promise
Theory and Semantic Spacetime terms stay internal.

A **Bounded Context**, **Service**, **Repository**, and **Team** are distinct concepts. AIP should not
infer one from another. Tactical DDD and internal domain-model structure are outside the product
center.

---

## 13. Recommended Positioning

### Short positioning

> **AIP shows who relies on what across autonomous boundaries, whether it is promised, and what the
> evidence shows.**

### Product positioning

> **AIP establishes the binding picture across distributed-system boundaries: what autonomous
> participants promise to each other, what the evidence establishes, and what the evidence supports
> about the difference.**

### Customer problem

> **Teams and agents change, move or start to use capabilities across team boundaries without knowing
> who relies on them, what was promised, or whether the bindings actually hold. Human developers
> covered this gap with informal knowledge; agents cannot.**

### Product boundary

> **AIP is concerned with architecture between autonomous services/components, not architecture
> inside them.**

### Projection principle

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> AIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

### Projection invariant

> **Projection may combine local views, but it must not erase their locality, authority, provenance,
> qualification, or uncertainty.**

### Integration principle

> **Use repository/source tools for implementation internals and direct execution for behavior the
> agent can verify itself; read catalogs, contracts and platforms as carriers of promises; use AIP to
> keep promises and evidence apart and to assess each cross-boundary binding; integrate with
> specialized Intent/conformance products when they already own the adjacent concern well.**

---

## 14. Strategic Conclusion

The pivot repositions AIP. It does not broaden it.

The product is not:

- a complete enterprise architecture model;
- a catalog or an enterprise-architecture management tool;
- a source-code architecture analyzer;
- a generic knowledge graph;
- a policy engine; or
- an agent platform.

The product is the **binding picture**: local evidence-qualified Current State, attributable
promises, their local Assessment, and bounded question-specific projections, with explicit
uncertainty and provenance.

The durable center is **distributed architecture across autonomous boundaries**.

Current State, Intent, and Assessment remain distinct. **Current State** describes locally observed
distributed cooperation. **Intent** captures locally attributable external promises. **Assessment**
is a locally made evaluation of the relationship between those promises and the observed cooperation.

AIP may project several such local views to answer one bounded question, but it should not use that
ability as justification for constructing a universal enterprise architecture model.

The strongest strategic test is:

> **Does the binding picture reduce surprises and avoidable coordination for teams and agents that
> use, change or move capabilities across autonomous boundaries, at an owner effort they accept?**

If yes, AIP has a distinct product role.

If no, AIP should integrate, narrow or stop rather than add more machinery.
