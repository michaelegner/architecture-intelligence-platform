# AIP Research Landscape

> A curated set of concepts, projects, standards, and publications relevant to the Architecture Intelligence Platform (AIP).
>
> **Purpose:** inform architecture and product decisions, identify adjacent work, and sharpen AIP's differentiation.
>
> Inclusion does not imply endorsement, dependency, or roadmap commitment. External ideas should influence AIP only where they survive AIP's own evidence, semantics, and validation requirements.

_Last reviewed: 2026-09-04_

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

### Deterministic verification

AIP should preserve an important distinction as agent-facing features grow:

```text
AI judgment
     ≠
deterministic verification
```

Probabilistic reasoning may help formulate or interpret a question, while supported architecture claims should remain independently traceable to deterministic model state and evidence.

Mneme's benchmark methodology is relevant here because it similarly emphasizes structured outputs, reproducibility, explicit scope, and avoiding subjective LLM-as-judge grading where deterministic checks are possible.

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
| Agent context | MCP | How should architecture facts be exposed safely to agents? |
| Agentic development platforms | Thoughtworks AI/works | How are as-is state, enterprise context, transformation, and reverse propagation connected? |
| Governed domain context for agents | Google Gemini Enterprise for Financial Services | How should agents consume secure, auditable context with lineage, snapshots, citations, and governance? |
| Pre-generation governance | Mneme HQ | How should machine-readable intent constrain coding agents? |
| Architecture guardrails | O'Reilly | How can decisions become enforceable without making an LLM the authority? |
| AI-era engineering workflow | Rachel Laycock / Martin Fowler | Which assurance work should move before or beyond human code review? |
| AI-system reliability | Shahani / Building Reliable AI Systems | Which reliability concerns belong to agents and operations, and which require independently verifiable context? |
| Agent trajectory evaluation | Google agent evaluation metrics | How should agent behavior be evaluated independently from the truth and provenance of the architecture context it consumes? |

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
