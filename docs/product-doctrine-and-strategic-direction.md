# AIP Product Doctrine and Strategic Direction

**Status:** Working product strategy  
**Project:** Architecture Intelligence Platform (AIP)  
**Product positioning:** distributed Architecture Intelligence Platform (dAIP)  
**Revision:** 2026-10-13 — complete strategy rewrite around distributed boundaries, local views, and bounded projections  
**Scope:** release-independent product doctrine and strategic direction  
**Roadmap authority:** release sequencing and shipped/planned status remain in [ROADMAP.md](../ROADMAP.md)

---

## 1. Product Thesis

AIP's mission remains:

> **Build architecture intelligence that agents can consume and humans can inspect, challenge, and understand.**

The product is increasingly best understood as **dAIP — distributed Architecture Intelligence
Platform**. The repository and project may continue to use the shorter AIP name, but the strategic
product boundary is distributed architecture.

The customer value proposition is:

> **Help coding agents make bounded changes in distributed systems without reconstructing the
> relevant architecture from repositories, configuration, runtime evidence, contracts, and people
> for every task.**

The durable product distinction is:

> **dAIP specializes in architectural relationships across autonomous service/component boundaries
> that cannot be reduced reliably to source-code dependencies.**

The central doctrine is:

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> dAIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

dAIP composes local knowledge **only as far as needed to answer a concrete
distributed-architecture question**. It does not aim to construct or own a complete enterprise
architecture model.

The product should be judged by whether this architecture context changes a useful engineering
decision before code is edited.

A concise working theorem is:

> **Distributed architecture evidence tells the agent where investigation must cross autonomous
> boundaries; repository/source analysis tells the agent what each implementation does.**

---

## 2. Primary Customer Job

The initial product wedge is **AI-assisted bounded change in existing distributed systems**.

The primary user is:

> **A developer, architect, or platform team using coding agents to change an existing distributed
> system whose relevant dependencies may cross repositories, teams, deployment boundaries, or
> independently operated components.**

The first customer job is not "show me the architecture." It is:

> **Before I change this component, which external components and distributed relationships must I
> inspect, why are they relevant, what evidence supports that relevance, and what remains unknown?**

A repository-aware coding agent is already good at reading code that it can see. AIP should add value
where the investigation boundary is larger than that repository.

Typical examples include:

- a service publishing an event consumed by a component in another repository;
- a raw HTTP client whose runtime target is selected by configuration or service discovery;
- gateway or routing configuration that changes which service is actually reached;
- broker topology that creates publisher/consumer relationships without a source dependency;
- environment-specific relationships that do not exist in every deployment;
- deployment/runtime relationships that source analysis cannot establish safely.

For a bounded change, the agent should first ask the relevant distributed-impact question. dAIP
returns a bounded projection that identifies which autonomous boundaries require inspection. The
agent then uses repository/source analysis inside each relevant component and continues with the
normal engineering verification workflow.

AIP does not own coding-agent planning, implementation, testing, deployment, or review. It supplies
qualified distributed-architecture premises to those workflows.

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

---

## 4. Three Local Semantic Views

dAIP's long-term semantic frame has three distinct local views: **Current State**, **Intent**, and
**Assessment**. They may be projected together for a question, but none is allowed to manufacture
the others.

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

Whether AIP should persist and own this Intent domain, or consume it from an adjacent architecture
product, is a product-ownership question. The semantic separation is mandatory either way.

### 4.3 Assessment is locally made

Assessment answers:

> **What does the available evidence support about the relationship between an autonomous
> component's external promises and the distributed interactions that actually occur?**

Assessment is not a universal compliance judgment. It is made for an explicit locality, time,
evidence set, promise set, and assessment rule.

For example, Current State may establish that `WorkshopManagementAPI` publishes on distributed
path P. An independently attributable Intent may state that `WorkshopManagementAPI` promises
external contract X. A local Assessment can then state whether the evidence in context C supports,
contradicts, or cannot establish the relevant relationship between X and the observed cooperation.

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

> **Which external dependencies of WorkshopManagementAPI matter for this change?**

> **Which observed relationships cross the Pitstop → Reporting component boundary?**

> **Which external promises relevant to MaintenanceJobFinished are supported, conflicting, or
> unresolved in this context?**

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

A shared knowledge store may contain evidence from many systems. That is an implementation and scale
choice, not a requirement to construct a global architecture truth model.

---

## 6. Evidence Qualification Is the Core Domain

AIP's Core Domain is now stated more narrowly as:

> **Establishing and projecting evidence-qualified distributed relationships across autonomous
> boundaries.**

The durable differentiation is not the graph, database, MCP transport, or number of source adapters.
It is the ability to say what a particular body of evidence actually supports.

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

Deterministic replay is valuable because agents and humans should be able to reason from the same
architectural premises.

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

> **AIP establishes where distributed investigation must cross autonomous boundaries. Source
> analysis establishes what each implementation does.**

### Observability systems

Observability systems provide telemetry. AIP's role is to determine which distributed-architecture
claims supported telemetry can establish, with identity, context, qualification, and limitations.

### Catalogs and architecture models

Catalogs and authored architecture models may provide useful identity, composition, or declaration
evidence. They do not become global truth merely because they are curated.

AIP should preserve the semantic mode and provenance of what they contribute.

### Architecture-conformance tools

Mature tools such as Teamscale can be stronger at repository-internal architecture modeling,
source-code dependencies, and conformance rules.

AIP should integrate rather than duplicate those capabilities.

AIP's strategic question is whether evidence-qualified distributed Current State changes the
investigation boundary beyond what strong source/repository analysis already provides.

The product risk is explicit:

> **If a mature source/architecture tool at realistic multi-repository scope produces the same useful
> investigation boundary at lower maintenance cost, AIP adds too little and should narrow or stop.**

Conversely, AIP earns a distinct product role where runtime, deployment, gateway, broker, contract, or
other independent evidence establishes distributed relationships that source analysis cannot safely
recover.

### Intent and assessment ownership

The semantic frame includes Current State, Intent, and Assessment because all three matter at
distributed boundaries.

That does **not** imply AIP must own every implementation.

The preferred rule is:

> **Own evidence-qualified distributed semantics where AIP adds distinctive value; integrate where a
> mature adjacent product already owns authoring, policy, approval, or conformance.**

The roadmap checkpoint decides whether AIP-owned external Intent and Assessment add enough value to
justify separate product capabilities.

---

## 8. Product Validation

The primary validation question is:

> **When a coding agent is about to make a bounded change in an existing distributed system, does
> AIP materially improve the agent's next decision beyond repository/source analysis and a strong
> architecture-analysis tool?**

This is more important than adding another source adapter or semantic abstraction.

### What to compare

A useful evaluation compares four conditions:

- baseline repository/source analysis;
- a strong architecture-analysis tool;
- AIP distributed evidence; and
- the combined workflow.

For enterprise-scale source-analysis comparisons, do not artificially hide repositories from the
baseline. If a tool can analyze multiple repositories in one project, let it do so.

AIP must still demonstrate additional value from evidence that is genuinely outside or orthogonal to
source dependencies.

### What to measure

Measure the resulting change plan and investigation boundary in terms of:

- relevant external investigation targets found;
- unsupported targets introduced;
- whether established facts remain separate from inference;
- missing source/code requests identified;
- distributed risks discovered before editing;
- questions left explicitly unresolved;
- setup and maintenance effort;
- identity/mapping maintenance cost;
- evidence collection/instrumentation cost; and
- reuse across later questions.

A lower false-claim rate achieved only by returning almost everything unresolved is not product
success. More context is not automatically better; the answer must materially improve the next
decision.

### Product proof

The current product thesis is strongest when:

> **Architecture context changes the next action before code is edited.**

A realistic distributed evaluation should include at least one relevant component outside the
repository being changed and should establish that component through independent distributed-system
evidence such as telemetry, broker topology, gateway/routing configuration, deployment identity, or
another qualified source.

The evaluation must permit a negative result. Valid checkpoint outcomes are **continue**, **narrow**,
**integrate**, **defer**, or **stop**.

### Success criteria

AIP should demonstrate all of the following before broadening the product:

- materially better discovery of relevant cross-boundary investigation targets;
- no systematic increase in unsupported architectural claims;
- clear separation between AIP evidence and source-code findings;
- evidence and limitations inspectable by humans and agents;
- bounded question cost as unrelated systems/evidence grow;
- maintenance cost justified by reuse and decision improvement.

---

## 9. Strategic Priorities

Prefer work in this order:

1. **Prove the distributed product boundary.** Show that cross-repository/runtime/deployment evidence
   changes useful engineering decisions beyond source analysis.
2. **Strengthen distributed Current State.** Improve evidence applicability, identity,
   reconciliation, qualification, provenance, and bounded uncertainty for relations across autonomous
   components.
3. **Support bounded cross-boundary projections.** Add only the System/Component membership semantics
   required to answer concrete distributed questions.
4. **Validate external Intent as promises, not generic policy.** If owned by AIP, focus on explicit,
   attributable promises to the outside.
5. **Validate local Assessment.** Compare externally relevant promises with distributed interactions
   without turning AIP into a centralized compliance engine.
6. **Freeze only what survives product validation.** Stable contracts must follow evidence, not
   strategy prose.
7. **Keep historical trajectories and transformation reasoning downstream.**

A new adapter is strategically important only when it enables a materially new class of qualified
distributed relationship or a recurring question that AIP could not safely answer before.

Transport, storage, graph layout, protocol libraries, and source APIs should be standardized or
consumed where practical.

---

## 10. Product Decision Filter

For a proposed capability, ask:

1. **Which autonomous boundary does this concern?**
2. **What concrete distributed-architecture question becomes safely answerable?**
3. **What customer decision changes because of the answer?**
4. **Is the output Current State, external Intent, local Assessment, or a bounded projection?**
5. **What exact evidence can establish it?**
6. **What locality, time, identity, and authority apply?**
7. **What remains unresolved when the evidence is partial?**
8. **Could repository/source analysis already answer this adequately?**
9. **Could an adjacent architecture product own this better?**
10. **Can the semantics and qualification be evaluated deterministically?**
11. **Does this create a stronger claim than its inputs justify?**
12. **What maintenance cost does it introduce?**

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

### Semantic overreach

AIP claims field-level impact, causal flow, ownership, intent, or compliance that the available
evidence does not establish.

These risks should be tested by product experiments, not only mitigated in design prose.

---

## 12. Strategic Design Lenses

External theories are useful only where they sharpen the product boundary.

### Promise Theory

Promise Theory is useful because autonomous components can make local promises without requiring a
central authority to manufacture those promises.

AIP uses Promise Theory to preserve three distinctions:

- a provider promise is not a consumer desire;
- an external promise is not observed cooperation; and
- a local promise assessment is not central compliance truth.

Promise Theory is a semantic/evaluation lens, not a required implementation model or user-facing
vocabulary.

### Semantic Spacetime

The useful principle is that architecture meaning depends on **context, locality, time, and evidence
perspective**.

This supports local Current State, local Assessment, and bounded projection without claiming global
truth.

### Bigraphs

The useful principle is that **place/composition and link/connectivity are distinct dimensions**.

This reinforces the rule that boundaries and relationships are established independently.

### Strategic DDD

Strategic DDD is useful as a boundary lens because AI makes implementation cheaper without making
domain meaning or autonomous boundaries cheaper.

However, a **Bounded Context**, **Service**, **Repository**, and **Team** are distinct concepts. AIP
should not infer one from another. Tactical DDD and internal domain-model structure are outside
the product center.

---

## 13. Recommended Positioning

### Short positioning

> **AIP gives coding agents evidence-qualified context about distributed dependencies they cannot
> safely reconstruct from the repository alone.**

### Product positioning

> **dAIP establishes evidence-qualified architecture across distributed-system boundaries: what
> relationships currently exist, what autonomous components promise externally, and what the
> evidence supports about the difference.**

### Customer problem

> **A coding agent can understand the repository and still miss a relevant service, event consumer,
> gateway route, broker relationship, or environment-specific dependency outside it.**

### Product boundary

> **AIP is concerned with architecture between autonomous services/components, not architecture
> inside them.**

### Projection principle

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> dAIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

### Projection invariant

> **Projection may combine local views, but it must not erase their locality, authority, provenance,
> qualification, or uncertainty.**

### Integration principle

> **Use AIP for evidence-qualified distributed relationships; use repository/source tools for
> implementation internals; integrate with specialized Intent/conformance products when they already
> own the adjacent concern well.**

---

## 14. Strategic Conclusion

AIP should become narrower, not broader.

The product is not:

- a complete enterprise architecture model;
- a source-code architecture analyzer;
- a generic knowledge graph;
- a policy engine; or
- an agent platform.

The product combines **local evidence-qualified distributed views**, **bounded question-specific
projections**, and **explicit uncertainty and provenance**.

The durable center is **distributed architecture across autonomous boundaries**.

Current State, Intent, and Assessment remain distinct. **Current State** describes locally observed
distributed cooperation. **Intent** captures locally attributable external promises. **Assessment**
is a locally made evaluation of the relationship between those promises and the observed cooperation.

AIP may project several such local views to answer one bounded question, but it should not use that
ability as justification for constructing a universal enterprise architecture model.

The strongest strategic test remains simple:

> **Does this architecture intelligence change what a developer or coding agent needs to inspect
> before making a distributed-system change, beyond what repository/source analysis already tells
> them?**

If yes, AIP has a distinct product role.

If no, the strategy should narrow rather than add more machinery.
