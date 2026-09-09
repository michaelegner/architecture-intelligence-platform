# AIP Research Landscape

> A curated set of concepts, projects, standards, and publications relevant to the Architecture Intelligence Platform (AIP).
>
> **Purpose:** inform architecture and product decisions, identify adjacent work, and sharpen AIP's differentiation.
>
> Inclusion does not imply endorsement, dependency, or roadmap commitment. External ideas should influence AIP only where they survive AIP's own evidence, semantics, and validation requirements.

_Last reviewed: 2026-09-09_

## AIP anchor

AIP's core direction is:

```text
Evidence
   ↓
Evidence-backed Current State
   ↓
Architecture Intelligence
   ↓
Trusted Architecture Context for Agents
   ↓
Future: Intent / Governance / Transformation
```

The landscape is organized by the architectural question each source helps answer.

---

## 1. Formal and strategic foundations

These sources are not product comparisons. They are theoretical or strategic design foundations for reasoning about structure, boundaries, interaction, intent, observation, and change.

### Robin Milner — Bigraphs / Bigraphical Reactive Systems

**Primary sources**

- [Bigraphical reactive systems: basic theory](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-523.html)
- [Bigraphs and mobile processes (revised)](https://www.cl.cam.ac.uk/techreports/UCAM-CL-TR-580.html)
- [The Space and Motion of Communicating Agents](https://www.cambridge.org/core/books/space-and-motion-of-communicating-agents/267A0C3F2DB68EF43E7158DB5A7016C3)

**Core idea**

Bigraphs separate two dimensions of a system:

- **place / locality** — where components are nested or located;
- **link / connectivity** — how components communicate or relate.

Bigraphical Reactive Systems add rules for how those structures can change.

**Why this matters to AIP**

AIP may eventually need to distinguish cleanly between:

```text
WHERE something is
        ≠
HOW it interacts
```

For example, a service may be deployed in a namespace while simultaneously calling another service. This becomes increasingly relevant when AIP adds Kubernetes and other infrastructure sources. Bigraphs are also interesting for later work on architecture evolution, reconfiguration, mobility, and transformation.

**AIP stance**

Research input only. There is no reason to replace AIP's current Canonical Model with a bigraph formalism unless a concrete modeling problem justifies it.

### Mark Burgess — Promise Theory

**Primary sources**

- [Promise Theory](https://markburgess.org/promises.html)
- [Promise Theory FAQ](https://markburgess.org/promiseFAQ.html)

**Core idea**

Promise Theory models systems as autonomous agents and the promises they make about their own behavior and cooperation. It provides a language for relating **intent** to **outcome** without assuming centralized control.

**Why this matters to AIP**

Promise Theory may provide useful conceptual foundations for the future distinction between:

```text
INTENT
   ≠
DECLARED
   ≠
OBSERVED
```

A declaration says something was specified. Runtime evidence says something happened. Architectural intent expresses what agents or components are expected or permitted to do.

A Promise is not simply an ADR. ADRs, constraints, and policies are organizational artifacts; Promise Theory is a more general model of autonomous cooperation.

### Mark Burgess — Semantic Spacetime

**Primary sources**

- [Semantic Spacetimes](https://markburgess.org/spacetime.html)
- [Spacetimes with Semantics (I)](https://arxiv.org/abs/1411.5563)
- [Spacetimes with Semantics (II)](https://arxiv.org/abs/1505.01716)
- [Spacetimes with Semantics (III)](https://arxiv.org/abs/1608.02193)

**Core idea**

Semantic Spacetime treats systems as evolving discrete graphs whose topology, dynamics, semantics, locality, and observer perspective are related rather than treated as separate afterthoughts.

**Why this matters to AIP**

This is close to several long-term AIP questions around incomplete information, observation context, identity, locality, provenance, and architecture over time.

```text
Architecture(t0)
      ↓
evidence / change
      ↓
Architecture(t1)
      ↓
evidence / change
      ↓
Architecture(t2)
```

This is a natural theoretical reference for future **Architecture Trajectories**, but not a reason to expand v0.4 scope.

### Domain-Driven Design — Strategic Patterns

**Primary sources**

- [Eric Evans — Domain-Driven Design](https://www.domainlanguage.com/ddd/)
- [Martin Fowler — Bounded Context](https://martinfowler.com/bliki/BoundedContext.html)
- [Context Mapper — Strategic DDD](https://contextmapper.org/docs/strategic-ddd/)

**Core idea**

Strategic Domain-Driven Design treats semantic boundaries as first-class design decisions. Important patterns include:

- **Bounded Context** — the boundary within which a domain model and its language have a specific, consistent meaning;
- **Context Map** — explicit relationships and integration patterns between Bounded Contexts;
- **Core / Supporting / Generic Subdomains** — strategic classification of domain areas;
- relationship patterns such as **Partnership**, **Shared Kernel**, **Customer/Supplier**, **Conformist**, **Anti-Corruption Layer**, **Open Host Service**, and **Published Language**.

**Why this matters to AIP**

Technical connectivity alone does not tell us where semantic boundaries should be:

```text
TECHNICAL RELATIONSHIP
Service A ──calls──> Service B

        ≠

SEMANTIC / DOMAIN BOUNDARY
Context A ──relationship──> Context B
```

AIP should not silently equate a service, Bounded Context, deployment unit, or team boundary. They may align, but that alignment is itself an architectural claim requiring evidence or explicit intent.

Strategic DDD can therefore inform a future split between evidence-backed Current State and explicit architectural intent, without treating domain design artifacts as proof of runtime behavior.

---

## 2. Evidence and Current State

### OpenTelemetry Semantic Conventions

**Sources**

- [OpenTelemetry Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/)
- [Messaging Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/messaging/)

**Why this matters to AIP**

OpenTelemetry is a primary source of **observed evidence**. Its semantic conventions define the meaning AIP can safely attach to runtime spans, resources, operations, messaging destinations, RPCs, databases, and related signals.

AIP must not silently assign stronger architectural meaning than the telemetry semantics support.

```text
Weak or ambiguous telemetry
        ↓
qualified / unresolved result

not

weak telemetry
        ↓
plausible-looking architecture fact
```

### Backstage Software Catalog

**Sources**

- [Backstage Software Catalog](https://backstage.io/docs/features/software-catalog/)
- [Creating the Catalog Graph](https://backstage.io/docs/features/software-catalog/creating-the-catalog-graph/)

**Why this matters to AIP**

Backstage represents components, APIs, ownership, resources, and relationships in a developer-facing catalog. It is a natural integration point and an important comparison for what an architecture graph is — and is not.

```text
Backstage
human-maintained / catalog-oriented system knowledge

AIP
evidence-backed, qualified architecture knowledge
derived from declared and observed signals
```

### ProvenMap — Architecture Intelligence

**Sources**

- [Why Architecture Intelligence, Not Visualization](https://provenmap.com/blog/why-architecture-intelligence-not-visualization)
- [ProvenMap Documentation](https://provenmap.com/docs)
- [ProvenMap Intents](https://provenmap.com/docs/platform-features/intents)

**Core idea**

ProvenMap positions itself as an Architecture Intelligence platform rather than a diagramming tool: AI-assisted development changes systems faster than architects can maintain diagrams by hand, so tooling has to move from "help me illustrate what I know" toward "help me understand what I don't." Its documentation describes real sources populating an architecture model with provenance-carrying relationships, and **Intents** — living specifications of a desired change, anchored to existing architecture, that can come back **verified rather than merely reported**.

**Why this matters to AIP**

This is currently AIP's closest strategic product neighbor:

```text
ProvenMap
sources → architecture model → IS / OUGHT → intent → verification

AIP
evidence → qualified Current State → Architecture Intelligence → trusted context for agents
```

`IS vs. OUGHT` is a useful reference point for AIP's own future Current State vs. Intent split (Section 4), and `Finding → Intent → implementation → verification` is a plausible model for a future Transformation Lineage.

**AIP distinction**

Having provenance does not by itself answer AIP's sharper epistemic question:

> **What does the available evidence actually entitle us to claim?**

That is what drives AIP's explicit qualification (`CONFIRMED`, `OBSERVED_ONLY`, `NOT_OBSERVED_IN_WINDOW`) and its binding of every answer to an observation context and snapshot — a distinction that survives even where ProvenMap's provenance model overlaps with AIP's own.

### Logorythm — Architecture Intelligence from Static Analysis

**Source**

- [Logorythm](https://logorythm.io/en)

**Core idea**

Logorythm builds service maps from repositories using static analysis, with an explicit emphasis on discovering service dependencies without tracing, runtime instrumentation, or manual cross-repository investigation. This can reveal code paths that a runtime observation window has not exercised.

**Why this matters to AIP**

Logorythm is close to AIP's architecture-intelligence problem, but approaches evidence from the code side:

```text
Logorythm
code / static analysis
        ↓
service map + structural risk

AIP
declared evidence + observed evidence
        ↓
qualified architecture facts
```

The distinction is useful rather than competitive by definition. Static code evidence can answer what a system **can declare or encode as a dependency**; runtime evidence can answer what was **observed in a bounded context**. AIP's role is to preserve that distinction and qualify the resulting architectural claim rather than collapse the two into one notion of truth.

Logorythm is therefore a relevant reference for future code-discovery work, dependency extraction, structural-risk analysis, and possible adapter boundaries. It does not by itself change AIP's evidence or roadmap semantics.

### Praveen Kasam — Why Your AI Agent Fails: The Answer Is Almost Never the Model

**Source**

- [Why Your AI Agent Fails: The Answer Is Almost Never the Model](https://www.linkedin.com/pulse/why-your-ai-agent-fails-answer-almost-never-model-praveen-kasam-goaef/)

**Core idea**

Kasam argues that most agent failures trace back to the knowledge the agent reasoned over — stale, ambiguous, or incomplete premises — rather than to model capability. Reasoning quality cannot exceed the quality of what it reasons about.

**Why this matters to AIP**

This is a direct statement of AIP's founding assumption, seen from the agent-consumption side rather than the architecture side:

```text
Weak, stale, or ambiguous premise
      ↓
confident-looking but wrong conclusion

regardless of model capability
```

AIP's provenance and freshness guarantees — `source_revision`, `evidence_type`, per-service atomic reimport (no partial import ever left in the graph) — exist to keep the premises an agent reasons over evidence-backed and current, rather than merely plausible-looking. This reinforces why AIP treats provenance and qualification as architecture, not as an optional annotation.

### Spark Tsai — From Trace IDs to Trace Matrix: What Does a Change Actually Affect?

**Source**

- [From Trace IDs to Trace Matrix: What Does a Change Actually Affect?](https://www.linkedin.com/pulse/from-trace-ids-matrix-what-does-change-actually-affect-spark-tsai-u1rzc/)

**Core idea**

Tsai argues that answering "what does this change actually affect" well requires typed, structured relationships between artifacts — a trace matrix — rather than untyped trace IDs pointing at commits or tickets. Known, typed relationships let impact analysis run deterministically instead of being re-derived by an LLM each time it's asked.

**Why this matters to AIP**

```text
Known typed relationship (graph edge)
      ↓
deterministic traversal
      ↓
impact analysis

untyped reference
      ↓
LLM re-inference of the relationship, each time it's asked
      ↓
inconsistent / non-reproducible impact analysis
```

This mirrors AIP's own `PROVIDES` / `CALLS` / `SENDS` / `RECEIVES_FROM` model and the A5 blast-radius analysis: relationships are declared once, from evidence, and traversed deterministically rather than re-inferred by an LLM per question. It is also a plausible reference point for a future Intent / Transformation layer (Section 4): typed relationships between decisions and implementation would need the same discipline AIP already applies to typed relationships between services.

---

## 3. Agent context and machine consumption

### Model Context Protocol (MCP)

**Source**

- [MCP specification](https://modelcontextprotocol.io/specification/2025-06-18)

**Why this matters to AIP**

MCP gives AIP a standard mechanism for exposing architecture knowledge to agents and tools. This directly relates to the v0.4 goal:

> **Trusted Architecture Context for Agents**

AIP's differentiated value is not merely an MCP server. It is the evidence-backed semantics behind each tool result.

```text
Evidence
   ↓
Canonical Architecture Model
   ↓
ArchitectureIntelligenceService
   ↓
structured evidence-backed result
   ↓
MCP / agent
```

An agent must remain downstream of the deterministic architecture model and must not become the source of canonical architectural truth.

### Kin Lane — Agents Should Write Code to Integrate, Not Infer It at Runtime

**Source**

- [Agents Should Write Code to Integrate, Not Infer It at Runtime](https://apievangelist.com/2026/09/01/agents-should-write-code-to-integrate-not-infer/)

**Core idea**

Lane argues for a clear division between probabilistic and deterministic work: an agent is useful for ambiguous tasks like discovering capabilities and deciding what integration to build, but once a contract is understood, repeated production integration should be deterministic, reviewed, and testable — not re-interpreted by an LLM at runtime on every call.

```text
ambiguity
   ↓
inference

known contract + repeated operation
   ↓
deterministic implementation
```

**Why this matters to AIP**

The same rule applies to architecture, and is already implicit in how AIP's MCP tools above are built:

```text
sources
   ↓
deterministic evidence processing
   ↓
qualified architecture claims
   ↓
agent reasoning
```

AIP does not expose raw OpenAPI, telemetry, or arbitrary graph access and ask an LLM to infer their architectural meaning on each call — the deterministic architecture layer sits behind MCP, not inside it:

> **Do not spend probabilistic reasoning on facts and relationships that can be established deterministically.**

### UI Atlas — AI Successors

**Sources**

- [UI Atlas — GitHub repository](https://github.com/AI-Successors/ui-atlas)
- [UI Atlas — architecture documentation](https://github.com/AI-Successors/ui-atlas/blob/main/docs/architecture.md)
- [Interaction Trace documentation](https://github.com/AI-Successors/ui-atlas/blob/main/docs/interaction-trace.md)

**Core idea**

UI Atlas builds a persistent, evidence-linked representation of desktop software for computer-use agents, transforming raw observations deterministically through four retained layers:

```text
Raw Data Streams → Raw World → Semantic World → UI Knowledge Graph
```

Canonical identities deliberately exclude volatile properties (process IDs, window handles, timestamps). Its interaction model only links an observed action to an observed result state — a merely possible UI affordance never receives an invented destination, and failed, timed-out, or no-change interactions remain explicit evidence rather than being discarded.

**Why this matters to AIP**

At a different system layer, UI Atlas implements almost the same grounding discipline:

```text
UI Atlas
UI evidence → persistent evidenced UI map → computer-use agent

AIP
architecture evidence → qualified architecture model → software agent
```

The shared principle — **do not invent a relationship simply because it is plausible** — is one AIP already applies to `CALLS`/`SENDS` edges, and UI Atlas's layered raw-to-semantic transformation with retained lineage is a useful external reference for AIP's own evidence-to-claim derivation chain (Section 2).

**AIP distinction**

UI Atlas models UI states, controls, and transitions; AIP models architectural relationships and additionally reconciles distinct evidence classes (declared vs. observed). The two are complementary rather than competing.

### Thoughtworks AI/works

**Sources**

- [AI/works](https://www.thoughtworks.com/en-us/ai/works)
- [AI/works Technical Guide](https://www.thoughtworks.com/ai/works/technical-guide)
- [August 2026 V2 release](https://www.thoughtworks.com/ai/works/release/august-2026-V2-release)

**Relevant concepts**

- Code to Spec
- Dynamic / SuperSpec
- Spec to Code
- enterprise context / Knowledge Fabric
- evaluations
- Control Plane
- Runtime Operations
- continuous modernization

**Why this matters to AIP**

AI/works is a close large-scale example of an agentic development platform combining system understanding, context, modernization, generation, governance, and continuous evolution.

A useful distinction is directionality:

```text
AI/works
Code → Spec → enriched future-state context → Code

AIP
Evidence → qualified Current State
                    ↓
          trusted context for agents
```

The particularly relevant question for AIP is **reverse propagation**: after agents or developers change an implementation, how is higher-level architectural knowledge updated from real evidence without assuming the generated intent became reality?

A useful AIP distinction is:

> Context is useful. Evidence makes architecture context trustworthy.

### Nicole Königstein — AI Agents: The Definitive Guide

**Source**

- [AI Agents — The Definitive Guide repository](https://github.com/Nicolepcx/ai-agents-the-definitive-guide)

**Relevant concepts**

The open repository accompanying the O'Reilly book spans agent architectures and planning through production tool contracts, MCP, secure execution, evaluation, observability, memory, cost, and threat modeling. Particularly relevant to AIP are the examples around MCP/tool contracts, governed execution, production reliability, and deterministic evaluation harnesses.

**Why this matters to AIP**

The guide describes the engineering environment in which AIP's architecture context will be consumed:

```text
Agent system
planning · tools · MCP · governance · evaluation
                         ▲
                         │
                architecture context
                         │
                        AIP
```

Its production focus reinforces that architecture context exposed to agents needs explicit contracts, bounded tool behavior, failure semantics, evaluation, and provenance. AIP remains narrower: the agent framework determines **how an agent acts**, while AIP determines **which architecture claims are supported by evidence and how they are qualified**.

The repository is therefore useful both as an integration reference and as a source of agent-side evaluation scenarios, without making its agent architecture part of AIP itself.

### Tim O'Reilly — Why Open Source Matters for AI

**Source**

- [Why Open Source Matters for AI](https://oreillyradar.substack.com/p/why-open-source-matters-for-ai)

**Core idea**

O'Reilly argues that durable openness comes not only from licenses but from **composable architecture**: small replaceable components connected by standard interfaces and protocols. In AI, this means keeping models, agent harnesses, context, tools, memory, and skills sufficiently unbundled that one component can be replaced without rewriting the whole system. MCP is cited as an example of protocol-centric composition.

**Why this matters to AIP**

This supports an important architectural boundary for AIP:

```text
Model
  ≠
Agent harness
  ≠
Architecture context
  ≠
Tools / evidence sources
```

AIP should be useful across model and agent-framework choices. Its durable interface should be evidence-backed architecture semantics exposed through open, replaceable integration boundaries rather than coupling architectural truth to one model vendor or agent runtime.

This makes composability relevant to AIP's architecture, but not an argument for adding every adjacent agent capability. The stronger design goal is that models, harnesses, discovery adapters, and protocols can evolve independently while AIP's evidence and qualification guarantees remain explicit.

### Google Cloud — Gemini Enterprise for Financial Services

**Sources**

- [Gemini Enterprise for Financial Services](https://cloud.google.com/ai/financial-services)
- [Introducing Gemini Enterprise for Financial Services](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-for-financial-services)

**Relevant concepts**

- purpose-built reusable skills;
- secure MCP connectors to licensed and enterprise data;
- a Google-managed Financial Research agent exposed through UI and A2A APIs;
- confidence scores, explicit methodologies, auditable data snapshots, and precise source citations;
- verifiable data lineage;
- centralized governance and policy enforcement.

**Why this matters to AIP**

Gemini Enterprise for Financial Services is a concrete example of an enterprise agent platform treating **trusted context, lineage, snapshotting, source citation, and governance** as architectural capabilities rather than prompt-level concerns.

The domain differs, but the trust pattern is close:

```text
Google financial services
trusted financial data
      ↓
lineage + snapshots + citations
      ↓
agent workflows

AIP
architecture evidence
      ↓
provenance + qualification + snapshot context
      ↓
trusted architecture context for agents
```

The important distinction is semantic scope: Google is grounding financial workflows in governed domain data; AIP is concerned with what architectural claims can be supported from declared and observed software-system evidence.

Confidence scores or standardized skills should also not be confused with deterministic verification. AIP should preserve a hard boundary between probabilistic agent reasoning and evidence-backed architectural claims.

---

## 4. Architectural Intent and Governance

### Daniel Kocot — Context Is Not More Information

**Source**

- [Context Is Not More Information. It Shapes the Conditions for Interpretation and Action](https://www.linkedin.com/pulse/context-more-information-shapes-conditions-action-daniel-kocot-z55ze/)

**Core idea**

Kocot argues that context is not the amount of information supplied to a system — its usefulness depends on boundaries, relationships, authority, purpose, and relevance. Architecture artifacts (OpenAPI documents, code, diagrams) describe parts of a system but do not necessarily preserve why a boundary exists, which policy applies, or which domain gives a concept meaning. Critically: **a knowledge graph itself is not context** — it is infrastructure from which the information relevant to a particular interpretation or action can be assembled.

**Why this matters to AIP**

This sharpens AIP's own positioning:

```text
complete architecture graph
        ≠
architecture context needed for this question
```

AIP's narrow, per-question MCP tools (Section 3) are already a move in this direction — an agent receives a bounded, qualified answer, not generic Cypher access or a full graph dump:

> **The graph is infrastructure. The qualified answer is the context.**

Kocot's separation of "what exists / what does it mean / why should it exist / what is permitted" is also a useful frame for scoping this section: AIP currently answers mainly the first question and should not infer the remaining three from Current State alone.

### Mneme HQ

**Sources**

- [Mneme HQ](https://mnemehq.com/)
- [Architecture](https://mnemehq.com/architecture/)
- [Governance Benchmark](https://mnemehq.com/benchmark/)

**Core idea**

Mneme focuses on architectural governance before generation: engineering decisions and constraints are represented in a form coding agents can retrieve and enforce.

```text
Mneme
Architectural Intent
      ↓
Constraints
      ↓
GUIDE / WARN / BLOCK
      ↓
Coding Agent
```

**Relationship to AIP**

The current boundary is clean:

```text
Mneme
Intent → constraints → governance

AIP
Evidence → Current State → trusted architecture context
```

This makes Mneme especially interesting as a potentially complementary layer rather than a direct competitor.

AIP should not turn v0.4 into an architecture-governance release. First make trusted Current State safely consumable. Intent and governance can be added later or integrated with dedicated governance systems.

### O'Reilly — Architectural Guardrails for AI-Generated Code

**Source**

- [Architectural Guardrails for AI-Generated Code](https://www.oreilly.com/radar/architectural-guardrails-for-ai-generated-code/)

**Why this matters to AIP**

The article reinforces the need for architectural decisions to become machine-readable, retrievable, traceable, and enforceable when AI participates in implementation.

For AIP this suggests a future two-sided model:

```text
WHAT IS TRUE?
Evidence → Current State

WHAT SHOULD BE TRUE?
Intent → Decisions / Constraints

             ↓

Current State + Intent
             ↓
Architecture assessment / drift / governance
```

This is a future direction, not v0.4 scope.

### Alireza Rahmani Khalili — AI Did Not Eliminate Software Design

**Source**

- [AI Did Not Eliminate Software Design](https://nidly.substack.com/p/ai-did-not-eliminate-software-design)

**Core idea**

Rahmani Khalili argues that AI separates implementation from design — "design chooses constraints, implementation expresses them" — and that as implementation gets cheaper, architecture increasingly moves toward constraints, authority, boundaries, and verification. AI can produce locally coherent systems whose global architecture is worse; passing tests do not establish architectural correctness, which the article treats as a distinct concern from behavioral verification.

**Why this matters to AIP**

This supports AIP's core split between probabilistic reasoning and deterministic verification (Section 5), and explains why architecture intelligence becomes more valuable as generation gets cheaper:

```text
faster generation
      ↓
more architectural change
      ↓
less human ability to inspect every change
      ↓
explicit context + constraints + verification
```

The article's distinction between intelligence and authority mirrors AIP's own stance:

> An agent may reason about architecture, but must not become the source of architectural truth.

**AIP distinction**

The article reaches into future concepts — architectural intent, domain authority, enforceable constraints — that should stay separate from AIP's present evidence-backed Current State rather than being folded prematurely into the Canonical Model.

### Matthew Skelton — Reframing the AI-native SDLC in Terms of Stewardship Boundaries

**Source**

- [Reframing the AI-native SDLC in terms of stewardship boundaries](https://www.linkedin.com/pulse/reframing-ai-native-sdlc-terms-stewardship-boundaries-matthew-skelton-vrfpe)

**Core idea**

Skelton proposes shifting from *construction boundaries* (who builds what) to *stewardship boundaries*: which long-lived human teams remain accountable for the ongoing health, outcomes, and risk of a value flow. He draws an analogy between human cognitive load and agent context windows — both become less reliable given large, loosely bounded information — and argues reliable agentic engineering needs narrow, well-defined context and platform capabilities, illustrated by a case combining agent-assisted development with deterministic guardrails rather than prompting alone.

**Why this matters to AIP**

The context argument fits AIP's own MCP design (Section 3) directly:

```text
more architecture information
        ≠
better agent context

bounded + relevant + trustworthy architecture information
        ↓
better reasoning
```

The stewardship concept is more future-facing but relevant to this section:

```text
architecture relationship + ownership/responsibility + constraints
                    ↓
            stewardship boundary
```

> **More autonomous implementation requires stronger boundaries and independently verifiable context.**

**AIP distinction**

Organizational accountability must not be inferred from runtime connectivity. `Service`, Bounded Context, deployment unit, team, and stewardship boundary are distinct concepts; any future relationship between them needs explicit evidence or intent, echoing the same caution already stated for Strategic DDD (Section 1).

### Rachel Laycock / Martin Fowler — Code Review in an AI-heavy SDLC

**Source**

- [Maybe We Shouldn't Be Reviewing All This Code](https://martinfowler.com/rachels-ramblings/code-review.html)

**Why this matters to AIP**

As AI increases code volume, human review cannot remain the universal mechanism for knowledge sharing, architecture alignment, verification, and confidence. More decisions and checks need to move earlier or become automated, preserving human attention for judgment.

A concise AIP connection is:

> Agents need architectural constraints before they write code — and evidence afterwards that the system still follows them.

---

## 5. Verification, reliability, and observability

### Rush Shahani — Building Reliable AI Systems

**Source**

- [Building Reliable AI Systems: Applications and Agents You Can Trust](https://www.manning.com/books/building-reliable-ai-systems)

**Core idea**

Shahani organizes AI reliability into three layers:

```text
Reliable Outputs
      ↓
Reliable Agents
      ↓
Reliable Operations
```

The book covers grounding and hallucination reduction, agent architectures, tool integration and MCP, multi-agent coordination, evaluation, performance, deployment, monitoring, and responsible AI.

**Why this matters to AIP**

The book is a useful reference for the reliability requirements surrounding systems that consume AIP context. In particular, chapters 7–10 connect tool interfaces, agent workflows, evaluation, failure handling, deployment, and observability.

AIP occupies a narrower layer:

```text
Reliable agent
      +
reliable architecture context
      ↓
more trustworthy agent reasoning
```

The book's emphasis on grounding, graceful failure, source-backed answers, continuous evaluation, and monitoring aligns strongly with AIP's conservative semantics. A system should be able to say that it cannot establish an answer instead of filling gaps with plausible output.

**AIP distinction**

AIP should preserve a sharper distinction between:

```text
probabilistic evaluation
        ≠
deterministic verification
```

An LLM judge may help assess usefulness, relevance, or faithfulness. A supported architecture claim should still be reconstructable from deterministic model state, evidence, provenance, and qualification.

The book is therefore complementary rather than an architectural blueprint for AIP: it addresses AI-system reliability broadly, while AIP focuses specifically on the trustworthiness of architecture knowledge supplied to humans and agents.

### Google — Agent Evaluation and trajectory metrics

**Source**

- [agents-cli Evaluation Guide](https://google.github.io/agents-cli/guide/evaluation/)

**Core idea**

Agent evaluation should inspect the full multi-turn execution trajectory rather than only the final answer. Google's evaluation tooling exposes dedicated metrics for:

- `multi_turn_task_success` — whether the user's goal was fulfilled across the conversation;
- `multi_turn_trajectory_quality` — whether the execution path was logical, efficient, and resilient;
- `multi_turn_tool_use_quality` — technical and semantic correctness of tool calls across turns;
- hallucination and grounding checks against tool-returned or supplied context.

This separates several failure modes that can be invisible in a superficially correct final response: wrong tool selection, malformed parameters, incomplete execution, incorrect handling of tool output, or an inefficient trajectory.

**Why this matters to AIP**

Agent evaluation and AIP qualification answer complementary questions:

```text
Agent evaluation
Did the agent behave correctly?

AIP
Was the architecture context it consumed
supported by evidence and correctly qualified?
```

For v0.4, this is useful input for deterministic tool evaluation. An AIP tool result should make it possible to reconstruct which snapshot was queried, which claims were returned, what evidence supports them, and where the model returned unsupported or insufficiently evidenced results.

AIP should still distinguish trajectory evaluation from architectural verification. An LLM-as-judge metric may assess whether an agent used context well; it must not become the authority that decides whether an architecture claim is true.

### Agentic Software: How AI Agents Are Restructuring the Software Paradigm

**Source**

- [Agentic Software: How AI Agents Are Restructuring the Software Paradigm](https://arxiv.org/html/2606.05608)

**Core idea**

The paper examines context drift and verification fidelity across long-running, agent-driven software evolution, and argues for shared, observable context that multiple agents and humans can rely on across sessions rather than each agent re-deriving its own working picture of the system.

**Why this matters to AIP**

```text
single-session working context
      ↓
context drift across sessions / agents / time

evidence-backed architecture context
      ↓
stable reference point, re-derived from evidence on each import
rather than accumulated in any one agent's session state
```

AIP's graph is a candidate for exactly this durable, shared context layer: a system whose state does not drift with conversation history, because it is re-derived from declared and observed evidence on each import rather than carried forward as accumulated agent memory.

### Deterministic verification

AIP should preserve an important distinction as agent-facing features grow:

```text
AI judgment
     ≠
deterministic verification
```

Probabilistic reasoning may help formulate or interpret a question, while supported architecture claims should remain independently traceable to deterministic model state and evidence.

Mneme's benchmark methodology is relevant here because it similarly emphasizes structured outputs, reproducibility, explicit scope, and avoiding subjective LLM-as-judge grading where deterministic checks are possible.

### Lucas F. Costa — Backpressure Is All You Need

**Source**

- [Backpressure Is All You Need](https://www.lucasfcosta.com/blog/backpressure-is-all-you-need)

**Core idea**

Costa argues for shifting feedback left: deterministic, automated checks applied at planning/generation time act as backpressure on agents, catching problems before they compound, rather than relying on downstream review to catch them after the fact.

**Why this matters to AIP**

```text
agent proposes a change
      ↓
deterministic check against evidence-backed Current State
      ↓
accept / block — before the change compounds
```

This is close to AIP's own emphasis on deterministic Cypher analyses over LLM judgment (see "Deterministic verification" above). AIP's Current State graph is itself a natural backpressure signal: an agent's plan can be checked against it before code is written, not only reviewed against it afterwards.

### Agent observability

Agent observability and architecture observability are complementary but different concerns:

```text
Agent observability
What did the agent do?

Architecture observability / intelligence
What does the software system actually look like,
and what evidence supports that conclusion?
```

---

## 6. Landscape summary

| Area | Representative sources | Main question for AIP |
|---|---|---|
| Formal structure & dynamics | Milner / Bigraphs | How should locality, connectivity, and change be modeled? |
| Strategic domain boundaries | DDD strategic patterns | How should semantic boundaries and intended context relationships be represented independently from technical topology? |
| Intent & autonomous cooperation | Burgess / Promise Theory | How should architectural intent relate to observed outcome? |
| Temporal / contextual knowledge | Burgess / Semantic Spacetime | How should architecture knowledge evolve across time and observation contexts? |
| Runtime evidence | OpenTelemetry | What can runtime signals safely prove? |
| Software catalogs | Backstage | How does evidence-backed architecture intelligence differ from maintained catalog metadata? |
| Architecture intelligence product neighbor | ProvenMap | How does epistemic qualification (what evidence entitles us to claim) differ from provenance-tracked current-state modeling and Intents? |
| Static architecture discovery | Logorythm | What architectural structure can code reveal before or without runtime observation, and how should that evidence be qualified? |
| Premise quality for agent reasoning | Praveen Kasam | How much of an agent's failure traces back to stale, ambiguous, or incomplete premises rather than model capability? |
| Typed relationships & impact analysis | Spark Tsai / Trace Matrix | How should typed relationships support impact analysis without re-inferring them via an LLM each time? |
| Agent context | MCP | How should architecture facts be exposed safely to agents? |
| Deterministic vs. inferred integration | Kin Lane | Where should agent inference stop and deterministic, reviewable implementation begin for repeated tool/API operations? |
| Persistent evidenced agent representations | UI Atlas | How should raw observations be deterministically transformed into a persistent, evidence-linked knowledge layer without inventing plausible relationships? |
| Agentic development platforms | Thoughtworks AI/works | How are as-is state, enterprise context, transformation, and reverse propagation connected? |
| Production agent engineering | AI Agents — The Definitive Guide | What contracts, governance, and evaluation does the agent side need when consuming architecture context? |
| Composable AI architecture | Tim O'Reilly / open source and protocols | How can architecture context remain portable across models, agent harnesses, tools, and protocol evolution? |
| Governed domain context for agents | Google Gemini Enterprise for Financial Services | How should agents consume secure, auditable context with lineage, snapshots, citations, and governance? |
| Definition of context | Daniel Kocot | What separates a knowledge graph (infrastructure) from context (boundaries, relevance, authority, meaning)? |
| Pre-generation governance | Mneme HQ | How should machine-readable intent constrain coding agents? |
| Architecture guardrails | O'Reilly | How can decisions become enforceable without making an LLM the authority? |
| Design vs. implementation under AI | Alireza Rahmani Khalili | As implementation cost falls, how does architecture shift toward constraints, authority, and verification? |
| Stewardship boundaries | Matthew Skelton | How should long-lived accountability boundaries and bounded agent context relate to architecture ownership? |
| AI-era engineering workflow | Rachel Laycock / Martin Fowler | Which assurance work should move before or beyond human code review? |
| AI-system reliability | Shahani / Building Reliable AI Systems | Which reliability concerns belong to agents and operations, and which require independently verifiable context? |
| Agent trajectory evaluation | Google agent evaluation metrics | How should agent behavior be evaluated independently from the truth and provenance of the architecture context it consumes? |
| Long-running agentic context drift | Agentic Software paradigm paper | How should shared, observable context stay stable across long-running, drifting agent sessions? |
| Deterministic backpressure on agents | Lucas F. Costa / Backpressure | Where should deterministic checks be applied to backpressure agents before problems compound? |

---

## 7. AIP's emerging position

The sources above suggest several adjacent layers, but AIP should retain a narrow semantic center:

```text
                         ARCHITECTURAL INTENT
                       ADRs · Rules · Constraints
                                  │
                         Governance systems
                        e.g. Mneme / guardrails
                                  │
                                  ▼
                             AI AGENTS
                         Copilot · Claude · ...
                                  ▲
                                  │
                         trusted context
                                  │
                                 AIP
                    Architecture Intelligence
                                  ▲
                                  │
             ┌────────────────────┼────────────────────┐
             │                    │                    │
          DECLARED             OBSERVED            FUTURE
      OpenAPI/AsyncAPI      OpenTelemetry       K8s / code /
         manifest                               more adapters
```

AIP's differentiating question remains:

> **What architecture can we support from available evidence, and what are the limits of that knowledge?**

This leads to four durable principles:

1. **Evidence before inference.**
2. **Correct but incomplete is better than complete-looking but wrong.**
3. **Non-observation is not absence.**
4. **An agent may reason over architecture, but must not become the source of architectural truth.**

---

## 8. How to use this document

When a source appears relevant to AIP:

1. Identify the concrete AIP problem it helps illuminate.
2. Separate conceptual similarity from actual semantic equivalence.
3. Record what the source does **not** solve.
4. Test whether adopting the idea would strengthen AIP's evidence and correctness guarantees.
5. Do not add roadmap scope merely because an adjacent platform contains a feature.
6. Prefer integration boundaries over duplicated functionality when another layer already has a strong, well-defined responsibility.
7. Turn an external idea into an AIP feature only after its semantics and validation criteria can be stated independently.

The landscape should remain a **research map**, not a feature checklist.