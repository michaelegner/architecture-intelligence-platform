# AIP Product Doctrine and Strategic Direction

**Status:** Working strategy — revised after semantic-boundary and roadmap-alignment review<br>
**Project:** Architecture Intelligence Platform (AIP)<br>
**Date:** 2026-09-12<br>
**Scope:** Product doctrine, target wedge, semantic model, strategic direction, and roadmap hypotheses<br>
**Current implementation center:** Evidence-qualified Current State and read-only agent context<br>
**Important:** `ROADMAP.md` now assigns planned themes to v0.6–v0.8; their detailed scope remains
subject to release-specific specifications and qualification gates.

---

## 1. Executive Summary

AIP should become the **evidence-qualified architecture knowledge layer for AI agents and engineering tools**.

Its purpose is not to make agents more autonomous. Its purpose is to give them architecture context
they do not have to reconstruct or invent.

The current product center remains:

```text
Architecture Evidence
        ↓
Evidence Applicability
        ↓
Qualified Architecture Facts
        ↓
Evidence-Qualified Current State
        ↓
Bounded Agent-Ready Context
        ↓
Agent Reasoning
```

The longer-term product thesis is now sharper, but it preserves a hard semantic separation between
Current State and Intent:

```text
CURRENT-STATE PATH

Local Evidence
      ↓
Qualified Local Evidence Assessments
      ↓
Context-Bound Current-State Projection


INTENT PATH

Explicit Attributable Intent / Promises
      ↓
Applicable Intent Projection


ASSESSMENT PATH

Current-State Projection
      +
Applicable Intent Projection
      ↓
Qualified Current ↔ Intent Assessment
```

**Intent is never an input to Current-State qualification.**

In Promise-Theory terms, AIP does not define what autonomous components should promise. It preserves
explicit, attributable promises where available and separately assesses how evidence-qualified
cooperation relates to those promises in a given locality and time.

This does **not** mean that AIP should become a central planner, policy engine, migration orchestrator,
or architecture generator.

The durable product boundary is:

> **AIP establishes what can currently be supported about architecture from available evidence,
> preserves why that conclusion was reached, relates it to explicit attributable intent where
> available, and exposes the result in a form humans and agents can safely reason from.**

AIP does not decide what an agent should do. It does not promote inferred intent into architectural
truth. It does not treat missing evidence as proof of absence. It does not prescribe a migration
procedure merely because a Current State differs from explicit intent.

---

## 2. Primary Customer Hypothesis

The initial product audience should remain explicit enough to prioritize work.

### Primary user

> **Platform engineering and architecture teams enabling coding agents to change multi-service
> systems.**

These teams need to let agents work across service boundaries without forcing the agent to reconstruct
architecture from source code, documentation, naming conventions, stale diagrams, or incomplete
telemetry.

### Secondary users

- senior software architects reviewing agent-generated changes;
- developers using coding agents in distributed systems;
- platform teams exposing architecture context through MCP or other machine interfaces;
- engineering organizations building deterministic guardrails around probabilistic development;
- teams managing long-running architecture evolution across environments, regions, and deployment
  topologies.

These remain secondary until the primary workflow is validated.

---

## 3. Initial Wedge Workflow

The first high-value workflow remains:

> **Before a coding agent changes a service, provide bounded, evidence-qualified dependency context;
> after the change is deployed or otherwise observable, independently establish the resulting
> architecture state again.**

Conceptually:

```text
Engineering task
     ↓
Agent identifies affected service(s)
     ↓
AIP: dependency / drift / evidence context
     ↓
Agent plans and changes software
     ↓
Tests / deployment / runtime evidence
     ↓
AIP reconstructs current architecture state
     ↓
Architect / agent inspects what is now established
```

AIP does **not** claim that the agent caused the resulting state merely because the state changed
after the agent's work.

Post-change verification establishes:

```text
what the architecture state is now
```

not automatically:

```text
why it changed
who caused it
whether the change was intentional
```

Causal attribution requires separate evidence.

The longer-term wedge extension is:

```text
Before change:
  establish Current State
  +
  retrieve applicable explicit intent
  +
  identify qualified difference

After change:
  re-observe
  +
  re-assess
  +
  establish the new qualified difference
```

This remains advisory and read-only.

---

## 4. Product Evolution Thesis

AIP should evolve by deepening the quality of architecture knowledge before broadening its authority.

The sequence is:

```text
1. Establish architecture facts from evidence.
2. Qualify those facts under explicit observation context.
3. Preserve provenance and derivation.
4. Establish facts locally before projecting them globally.
5. Introduce explicit attributable intent as a separate domain.
6. Assess Current State against applicable intent.
7. Represent architecture evolution as context-bound trajectories.
8. Only then consider transformation reasoning.
```

The progression deliberately separates:

```text
KNOW
what can currently be established

from

INTEND
what has explicitly been promised / required

from

ASSESS
how Current State relates to Intent

from

TRANSFORM
how the system might safely change
```

AIP should not collapse these stages into one graph or one AI-generated answer.

---

## 5. Customer Outcome Hypotheses

AIP should be evaluated against customer outcomes, not only internal semantic elegance.

The current hypotheses are:

1. **Reduce unsupported architectural assumptions before implementation.**
2. **Reduce senior-engineer time spent reconstructing cross-service architecture during review.**
3. **Make architecture questions reproducible across humans, agents, and tools.**
4. **Surface uncertainty early instead of allowing agents to convert missing context into plausible
   architecture.**
5. **Provide an independent post-change architecture check without relying on the agent's own report
   of success.**
6. **Reduce ambiguity between expected evolution and unintended architecture drift.**
7. **Allow teams to express partial architectural intent without maintaining a complete target-state
   blueprint.**
8. **Make locality- and time-specific differences visible instead of flattening them into one global
   architecture view.**

These are hypotheses to validate, not claims that AIP has already demonstrated these business
outcomes.

---

## 6. Product Success Measures

AIP needs both semantic-quality metrics and workflow-value metrics.

### 6.1 Semantic quality

Examples:

```text
false supported-claim rate
qualification disagreement rate
unresolved-identity rate
unsupported-relation rate
deterministic replay equality
evidence/provenance resolution rate
snapshot reproducibility
cross-context projection consistency
local-assessment reconciliation consistency
```

Desired direction:

```text
false supported claims -> zero in qualified scenarios
cross-surface semantic mismatches -> zero
unexplained nondeterminism -> zero
silent locality/context loss -> zero
```

### 6.2 Agent-context quality

Measure:

```text
percentage of returned claims with:
- qualification
- applicable evidence
- snapshot identity
- observation context where relevant
- locality/context scope where relevant
- explicit limitations

context truncation frequency
context completeness status
excluded/unresolved claim count
```

### 6.3 Workflow value

For pilot users, measure:

```text
time to answer "what does this service depend on?"
time spent reconstructing architecture during review
unsupported assumptions surfaced before implementation
post-change discrepancies surfaced independently
architecture-sensitive agent tasks that query AIP before acting
time to identify Current ↔ Intent differences
time to distinguish local deviation from system-wide deviation
```

Metrics should remain small enough to support actual product decisions.

---

## 7. Core Product Question

AIP's current differentiating question remains:

> **What architecture can we currently support from available evidence, and what are the limits of
> that knowledge?**

The longer-term question becomes:

> **What architecture is currently established here and now, what explicit intent applies here and
> now, and what does the evidence support about the difference?**

This is intentionally weaker and more defensible than claiming a universal architecture "truth
layer."

The preferred product term remains:

> **evidence-qualified architecture knowledge layer**

not:

> technical-architecture truth layer

---

## 8. Durable Principles

1. **Evidence before inference.**
2. **Correct but incomplete is better than complete-looking but wrong.**
3. **Non-observation is not absence.**
4. **An agent may reason over architecture, but must not become the source of architectural truth.**
5. **A relationship being present in a graph does not by itself qualify an architecture claim.**
6. **Traceability proves that a chain exists; qualification determines what that chain supports.**
7. **Different evidence modes must not be collapsed into one generic notion of truth.**
8. **Intent, declaration, and observation are distinct semantic domains.**
9. **Architectural intent is established only by explicit, attributable intent artifacts.**
10. **Inferred intent is a hypothesis, never an instruction or authoritative intent source.**
11. **Explicit promises and observed cooperation are distinct: observing cooperation does not prove
    that the cooperation was promised or intended.**
12. **A promise assessment is context-bound: whether evidence supports a promise depends on locality,
    time, observation context, applicable evidence, and the assessment rule.**
13. **Current State must be derivable entirely from current-state evidence and qualification rules;
    Intent must never be an input to Current-State establishment.**
15. **AIP establishes architecture locally before projecting it globally.**
14. **Global architecture knowledge is a context-bound projection of qualified local assessments.**
16. **Locality and connectivity are independent: WHERE something is does not establish HOW it
    interacts.**
17. **Emergent behavior may establish Current State; it does not establish Intent.**
18. **Current State and Intent may both be partial, local, and time-bound.**
19. **Desired architecture should be declarative and partial rather than encoded as a migration
    script.**
20. **Assessment must preserve evidence, context, time, rule version, provenance, and limitations.**
21. **Agent-facing convenience must not weaken deterministic semantics.**
22. **Advisory, read-only architecture intelligence is preferred over policy enforcement in the AIP
    core.**
23. **Transformation planning is downstream from qualified Current State, explicit Intent, and
    qualified difference.**

---

## 9. Epistemic Model

AIP should keep Current State, Intent, and Current↔Intent assessment on separate semantic paths.

### 9.1 Current-state evidence modes

Current State may be established only from evidence modes that describe or support the system as it
is currently declared, implemented, deployed, or observed:

```text
DECLARED
OBSERVED
SOURCE_DERIVED / IMPLEMENTATION_DERIVED
INFRASTRUCTURE_DERIVED
```

These modes may differ in authority and applicability, but all belong to the **Current-State path**.

### 9.2 Intent artifacts are a separate normative source domain

Explicit intent artifacts do **not** participate in Current-State qualification.

Examples may include:

```text
OpenAPI Overlay
AsyncAPI-compatible explicit intent artifact / extension
standalone AIP intent artifact
OpenSpec
machine-readable ADR assertion
other attributable normative specification
```

They establish candidate **Intent Assertions**, not Current-State facts.

The separation is:

```text
Current-State Evidence
        ↓
Current-State Assessment / Projection

Explicit Intent Artifact
        ↓
Intent Assertion / Intent Projection
```

Only a later advisory assessment may compare the two.

### 9.3 Current-state observation context

Current-state evidence may be scoped by:

```text
snapshot identity
environment
observation window
source revision / source observation
region
cluster / namespace
tenant
service version
deployment identity
other explicitly supported locality dimensions
```

AIP must not expose a locality dimension unless it has evidence and semantics to support it.

### 9.4 Intent applicability

Intent has its own applicability dimensions, independently of runtime observation windows:

```text
scope
environment / region / tenant / version where explicitly stated
effective_from
effective_until
source revision
authority / provenance
```

An intent effective interval and an evidence observation window may overlap, but they are never the
same field and must never be silently substituted for one another.

### 9.5 Important distinctions

```text
observed repeatedly
    ≠
intended

declared
    ≠
observed

implemented
    ≠
organizationally approved

not observed
    ≠
absent

co-located
    ≠
dependent

globally projected
    ≠
universally true

agent-inferred target
    ≠
explicit intent

current-state evidence
    ≠
intent evidence

observation window
    ≠
intent effective interval
```

---

## 10. Qualified Local Evidence Assessment

The key semantic unit for establishing Current State should be the **Qualified Local Evidence
Assessment**.

It is intentionally independent of Intent.

A conceptual form is:

```text
EvidenceAssessment(
    subject,
    assertion,
    context,
    observation_window,
    applicable_evidence,
    rule_version,
    qualification,
    provenance,
    limitations
)
```

There is **no `applicable_intent` field** in this assessment.

The governing rule is:

> **AIP qualifies what current-state evidence establishes locally before projecting it into a broader
> Current-State view.**

Example:

```text
EU / prod:
  OrderService -> PricingService
  ESTABLISHED

India / prod:
  OrderService -> LegacyPricingService
  ESTABLISHED
```

These evidence assessments can coexist without contradiction because their localities differ.

Any later question about whether either state conforms to explicit intent belongs to a separate
Current↔Intent assessment and must not alter these Current-State results.

---

## 11. Current-State Architecture Projection

A system-level Current-State view should be a deterministic projection over applicable **Qualified
Local Evidence Assessments only**.

Conceptually:

```text
CurrentState(context C, snapshot S)
    =
deterministic projection(
    applicable QualifiedLocalEvidenceAssessments
)
```

The projection must preserve:

```text
which evidence assessments contributed
which localities were included
which localities were excluded
which evidence was unresolved
which qualification / projection rules were used
whether the projection is complete
```

Intent assertions must not influence this projection.

A projection must not silently transform:

```text
"established in locality A"
```

into:

```text
"true everywhere"
```

The Current-State path is therefore:

```text
Current-State Evidence
          ↓
Qualified Local Evidence Assessment
          ↓
Current-State Architecture Projection
```

Intent remains on a separate path until an explicit advisory comparison is requested.

---

## 12. Locality, Connectivity, and Emergence

AIP should keep two structural dimensions independent:

```text
WHERE something is
        ≠
HOW it interacts
```

Examples of place/locality:

```text
region
cluster
namespace
workload
process
tenant
bounded execution context
```

Examples of connectivity/cooperation:

```text
CALLS
SENDS
RECEIVES
CONFORMS_TO
provides / accepts capability
```

AIP must not infer interaction from co-location.

AIP must not infer absence of interaction from separation.

This distinction becomes especially important with Kubernetes and broader infrastructure discovery.

### Emergent behavior

Operational architecture may emerge from local interactions even when nobody explicitly declared
the resulting global topology.

Therefore:

```text
emergent observed behavior
    -> may support Current State

emergent observed behavior
    -> does not establish Intent
```

AIP may expose higher-order emergent architecture only when the aggregation semantics are
deterministic, evidence-backed, and independently testable.

Probabilistic pattern recognition may propose a hypothesis, but must not directly create canonical
architecture truth.

---

## 13. Evidence Applicability

AIP should not assign broad authority to a source category such as "OpenTelemetry" or "Kubernetes."

Applicability should be explicit at the level of:

```text
artifact type
    ×
claim kind
    ×
mapping rule/version
    ×
context/locality applicability
```

Conceptually:

```text
OpenAPI operation
    + DIRECT_HTTP_CONTRACT claim
    + openapi.operation.v2 mapping
        -> applicable declared evidence

OTel span using supported HTTP semantic conventions
    + RUNTIME_HTTP_INTERACTION claim
    + otel.http.client.v3 mapping
        -> applicable observed evidence

Kubernetes workload identity
    + WORKLOAD_LOCALITY claim
    + kubernetes.workload.v1 mapping
        -> applicable infrastructure-derived evidence

explicit intent artifact
    + PROVIDES_CAPABILITY assertion
    + intent.promise.v1 mapping
        -> applicable intent evidence
```

AIP should ask:

> **What claim kind does this specific evidence, through this mapping rule, in this context, entitle us
> to support?**

It should not infer organizational authority, business ownership, or architectural intent merely
from technical source type.

---

## 14. Qualified Current State

AIP's current strategic center remains the Current-State path:

```text
Available Current-State Evidence
       ↓
Applicability
       ↓
Canonical Architecture Facts
       ↓
Qualified Local Evidence Assessments
       ↓
Current-State Projection
       ↓
Evidence-Qualified Current State
```

This pipeline must be executable without loading, resolving, or evaluating any Intent artifact.

Current State should preserve:

- unresolved identities;
- unsupported semantics;
- conflicting evidence;
- observation context and observation window;
- locality;
- qualification;
- provenance;
- rule versions;
- limitations;
- projection completeness.

AIP should prefer returning less information over returning a plausible-looking relation that the
evidence does not justify.

The invariant is:

> **Adding, removing, or changing an Intent artifact must not change the established Current State
> for an unchanged evidence snapshot.**

---

## 15. Explicit Intent

Agent-readiness creates pressure to add architectural intent. AIP should support this only with a
strict authority model.

The preferred separation is:

```text
WHAT CAN CURRENTLY BE ESTABLISHED?
Evidence -> Qualified Current State

WHAT HAS BEEN EXPLICITLY PROMISED / REQUIRED / INTENDED?
Explicit attributable intent artifacts -> Intent Assertions

Qualified Current State
        +
Applicable Explicit Intent
        ↓
Advisory Architecture Assessment
```

### 15.1 Intent authority rule

> **Inference may propose architectural intent; only explicit evidence may establish it.**

AIP should not establish intent from:

```text
runtime frequency
code structure
naming
co-location
probabilistic interpretation
agent-generated rationale
```

An inferred intent is a hypothesis, not an instruction.

### 15.2 Promise-oriented interpretation

Promise Theory provides a useful semantic interpretation of explicit architectural intent without
making Promise Theory itself a required AIP implementation model.

The key separation is:

```text
EXPLICIT PROMISE
what an autonomous component explicitly offers, accepts, requires, or commits to

        ≠

OBSERVED COOPERATION
what available evidence establishes that components actually did

        ≠

AIP ASSESSMENT
what that evidence supports about the relationship between promise and cooperation
in a given locality and time
```

AIP does not assign promises to autonomous components. It preserves explicit, attributable promise
artifacts where available and assesses how the observed or declared cooperation relates to those
promises.

AIP should therefore prefer statements of the form:

```text
Under context C, during time T, using evidence E and rule R,
AIP assesses promise P as qualification Q.
```

over absolute statements such as:

```text
promise P is kept
```

unless the semantics of `kept` are themselves explicitly defined and context-bound.

The corresponding doctrine rule is:

> **AIP distinguishes explicit promises from observed cooperation. Evidence may establish how
> components cooperate; only explicit attributable artifacts may establish what they intended or
> promised.**

And the strategic formulation is:

> **AIP establishes evidence-qualified cooperation independently, then separately assesses its
> relationship to explicit promises in the locality and time where those promises apply.**

### 15.3 Source-neutral intent semantics

AIP should standardize the **meaning** of architectural intent, not require every ecosystem to author
intent using the same format.

Potential carriers may include:

```text
OpenAPI Overlay
AsyncAPI x-extensions or another explicit AsyncAPI-compatible mechanism
standalone AIP intent artifacts
OpenSpec
ADRs with machine-readable explicit assertions
other versioned intent sources
```

The durable semantic layer should normalize these into source-neutral assertions such as:

```text
promise
capability offered
capability accepted
constraint
required relationship
prohibited relationship
scope
effective_from
effective_until
provenance
```

Intent applicability is independent of Current-State observation context. An intent assertion may be
effective during an interval while the Current-State evidence used to assess it comes from a
different, explicitly recorded observation window.

OpenAPI Overlay should therefore be treated as **one carrier**, not as the AIP intent model.

The absence of a standardized AsyncAPI Overlay equivalent is not a strategic blocker if AIP keeps
intent semantics source-neutral.

### 15.4 Declarative intent

Desired architecture should answer:

```text
WHAT SHOULD HOLD?
```

not:

```text
WHICH SEQUENCE OF IMPLEMENTATION STEPS MUST BE EXECUTED?
```

AIP should not require a complete future-state graph.

> **Explicit but partial intent is better than an inferred complete target architecture.**

---

## 16. Qualified Current ↔ Intent Assessment

AIP's longer-term differentiating capability is not merely "Desired State support."

It is a **separate second-order assessment** over an already-established Current State and an
independently established Intent projection.

The dependency direction is:

```text
Current-State Evidence
        ↓
Qualified Local Evidence Assessments
        ↓
Current-State Projection
                                                   +--> Current ↔ Intent Assessment
                         /
Explicit Intent Artifacts
        ↓
Applicable Intent Projection
```

Never:

```text
Intent
  ↓
Current-State qualification
```

A conceptual comparison form is:

```text
IntentAlignmentAssessment(
    current_state_ref,
    current_assessment_refs,
    intent_assertion_ref,
    evaluation_context,
    evaluated_at,

    current_observation_context: {
        observation_window,
        snapshot_id
    },

    intent_applicability: {
        effective_from,
        effective_until,
        scope
    },

    assessment_rule_version,
    qualification,
    provenance,
    limitations
)
```

The two temporal dimensions remain independent:

```text
observation_window
    = when Current-State evidence was observed

effective_from / effective_until
    = when the explicit Intent applies
```

For a given evaluation context:

```text
Current(C, S)
    =
projection of applicable Qualified Local Evidence Assessments

Intent(C, t)
    =
projection of explicit Intent Assertions applicable at t

Difference(C, S, t)
    =
qualified assessment of Current(C, S) versus Intent(C, t)
```

Possible future outcomes may distinguish:

```text
intent established
intent not yet established
explicit contradiction
conflicting evidence
unexpected observed relationship
insufficient evidence
intent not applicable in this context
```

Terms such as `expected transition` require temporal/historical semantics and are therefore deferred
until trajectory support exists.

Exact public vocabulary must be frozen only after deterministic truth tables exist.

AIP must not reduce this to generic PASS / FAIL compliance.

---

## 17. Architecture Trajectories — Beyond v1.0 Under the Current Roadmap

Architecture trajectories remain a valuable long-term concept, but they are **not part of the
pre-v1.0 roadmap under the current `ROADMAP.md`**.

The current roadmap explicitly places architecture trajectories in the unscheduled future beyond
v1.0.

A trajectory also requires capabilities that current snapshot binding does not provide.

At minimum, AIP would first need a deliberate historical-state model such as:

```text
durable historical assessment / snapshot retention or import
stable identity across historical states
historical evidence and provenance retention
versioned intent history and effective intervals
deterministic temporal ordering
trajectory continuity rules
historical query semantics
retention / compaction policy
```

Current snapshot identifiers bind answers to the current qualified state; they are not by themselves
a historical architecture store.

Only after those prerequisites exist should AIP ask:

> **How is the evidence-qualified architecture evolving relative to the explicit intent that applied
> in each context and time?**

A future trajectory capability might then distinguish:

```text
unexpected drift
expected migration phase
intent not yet realized
intent changed
local deviation
system-wide deviation
```

Until then, AIP should compare Current State with the Intent applicable to the selected evaluation
time without claiming a trajectory across historical states.

---

## 18. Distributed Local Assessment

If qualified local assessment becomes a core semantic unit, some evidence collection and
deterministic qualification may naturally move closer to the locality where the evidence has
meaning.

This is a strategic architecture candidate, not a current deployment requirement.

Conceptually:

```text
Service / Workload locality
        │
        ├── local contracts
        ├── runtime identity
        ├── telemetry
        └── deployment context
                │
                ▼
       Local Architecture Assessor
                │
                ▼
 Qualified Local Evidence Assessment
                │
                ▼
            Central AIP
                │
        reconcile / compose
                │
                ▼
    Current-State Projection

Explicit Intent remains a separate input to a later
Current ↔ Intent assessment.
```

### 18.1 Local versus global responsibility

Local assessment can answer:

```text
What can be established from evidence available here?
```

Central composition can answer:

```text
What follows when applicable local assessments are reconciled across localities?
```

The local assessor should emit assessment plus evidence lineage, not only conclusions.

### 18.2 Deployment form must remain flexible

"Local assessor" does not imply "sidecar" as the only topology.

Possible deployment forms include:

```text
sidecar
node agent
DaemonSet
OTel Collector processor / extension
local gateway
standalone local service
```

### 18.3 Failure boundary

The local assessor should not become part of the application's functional execution path.

Preferred failure mode:

```text
local assessor unavailable
    -> application continues
    -> architecture evidence / assessment for that locality degrades
```

This preserves AIP as architecture intelligence infrastructure rather than a service mesh or runtime
application dependency.

---

## 19. Derivation Lineage

Derivation lineage should be modeled as a DAG, not a linear chain.

A useful conceptual structure is:

```text
Architecture Assessment / Claim
├── Assertion
├── Applicable Evidence
│   ├── source artifact(s)
│   └── mapping rule + version
├── Applicable Intent
│   ├── explicit intent artifact(s)
│   └── intent mapping rule + version
├── Context / Locality / Time
├── Qualification Rule + Version
├── Projection Rule + Version
├── Snapshot / trajectory identity
└── Limitations
```

AIP should eventually make it possible to reconstruct:

```text
which source evidence was used
which intent artifact was used
which mapping rules interpreted them
which local assessment was produced
which qualification rule evaluated it
which context/locality/time applied
which projection rule produced a broader architecture view
which snapshot or trajectory point the answer belongs to
```

Stable rule identity/version is essential.

---

## 20. Agent-Ready Structured Context

AIP should become more agent-ready by assembling **bounded, deterministic context**, not by taking
over task reasoning.

The agent decides:

```text
what it needs to know
```

AIP decides:

```text
what the evidence and explicit intent support
```

Every returned claim or assessment must retain:

```text
qualification
applicable evidence references
applicable intent references where relevant
snapshot / trajectory identity
observation context
locality/context scope
rule version where relevant
limitations
```

The context envelope must expose completeness and truncation explicitly.

A generic unbounded graph-neighborhood dump is not an acceptable agent-context API.

---

## 21. MCP and Interface Doctrine

MCP is an adapter, not the product.

The durable product is:

```text
evidence-qualified architecture semantics
```

The MCP transport should remain as stable and boring as practical.

Future product evolution should appear primarily through typed architecture-intelligence contracts,
not repeated transport redesign.

Conceptually:

```text
MCP
│
├── Current State
│   dependencies / drift / evidence
│
├── Intent
│   applicable explicit intent
│
├── Assessment
│   qualified local assessments
│   Current ↔ Intent difference
│
└── Evolution
    trajectories across context / time
```

Exact future tool names and schemas require release-specific specifications.

All agent-facing architecture-intelligence tools should remain read-only unless AIP's product
boundary is explicitly reconsidered.

---

## 22. Reverse Verification

AIP has a useful position on both sides of an agent-generated change.

```text
Before change:
AIP establishes qualified architecture context
and, where available, applicable explicit intent
          ↓
Agent reasons and changes software
          ↓
After change:
new declared / infrastructure / runtime evidence appears
          ↓
AIP establishes the post-change architecture state
          ↓
AIP re-assesses the Current ↔ Intent difference
```

This supports independent verification.

It does not by itself establish causality.

---

## 23. Product Boundary

### AIP should own

Current and near-term core ownership:

- architecture evidence ingestion;
- canonical architecture modeling;
- evidence applicability;
- identity reconciliation;
- declared-versus-observed qualification;
- observation-context semantics;
- snapshot-bound architecture answers;
- provenance;
- derivation lineage;
- limitations and unresolved states;
- bounded deterministic architecture context.

Future, only if separately specified and validated:

- typed advisory assertion verification;
- source-neutral normalization of explicit architectural intent;
- Qualified Local Evidence Assessments as a public contract;
- locality/context applicability beyond what current evidence supports;
- advisory Current ↔ Intent assessment;
- composition of trustworthy local assessments;
- read-only agent-facing access to these semantics.

Beyond v1.0 under the current roadmap:

- historical-state persistence/import sufficient for temporal reasoning;
- architecture trajectories;
- trajectory-aware Current ↔ Intent assessment.

### AIP should not own

- agent orchestration;
- coding-agent planning;
- prompt management;
- agent memory;
- generic workflow automation;
- generic enterprise knowledge graphs;
- business capability ownership;
- policy authoring;
- approvals;
- CI enforcement;
- migration-script execution;
- deployment orchestration;
- target-state generation by an LLM;
- automatic promotion of inferred intent into authoritative intent;
- generic runtime service invocation;
- service-mesh responsibilities;
- LLM-generated architecture truth.

---

## 24. Differentiation

### Software catalogs

```text
Catalog:
maintained system metadata and relationships

AIP:
evidence-qualified architecture knowledge
with context, provenance, derivation, qualification, and limits
```

### Observability systems

```text
Observability:
what telemetry was emitted

AIP:
what architecture claims the supported telemetry
can actually establish
```

### Static architecture discovery

```text
Static discovery:
what code appears to contain or reference

AIP:
how code-derived, declared, infrastructure, and observed evidence
combine into qualified architecture knowledge
```

### Agent platforms

```text
Agent platform:
reason, plan, execute, recover

AIP:
establish architecture premises
the agent does not have to invent
```

### Governance / policy systems

```text
Governance:
intent, policy, permissions, allow/warn/block

AIP:
qualified Current State
+
applicable explicit intent
+
advisory evidence-linked assessment
```

### Desired-state / compliance tools

```text
Compliance:
compare implementation against a prescribed global target

AIP future direction:
compare context-bound established Current State
against partial, explicit, attributable intent
without requiring a complete target blueprint
```

### Knowledge graphs

```text
Knowledge graph:
connects information

AIP:
qualifies which architecture claims
the available evidence supports
and how local assessments project into broader views
```

---

## 25. Formal and Strategic Foundations

AIP may use external theories as design lenses without adopting them as implementation models.

### Promise Theory

Useful principle:

```text
autonomous agents
+
explicit promises / capabilities
+
local cooperation
+
assessment of outcomes
```

AIP relevance:

- distinguish explicit Intent from Declared and Observed evidence;
- model offered/accepted capabilities without assuming centralized control;
- support explicit partial intent rather than a globally complete target blueprint;
- distinguish promises from observed cooperation;
- assess promises contextually rather than assigning them timeless intrinsic truth states;
- preserve the rule that observed behavior does not imply intended behavior;
- provide a semantic bridge from local intent and cooperation to qualified local assessment.

AIP's preferred Promise-Theory interpretation is:

```text
explicit promises
        +
declared / observed cooperation evidence
        +
locality / time / observation context
        +
assessment rule
        ↓
qualified local assessment
```

AIP is the observer/assessor in this relationship, not the promise-maker and not necessarily the
promisee.

The product-facing implication is:

> **Architecture emerges from local promises and cooperation; AIP qualifies what the available
> evidence establishes about both.**

Promise Theory should remain a semantic foundation and design lens. AIP should not require users to
adopt Promise-Theory-specific terminology or encode the Canonical Model directly as a Promise Theory
formalism unless a concrete product need justifies it.

### Semantic Spacetime

Useful principle:

```text
architecture meaning depends on:
context
locality
time
observer / evidence perspective
```

AIP relevance:

- qualified local assessments;
- context-bound Current State;
- effective-time intent;
- architecture trajectories;
- explicit limits on global projection.

### Bigraphs

Useful principle:

```text
PLACE / LOCALITY
        ≠
LINK / CONNECTIVITY
```

AIP relevance from v0.5 onward:

- Kubernetes/locality modeling;
- clean separation between deployment structure and interaction structure;
- moving identity across locality changes;
- future architecture trajectories where place and links evolve independently, once historical-state semantics exist.

Bigraphs should remain a **design influence**, not a replacement for the Canonical Model before v1.0.

Formal Bigraphical Reactive Systems may become relevant later when AIP has a concrete transformation
problem involving valid reconfiguration and safe evolution.

### Transformation formalisms

Bigraphical Reactive Systems, process calculi, type systems, temporal logic, and confluence-related
ideas may later help answer:

```text
Given:
  Current State C
  Explicit Intent I
  Candidate Transformation T

under which conditions is T safe?
```

That is a future research problem, not a pre-v1.0 product commitment.

---

## 26. Roadmap Alignment

`ROADMAP.md` is authoritative for release sequencing and committed/planned scope. This doctrine is
**non-binding strategic guidance**.

### 26.1 Current committed/planned direction

```text
v0.4.x
Trusted Architecture Context hardening and interoperability

v0.5
Broader Architecture Discovery
- Kubernetes discovery
- broader evidence sources/adapters subject to semantic approval
- deeper runtime discovery
- reconciliation with existing declared and observed evidence

v0.6
Locality-Aware Current State

v0.7
Explicit Architecture Intent

v0.8
Qualified Architecture Assessment

v0.9
Contract Freeze / Production Qualification

v1.0
Stable Architecture Intelligence Platform

Beyond v1.0, unscheduled
Architecture trajectories and other future capabilities named by ROADMAP.md
```

v0.5 remains focused on broadening what AIP can safely know about Current State.

Bigraph-inspired `WHERE != HOW` semantics are relevant to v0.5 design, but a Bigraph implementation is
not part of the release requirement.

### 26.2 Planned v0.6–v0.8 direction and remaining hypotheses

`ROADMAP.md` now assigns the following semantic sequence to v0.6–v0.8. This doctrine explains the
strategic rationale; release-specific specifications still own exact scope and acceptance criteria.

#### v0.6 — Locality-Aware Current State

Question:

```text
What does Current-State evidence establish in this explicit locality and observation context?
```

Candidate capability:

```text
Qualified Local Evidence Assessment
context/locality preservation
deterministic Current-State projection
explicit projection completeness and limitations
```

This release theme must preserve the independence of locality and connectivity and must not require
a distributed Local Architecture Assessor deployment.

#### v0.7 — Explicit Architecture Intent

Question:

```text
What architectural intent / promises have been explicitly stated?
```

Candidate capability:

```text
source-neutral intent/assertion model
explicit provenance and authority
partial declarative intent
promise/capability semantics where useful
multiple intent carriers/adapters
```

Potential carriers may include OpenAPI Overlay, AsyncAPI-compatible explicit extensions/artifacts,
OpenSpec, and other attributable specifications.

#### v0.8 — Qualified Current ↔ Intent Assessment

Question:

```text
What does the already-established Current State imply
when compared with independently established applicable Intent?
```

Candidate capability:

```text
separate Intent projection
separate Current-State projection
deterministic comparison rules
Qualified Current ↔ Intent Assessment
evidence + intent + context + rule lineage
```

This release theme must preserve:

```text
Intent cannot influence Current-State establishment.
```

#### Unallocated hypothesis — Distributed Local Current-State Assessment

Question:

```text
Can deterministic evidence qualification move closer to the locality
where evidence has meaning without making AIP part of the functional runtime path?
```

Candidate capability:

```text
Local Architecture Assessor
Qualified Local Evidence Assessment
central reconciliation / projection
flexible deployment topology
```

This deployment hypothesis remains unallocated. It may inform a future roadmap revision only after
concrete user/system evidence and a release-specific specification justify it.

### 26.3 v0.9 implication

v0.9 freezes only the public contracts that actually exist and are intended for v1.0.

If Intent or Current↔Intent assessment has **not** been implemented and validated before v0.9, v0.9
must not freeze hypothetical contracts for those capabilities.

If such capabilities are introduced before v0.9 through an explicit roadmap change, they must be
qualified and stabilized like any other public contract.

### 26.4 Beyond v1.0: architecture trajectories

Under the current roadmap, architecture trajectories stay beyond v1.0 and unscheduled.

Before trajectory work begins, AIP needs an accepted design for historical-state
retention/import, temporal identity, provenance continuity, intent history, and temporal query
semantics.

### 26.5 Transformation hypothesis

Full transformation reasoning remains downstream of both qualified assessment and historical
evolution semantics:

```text
Current State
    +
Explicit Intent
    +
Qualified Difference
    +
Constraints
        ↓
Candidate Evolution / Transformation
        ↓
Safe / Unsafe / Unresolved
```

Formal Bigraphical Reactive Systems and other transformation formalisms are more likely to become
relevant here than in the current pre-v1.0 discovery and trusted-context roadmap.

---

## 27. Prioritization Framework

A feature should not enter the roadmap merely because it improves the internal model.

Prioritize using four gates.

### Gate A — Customer value

```text
Does this solve a recurring, high-cost architecture problem
for the primary user?
```

### Gate B — Strategic fit

```text
Does it strengthen AIP's evidence-qualified architecture context role?
```

### Gate C — Semantic defensibility

```text
Can the resulting claim semantics, uncertainty, applicability,
locality, context, and failure modes be stated independently of an LLM?
```

### Gate D — Executable validation

```text
Can the capability be evaluated deterministically
and, where appropriate, against independently authored or real-system evidence?
```

---

## 28. Near-Term Priority Order

Given the current product position, the preferred order remains:

```text
1. Preserve qualification correctness and semantic safety.
2. Complete the current agent-facing interoperability work.
3. Broaden trustworthy discovery in v0.5.
4. Keep locality and connectivity semantically independent during v0.5 design.
5. Improve reproducibility and derivation lineage.
6. Validate the pre-change architecture-context wedge with real users/agent workflows.
7. Keep any Intent work separate from Current-State establishment.
8. Deliver explicit Intent and Current↔Intent assessment only through the v0.7 and v0.8
   release-specific specifications and qualification gates; keep distributed local assessment an
   unallocated hypothesis until user and system evidence justify roadmap commitment.
9. Keep architecture trajectories beyond v1.0 unless `ROADMAP.md` is explicitly revised and the
   required historical-state prerequisites are designed first.
```

---

## 29. Product Decision Filter

For every proposed feature, ask:

1. **Who is the primary user for this capability?**
2. **What concrete job or failure mode does it address?**
3. **What measurable customer outcome should improve?**
4. **What claim, assessment, or context does AIP produce?**
5. **What exact evidence can support that output?**
6. **Which artifact type × claim kind × mapping rule defines applicability?**
7. **Which locality/context/time dimensions are actually supported?**
8. **Is the claim local, projected, or intended to be global?**
9. **If intent is involved, what explicit attributable artifact establishes it?**
10. **What happens when evidence is missing, partial, conflicting, unsupported, or local-only?**
11. **Can the semantics be stated without relying on an LLM?**
12. **Can behavior be validated deterministically?**
13. **Does the capability keep AIP advisory and read-only?**
14. **Would an integration boundary be better than AIP owning the adjacent function?**
15. **Does the feature accidentally couple AIP to one authoring format or deployment topology?**
16. **What existing roadmap item should be delayed if this enters scope?**

---

## 30. Strategic Risks

### Product broadening before wedge validation

Kubernetes, Pub/Sub, derivation, intent, assessment, and local assessors may all be
useful, but without a validated primary workflow they can become parallel attractive directions.

### Epistemic overclaiming

Calling AIP a "truth layer" would contradict its own open-world semantics.

### Silent incompleteness

Agent context that truncates, aggregates, or projects silently would undermine the trusted-context
proposition.

### False contradiction

Non-observation must never become contradiction unless an explicit closed-world rule permits that
interpretation.

### Global-truth flattening

Local assessments must not be silently promoted into universal facts.

### Static desired-state trap

AIP should not require a complete centrally authored target graph when explicit partial intent is
sufficient.

### Intent-carrier lock-in

OpenAPI Overlay, AsyncAPI extensions, OpenSpec, or another format must not become the semantic model
by accident.

### Sidecar coupling

A local-assessor architecture must not force every application to depend functionally on an AIP
sidecar.

### Governance drift

Advisory assessment must not gradually become hidden policy authoring or CI enforcement.

### Natural-language leakage into truth

Natural language may help formulate questions or hypotheses, but must not become the unverified
source of canonical facts or intent.

### Formalism creep

Promise Theory, Semantic Spacetime, Bigraphs, process calculi, and type systems are useful only when
they solve concrete AIP semantic problems.

### Transformation premature optimization

AIP should not design migration execution before Current State and any future Intent/Assessment semantics are sufficiently stable. Historical trajectory semantics remain a separate post-v1.0 prerequisite under the current roadmap.

---

## 31. Recommended Positioning

### Current short positioning

> **AIP makes evidence-qualified architecture knowledge agent-ready.**

### Current product positioning

> **AIP establishes what can currently be supported about architecture from available evidence,
> preserves how that conclusion was derived, and exposes it in a form agents can safely reason
> from.**

### Primary customer framing

> **For platform engineering and architecture teams enabling coding agents across multi-service
> systems, AIP provides bounded, evidence-qualified architecture context before a change and
> independent architecture verification afterward.**

### Boundary statement

> **AIP does not decide what an agent should do, and it does not turn inferred intent into
> architectural truth.**

### Agent-readiness statement

> **AIP is not an agent platform. It is evidence-qualified architecture infrastructure for agents.**

### Future product proposition — strategic hypothesis

> **Know what your architecture is, what it is explicitly intended to be, and where, when, and under
> which evidence that difference holds.**

This is a future proposition, not a claim about the current release.

### Promise-oriented strategic interpretation

Internally, the same proposition can be expressed as:

> **AIP shows which promises apply here and now, what cooperation is actually established by evidence,
> and where the two diverge.**

A more architectural formulation is:

> **AIP establishes evidence-qualified cooperation independently, then separately assesses its
> relationship to explicit promises in the locality and time where those promises apply.**

These formulations are useful for semantic design and strategy. They should not replace the primary
public positioning unless user research shows that Promise-Theory terminology is broadly understood
by the target audience.

---

## 32. Strategic Conclusion

The product direction remains sound, but the longer-term semantic center is now clearer.

AIP should evolve from:

```text
Evidence
   ↓
Qualified Current State
   ↓
Trusted Architecture Context
```

while preserving two independent semantic paths:

```text
Local Current-State Evidence
        ↓
Qualified Local Evidence Assessments
        ↓
Context-Bound Current-State Projection

Explicit Attributable Intent
        ↓
Applicable Intent Projection

Current-State Projection + Intent Projection
        ↓
Qualified Current ↔ Intent Assessment
```

Under the current roadmap, **Architecture Trajectories remain beyond v1.0** and require a separate
historical-state foundation before they can become a product capability.

The most important conceptual insight is:

> **AIP establishes architecture locally before projecting it globally.**

And the corresponding long-term product principle is:

> **Global architecture knowledge is a context-bound projection of qualified local assessments.**

This makes locality, time, provenance, and observer context first-class without turning AIP into a
general knowledge-representation system.

It also gives a clean division of responsibility among the theoretical influences:

```text
Promise Theory
  -> explicit local intent / promises, autonomous cooperation, promise assessment

Semantic Spacetime
  -> context, locality, time, observer perspective, trajectories

Bigraphs
  -> place versus connectivity, structural evolution

AIP
  -> evidence applicability, qualification, provenance, assessment
```

Before v1.0, these ideas should influence semantics only where they solve concrete product problems.
The Canonical Model should not be replaced wholesale by any formal theory.

The preferred strategic journey is:

```text
Broaden what AIP can safely know.
        ↓
Qualify local Current-State assertions from evidence.
        ↓
Project those assessments into contextual Current-State views.
        ↓
Validate whether explicit Intent is a valuable separate product capability.
        ↓
If justified, compare established Current State with applicable Intent.
        ↓
Freeze and production-qualify only the contracts that actually exist.
        ↓
Beyond v1.0: add historical-state foundations before trajectory reasoning.
        ↓
Only later reason about safe transformation.
```

AIP should preserve one durable center:

> **Agents should reason about architecture, not reconstruct it probabilistically on every run.**

And its deeper long-term differentiator may become:

> **AIP tells agents and engineers not only what architecture is established, but where and when that
> knowledge applies, what was explicitly intended, and what evidence supports the difference.**

In Promise-Theory terms, the same long-term differentiator is:

> **AIP tells agents and engineers which explicit promises apply, what cooperation is supported by
> evidence, and where the two align or diverge in a given locality and time.**
