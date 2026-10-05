# AIP Semantic Gaps and Boundaries

**Status:** Working register  
**Purpose:** Consolidate semantic gaps and semantic boundaries identified through AIP validation,
landscape research, implementation reviews, and product discussions.  
**Ordering:** Grouped by status, with the most actionable **candidate semantic gaps first** and
items ordered roughly by criticality within each group.

This document is a research and product-design register, not a roadmap commitment. A candidate gap
must still be demonstrated against a real architecture question and independent evidence before it
justifies a canonical-model or release-scope change.

AIP's product mission remains:

> **Build architecture intelligence that agents can consume and humans can inspect, challenge, and understand.**

The register uses five statuses:

- **Candidate gap** — a concrete semantic capability AIP may be missing and that merits bounded
  validation.
- **Research candidate** — a plausible semantic gap or extension that is not yet demonstrated strongly
  enough to justify implementation.
- **Semantic boundary** — a distinction AIP must preserve; it should not be "solved" by collapsing
  meanings.
- **Workflow gap** — a weakness in how implementation or qualification establishes semantic
  correctness rather than in the architecture model itself.
- **Demonstrated implementation gap** — a concrete correctness gap found in implementation/review;
  these belong to implementation history rather than future semantic scope once fixed.

## 1. Candidate semantic gaps

| Priority | Area | Gap | Why it matters / qualification |
|---|---|---|---|
| **High** | Logical composition | AIP does not yet have a general source-neutral way to represent logical composition such as system → container → component or comparable nested architecture structures. | CALM/Structurizr-style sources can express composition that cannot safely be reduced to deployment or dependency relations. Any addition must preserve source meaning rather than invent a universal containment semantics. |
| **High** | Generic declared connectivity | Some architecture sources state only that one element connects to another, while AIP's canonical relations are intentionally typed (`CALLS`, `SENDS`, `RECEIVES_FROM`, etc.). | Mapping a generic connection to a typed relation would invent semantics; adding a generic edge could weaken downstream reasoning. A bounded experiment should determine whether a qualified generic-connectivity concept is useful. |
| **High** | Broker-level connectivity | Architecture models may establish connectivity through a broker without identifying the exact operation, queue, topic, or subscription required by AIP's richer messaging semantics. | AIP currently risks either rejecting useful but coarser evidence or over-interpreting it. The right semantic level needs validation against real questions. |
| **Medium** | Internal component dependencies | Sources such as Structurizr can model component-level dependencies inside a service/application, while AIP's current model is centered more strongly on service, operation, messaging, and runtime relationships. | This may matter for change-impact questions below service level, but only if independently authored systems demonstrate recurring product value. |
| **Medium** | Non-Kubernetes deployment semantics | AIP's infrastructure representation is Kubernetes-centered and does not yet provide an equivalent source-neutral model for other deployment structures. | This can limit Current-State questions for systems deployed outside Kubernetes, but a broader deployment model should be driven by real evidence rather than abstraction-first redesign. |
| **Medium** | Database connectivity | External architecture models can explicitly represent service/component → database relationships that do not map cleanly to AIP's current typed relations. | Potentially important for impact and dependency questions, but the semantics must distinguish declared access, configured connectivity, and observed database use. |

## 2. Research candidates

| Priority | Area | Candidate | Why it is not yet an implementation commitment |
|---|---|---|---|
| **High** | Structural vs semantic contract compatibility | Two API/contracts may retain the same schema while changing domain meaning, guarantees, confidence interpretation, or advisory/binding behavior. | Existing structural evidence cannot establish semantic compatibility. This is a strong future assessment question, but a concrete source model and independently authored semantic oracle are still needed. |
| **High** | Schema drift vs semantic drift | Contract-diff mechanisms can miss meaning changes that do not alter OpenAPI/JSON shape. | Closely related to the previous item; needs a bounded real-system experiment rather than a generic "semantic versioning" abstraction. |
| **High** | Capability realization traceability | Which independently identified enterprise capabilities are supported/realized by which APIs, services, processes, and interactions? | AIP must not infer capability from names or topology. A real independently authored capability model plus explicit mappings is needed before adding `BusinessCapability`-style canonical semantics. |
| **Medium** | Requirements/specification traceability | AIP does not provide general requirements → design → implementation → runtime traceability. | Potentially valuable for agentic engineering, but substantially broader than AIP's current architecture-intelligence wedge and should remain question-driven. |
| **Medium** | Historical validity and transaction time | Distinguish when an architectural statement was valid in the world from when AIP learned/recorded it. | Bitemporal work such as Tiramemsu makes the distinction concrete, but historical architecture remains beyond the current pre-v1.0 roadmap. |
| **Medium** | Correction lineage | Corrections to source facts may require traceable recomputation of derived claims while preserving independent supporting evidence. | Relevant to future historical semantics; a derivation link alone must never imply that a corrected claim had only one justification. |
| **Low** | Metagraph/tag semantics | Statement grouping, tagging, or snapshot membership may need representation without implying architectural meaning. | Useful as a future organizational/context mechanism, but not currently a demonstrated architecture question. |

## 3. Semantic boundaries AIP must preserve

These are not missing features by themselves. They are distinctions that would become semantic defects
if AIP collapsed them.

| Priority | Boundary | Required distinction |
|---|---|---|
| **Critical** | Declared vs configured vs observed vs intended | A declared relationship, gateway configuration, runtime interaction, and architectural intent may all resemble `A → B`, but establish different claims. |
| **Critical** | Identity reconciliation vs name matching | Similar names, URLs, or graph proximity do not establish identity; unresolved identity must remain unresolved. |
| **Critical** | Unresolved / not observed vs absent | Failure to reconcile or observe something is not proof that the relationship does not exist. |
| **Critical** | Intent vs Current State | ADRs, rules, promises, architecture models, and SDD specifications may establish attributable Intent but never establish runtime Current State. |
| **Critical** | Assessment vs recommendation/decision | A qualified Current↔Intent assessment does not itself establish severity, migration action, approval, or organizational decision authority. |
| **High** | API discovery vs exposure vs consumption | APIs.json/catalogues/OpenAPI discovery identify artifacts; gateway configuration can establish bounded exposure/access; runtime evidence establishes observed use. None substitutes for the others. |
| **High** | Gateway presence vs integration style | A gateway or event gateway does not establish the system-wide integration style, architecture ownership, or completeness of the integration landscape. |
| **High** | API product vs operation vs capability | API product, API contract/version, operation, application service, enterprise capability, process, deployment unit, and team are separate concepts. |
| **High** | Bounded Context vs service/deployment/team | Strategic DDD boundaries cannot be inferred from technical service, repository, deployment, or team boundaries. |
| **High** | Dynamic model/scenario vs runtime observation | Structurizr dynamic views, Arazzo workflows, sequence diagrams, and similar scenario descriptions are not observed runtime traces. |
| **High** | Representation interoperability vs semantic preservation | CALM, ArchiMate, Structurizr, SST, and other representations may project similar graph shapes while carrying different semantics. Transformation must expose approximation, loss, or unsupported meaning. |
| **High** | Common representation vs common meaning | A unified/common-domain model must not make capability, process, service, operation, deployment, and other entities interchangeable. |
| **High** | Question-specific projection vs completeness | A partial projection may be useful, but omitted relationships must not become an implicit completeness claim. |
| **High** | Human/agent moldability vs truth | Humans and agents may mold questions, selections, projections, compositions, and representations; they may not mold source evidence, claim meaning, qualification, provenance, snapshot identity, or limitations. |
| **Medium** | Observed interaction vs business outcome | Seeing an API/message interaction does not establish that an enterprise capability or business outcome was achieved. |
| **Medium** | Evidence package vs approval/accountability | AIP can assemble qualified evidence and limitations; it cannot confer organizational authority or replace accountable human decision-making. |
| **Medium** | Round-trip fidelity vs useful interoperability | Useful interoperability is about preserving distinctions required for downstream reasoning, not necessarily reproducing the original syntax byte-for-byte. |
| **Medium** | Metagraph membership vs meaning | Membership in a group/tag/context does not itself establish the semantic meaning or qualification of the contained statements. |

## 4. Workflow semantic gaps

| Priority | Gap | Proposed direction |
|---|---|---|
| **High** | Verification mapping records tests/evidence but not always the independent authority for what the expected result means. An agent can otherwise derive both implementation and test from the same mistaken interpretation. | Extend implementation planning from `acceptance criterion → test/evidence` toward `acceptance criterion → authoritative expected outcome/source → verification`. This strengthens independence without adding a new workflow phase. |
| **Medium** | Final reconciliation is agent-produced self-accounting and can be mistaken for evidence that the implementation is correct. | State explicitly that reconciliation audits claimed plan coverage and deviations; it is not independent qualification. |

## 5. Demonstrated implementation gaps / historical findings

These are concrete findings from earlier implementation and review work. They should not be mistaken
for open semantic roadmap scope once corrected.

| Priority | Historical finding | Meaning |
|---|---|---|
| **High** | Same-snapshot drill-down/evidence resolution gap | Earlier work exposed a case where evidence could not be resolved consistently under the same observation context/snapshot. This was a concrete implementation defect against snapshot-consistent semantics and was subsequently hardened. |
| **High** | Service / REST / MCP semantic parity gaps | Reviews found missing coverage proving that public surfaces preserved the same dependency/drift/evidence-resolution semantics as the service layer. This is an implementation-contract issue rather than a new architecture concept. |
| **Medium** | Error-contract precision | Cases such as malformed snapshot identifiers producing the wrong status mapping showed that public error semantics need exact regression coverage. |

## 6. Prioritization rule

AIP should not implement a candidate merely because it is semantically plausible.

Promote a **candidate gap** into roadmap/specification scope only when all of the following hold:

1. a recurring architecture question requires the missing distinction;
2. independently authored real-system evidence demonstrates the gap;
3. the existing model cannot answer safely without guessing, flattening, or silently losing meaning;
4. the proposed semantics can state what is established, unsupported, unresolved, or incomplete;
5. deterministic evaluation can distinguish a correct implementation from a plausible one.

If a problem can be solved by preserving a semantic boundary or by qualifying a source limitation,
prefer that over extending the canonical model.

## 7. Recurring pattern

Most identified gaps reduce to five recurring concerns:

1. **Meaning must survive integration.** Similar graph shapes do not imply equivalent semantics.
2. **Evidence qualification must stay explicit.** Declared, configured, observed, intended, inferred,
   unresolved, and unsupported are different states.
3. **Identity must be reconciled, never guessed.**
4. **Moldability applies to exploration, not truth.** Humans and agents may ask different questions
   over shared qualified knowledge without redefining that knowledge.
5. **Verification needs an independent authority for expected meaning.** Green tests or another agent
   agreeing are not enough when implementation and oracle share the same assumption.
