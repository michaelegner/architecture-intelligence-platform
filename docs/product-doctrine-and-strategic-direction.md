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

The product core is the **binding picture**. For each binding across an autonomous boundary, it
holds the promises of both sides (Intent) and what the evidence establishes (Current State), with
locality and time. Their Assessment gives each binding one status:

- promised and observed;
- promised, not observed;
- observed, not promised;
- unresolved.

The durable product distinction is:

> **AIP keeps promises and evidence as separate, attributable views and assesses each
> cross-boundary binding against both, with locality, time, provenance and uncertainty preserved.**

The central doctrine is:

> **Current State is locally observed. Intent is locally attributable. Assessment is locally made.
> AIP answers distributed-architecture questions by projecting the relevant local views into a
> bounded, evidence-qualified result.**

Current State is the evidence side of the binding picture and remains core. Intent is the promise
side. Assessment relates the two. None of the three views manufactures another.

AIP composes local knowledge **only as far as needed to answer a concrete
distributed-architecture question**. It does not aim to construct or own a complete enterprise
architecture model.

The product should be judged by whether the binding picture changes a useful decision before a team
or an agent uses, changes or moves a capability across a boundary.

A concise working theorem is:

> **Source analysis tells what implementations say. Contracts and catalogs tell what participants
> declare. Runtime and platform evidence tell what happens. AIP keeps these apart, attributes them,
> and assesses each cross-boundary binding against them.**

### Pivot status

This revision moves AIP from "distributed context for coding agents beyond source analysis" to the
binding picture.

The reason is two negative results. The
[v0.7.2 checkpoint](specifications/0.7.2/i3-comparison-record.md#owner-checkpoint-i4-defer) recorded
DEFER: on Sokol111, AIP's correct answer changed no consumer set, change list or rollout gate beyond
a mature context engine. The
[v0.8 Round 7 screen](real-world-validation/v0.8.0/round7-result.md) found no real change-impact
question where boundary membership plus AIP evidence beats a fair source investigation. Both tests
measured whether AIP's evidence establishes relationships that source analysis cannot establish.
Neither tested whether a binding is promised by its participants, and whether the promises and the
evidence agree.

The binding picture is the working position. A pivot is no proof that the new position works. It
must be validated with a target customer (see [§8](#8-product-validation)). Until then, this
doctrine treats it as a hypothesis with explicit validation gates, not as an established fact.

---

## 2. Primary Customer Job

The driver is **AI enterprise transformation**:

- **AI-assisted modernisation:** agents do migration work, for example legacy modernisation,
  framework or runtime upgrades, and re-platforming;
- **AI enablement of capabilities:** systems are made usable by agents, which forces integration
  and re-platforming work.

Both change many components quickly and across team boundaries. Both depend on knowing which
bindings cross a boundary and what is agreed for them. Human developers covered that gap with
informal knowledge. Agents cannot.

The users are:

- **provider teams**, which offer capabilities to other participants;
- **consumer teams**, which rely on capabilities of other participants;
- **architects**, who need the declared and the actual bindings between Bounded Contexts; and
- **coding agents** that act for these teams.

The customer jobs are:

> **Consumer:** Before I rely on this capability, what does its provider promise, under which
> conditions, and does the evidence show that the promise holds?

> **Provider:** Who relies on what I promised, and who relies on something I never promised?

> **Change:** Before I change or move this component, which bindings cross its boundary, what is
> promised for each, and what does the evidence show?

None of these jobs is "show me the architecture." Each one asks about the bindings across one
boundary.

A coding agent is already strong at source it can inspect and behavior it can execute directly in
its own loop. AIP adds what lies outside that loop: the attributable promises of other participants
and independent evidence of the bindings. If neither exists, AIP leaves the claim unresolved rather
than replace missing verification with plausible narration.

Typical examples include:

- a service publishing an event consumed by a component in another repository;
- a raw HTTP client whose runtime target is selected by configuration or service discovery;
- gateway or routing configuration that changes which service is actually reached;
- broker topology that creates publisher/consumer relationships without a source dependency;
- environment-specific relationships that do not exist in every deployment;
- a declared consumer that is not live in this environment;
- a consumer that relies on another team's data or events with no promise from the owner.

In an organisation, two roles carry adoption. The lead of a modernisation or transformation
programme sponsors it. Enterprise architects drive it and connect it to the teams. The teams still
confirm their own promises: a promoter makes confirmation legitimate but does not author promises.

AIP does not own planning, implementation, testing, deployment, or review, whether a team or an agent
does the work. It supplies qualified distributed-architecture premises to those workflows.

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

In this doctrine a **Bounded Context** is a group of services owned by one team that share a common
language. Which services belong to which Bounded Context comes from an independent, attributable
source, for example a catalog domain or an owner's declaration. It is never inferred from who talks
to whom.

---

## 4. Three Local Semantic Views

AIP's semantic frame has three distinct local views: **Current State**, **Intent**, and
**Assessment**. Together they form the binding picture. They may be projected together for a
question, but none is allowed to manufacture the others.

### 4.1 Current State is locally observed

Current State answers:

> **What distributed relationships can the available evidence establish in this explicit context?**

Current State is the evidence side of the binding picture. Evidence qualification remains AIP's core
domain (see §6).

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

A declared contract can serve two views. As declared evidence, it is part of Current State. When it
is attributable to its owner, it is also a candidate promise in Intent (see §4.2). The two readings
stay separate, and neither strengthens the other.

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

**Promisers are typed.** A promise is made at one of two levels:

- **Bounded Context (contract level):** meaning, the published contract, and change and
  compatibility policy. The owning team makes these promises for its services, in its language.
- **Service or intermediary (runtime level):** availability, routing and delivery. Brokers,
  gateways and the platform are promisers in their own right.

**Promises are captured, then confirmed.** Carriers such as code, configuration, contracts, catalogs,
ADRs, platform documentation and access approvals yield **candidate promises**. The owning team
confirms or declines each candidate. The rules are:

- code is evidence and a source of candidates, never a promise by itself;
- an organisation's guideline is an imposition, not a promise, until a team adopts it;
- a decline is itself an attributable fact;
- unconfirmed candidates stay visible as candidates. AIP states the gap rather than hide it.

Meaning across Bounded Contexts is published by the provider or translated by the consumer, both
through attributable promises. AIP never unifies terms across contexts.

Whether AIP should persist and own this Intent domain, or consume it from an adjacent architecture
product, is a product-ownership question. The semantic separation is mandatory either way.

### 4.3 Assessment is locally made

Assessment answers:

> **What does the available evidence support about the relationship between an autonomous
> component's external promises and the distributed interactions that actually occur?**

Assessment is not a universal compliance judgment. It is made for an explicit locality, time,
evidence set, promise set, and assessment rule.

For example, Current State may establish that the Product Query service consumes the topic
`catalog.product.events` in environment E. The Catalog service may promise to publish
`ProductUpdatedEvent` on that topic, and Product Query may promise to receive it. A local Assessment
can then state whether the evidence in context C supports, contradicts, or cannot establish the
relationship between those promises and the observed cooperation.

For each binding, Assessment gives one status:

- **promised and observed:** the promises and the evidence agree;
- **promised, not observed:** a promise exists, but the evidence in this context does not show the
  binding. Non-observation is not absence;
- **observed, not promised:** the evidence shows a binding that no attributable promise covers;
- **unresolved:** the evidence or the promises are insufficient to decide.

DDD **Context Map patterns** (Partnership, Shared Kernel, Customer/Supplier, Conformist,
Anti-Corruption Layer, Open Host Service with Published Language, Separate Ways) are projections
over the promises and the qualified Current State between two Bounded Contexts. They are never stored
as facts. A declared pattern and the de-facto pattern that the promises and evidence support can
differ, and that difference is itself a useful answer.

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

> **Which Context Map pattern do the promises and the evidence support between Catalog Management
> and Storefront?**

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

Event and service catalogs (for example EventCatalog or Backstage), enterprise-architecture
management tools, migration-discovery tools and API platforms are the main **carriers** of the
declared side. They hold domains, owners, contracts, and declared producers and consumers. AIP reads
them as sources of candidate promises and Bounded Context membership, and it can write its
assessment back to them. AIP integrates with these tools; it does not replace them.

### Architecture-conformance tools

Mature tools such as Teamscale can be stronger at repository-internal architecture modeling,
source-code dependencies, and conformance rules.

AIP should integrate rather than duplicate those capabilities.

AIP's strategic question is whether the binding picture changes a useful decision beyond what source
analysis, direct execution, catalogs and discovery tools provide on their own.

The product risk is explicit:

> **If catalogs, platforms or discovery tools give the same binding picture at lower maintenance
> cost, AIP adds too little and should integrate, narrow or stop.**

Conversely, AIP earns a distinct product role where it keeps promises from both sides apart from
qualified evidence, assesses each binding against both, and preserves locality, time and
provenance across several carriers and evidence sources.

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

If H1 holds and H2 fails, AIP produces value it cannot sustain. If H2 holds and H1 fails, AIP is a
cheap map that nobody needs. Either result falsifies the position.

The terms are:

- **surprise:** a dependent, condition, owner or binding that is discovered late or after the change;
- **avoidable coordination:** a contact whose answer existed but could not be reached from the
  available sources.

Coordination is not always waste. Deliberate coordination, for example a DDD Partnership, does not
count as avoidable.

This is more important than adding another source adapter or semantic abstraction.

### What to compare

Validation needs a **target customer**: a real organisation with several teams that use each other's
capabilities. Public repositories cannot show the gap, because a binding that can be found in public
source is source-sufficient by construction.

On real tasks, compare:

- the organisation's current means: source, catalogs, discovery tools and people;
- the same, plus curated promises in the organisation's own catalog, without evidence or Assessment;
- the full binding picture.

The second condition separates AIP's contribution from the effort of curating promises. Expected
outcomes are authored independently, before the cases run.

### What to measure

- surprises and avoidable coordination;
- unsupported claims and justified unresolved answers;
- owner effort to confirm promises and keep them current;
- the share of candidates that owners confirm, decline or leave unanswered;
- the effort to produce candidates;
- setup, mapping and evidence-collection cost; and
- reuse across later questions.

A lower false-claim rate achieved only by returning almost everything unresolved is not product
success. More context is not automatically better; the answer must materially improve the next
decision.

### Product proof

The thesis is strongest when:

> **The binding picture changes a decision before a capability is used, changed or moved.**

A demonstration on a public system shows that AIP can produce the binding picture. It is not proof of
product value.

The evaluation must permit a negative result. Valid checkpoint outcomes are **continue**, **narrow**,
**integrate**, **defer**, or **stop**.

### Success criteria

AIP should demonstrate all of the following before broadening the product:

- fewer surprises at the same or lower avoidable coordination;
- no systematic increase in unsupported architectural claims;
- owner effort for promises below the coordination it removes;
- clear separation between promises, AIP evidence and source-code findings;
- evidence, promises and limitations inspectable by humans and agents;
- public conclusions reproducible from the same frozen evidence, promises, context, mappings and
  rules;
- bounded question cost as unrelated systems/evidence grow;
- maintenance cost justified by reuse and decision improvement.

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

### One more catalog to maintain

Confirming promises and keeping them current costs owners more than the coordination it removes.
AIP then becomes one more catalog that nobody keeps up to date.

### No incentive to confirm

Consumers want promises; providers often avoid them, because a confirmed promise creates an
obligation. If most providers stay silent, the binding picture holds mostly candidates.

### Absorption by adjacent products

Catalogs, API platforms, EAM tools or discovery tools add evidence and assessment to their own model,
and AIP's distinct role shrinks to an integration.

### Semantic overreach

AIP claims field-level impact, causal flow, ownership, intent, or compliance that the available
evidence does not establish.

These risks should be tested by product experiments, not only mitigated in design prose.

---

## 12. Semantic Model and Design Lenses

External theories are useful only where they sharpen the product boundary. Promise Theory and
Semantic Spacetime are the internal semantic model behind AIP's three views. Bigraphs and Strategic
DDD remain design lenses.

### Promise Theory

Autonomous participants make local promises about their own behavior. No central authority
manufactures those promises.

AIP uses Promise Theory as the model of Intent and Assessment:

- every promise has a promiser, a promisee or scope, a body, a validity, and a carrier;
- a provider promise is not a consumer desire, and a consumer's promise to use is a separate promise;
- intermediaries such as brokers, gateways and the platform make their own promises;
- an imposition, such as a central policy or guideline, is not a promise until a participant adopts
  it;
- an external promise is not observed cooperation; and
- a local promise assessment is not central compliance truth.

Promise Theory treats an observation as an assessment made by an observer. AIP's Current State is
that kind of assessment: qualified, local, and attributable to evidence. The doctrine keeps the names
Current State, Intent and Assessment for the three views; it does not introduce a second set of
terms.

### Semantic Spacetime

Architecture meaning depends on **context, locality, time, and evidence perspective**. This supports
local Current State, local Assessment, and bounded projection without claiming global truth.

AIP uses Semantic Spacetime as the organising basis of its relations:

- four relation families organise the model: **LEADSTO** (flow and order, for example an event that
  leads to a consumer's reaction), **CONTAINS** (membership and composition, for example a service in
  a Bounded Context), **EXPRESSES** (properties and expression, for example a capability expressed by
  an API, an event or a data product), and **NEAR** (similarity; SSTorytime calls this family
  `SIMILARTO`);
- every canonical relation is a typed, qualified relation inside one family. The Canonical Model
  stays; the families organise it;
- a relation is never stored as a bare edge. It keeps its source, time, scope, observer and
  qualification; and
- NEAR is a typed, non-authoritative hint. It never means identity, and it is never established
  automatically.

### Bigraphs

The useful principle is that **place/composition and link/connectivity are distinct dimensions**.

This reinforces the rule that boundaries and relationships are established independently.

### Strategic DDD

Strategic DDD is useful as a boundary lens because AI makes implementation cheaper without making
domain meaning or autonomous boundaries cheaper.

AIP uses it in three ways:

- the **Bounded Context** (§3) is the boundary of the binding picture;
- **Context Map patterns** are projections over promises and qualified Current State (§4.3); and
- DDD and contract vocabulary (contract, owner, consumer, upstream/downstream, the pattern names) is
  the language AIP uses towards users. Promise Theory and Semantic Spacetime terms stay internal.

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
