# AIP × Glamorous Toolkit — v0.8 Contract Reference Integration

**Status:** Draft 0.2 — specification only; not implemented or qualified  
**Date:** 2026-11-03  
**Location:** `docs/reference-integrations/glamorous-toolkit/0.8.0/`  
**Purpose:** contextual-tooling experiment supporting the **proposed AIP v0.9** validation direction  
**GT baseline:** official v1.1.657 (bundled gt4llm v0.7.341)  
**Starting AIP source:** hosted v0.8 Sokol111, `https://mcp.daip.io/mcp`

The folder version identifies the **AIP v0.8 binding-picture contract being consumed**, not a GT version or a commitment to publish an AIP v0.9 release. The historical `0.4.2/` and `0.5.1/` integrations remain unchanged.

## 1. Objective and boundary

**Question:** Can GT turn AIP's evidence-qualified distributed architecture knowledge into an interactive environment in which an architect develops situational awareness, explores established and candidate boundaries, and understands which relationships matter to a proposed change—**beyond what the architect can establish without AIP or by using AIP directly**?

The target user is an architect preparing a cross-team distributed-system change, initially in [Sokol111](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md). A Redpanda-to-Kafka change is one useful framing, **not an instruction to rerun or explain the v0.7/v0.8 migration experiments**.

The experiment tests:
- **Situational awareness:** move from a service/capability/change question to its relevant services, topics, APIs where evidenced, neighboring bounded contexts, attachments, promises and uncertainties.
- **Interactive boundary investigation:** navigate independently supported context membership and cross-boundary relationships; also create clearly marked *candidate* groupings for investigation.
- **Change relevance and comprehension:** explain why a binding is pertinent to the proposed change, which assumptions it challenges, what evidence supports it, and what remains unknown or needs an owner decision.

AIP owns architecture claims, local Current State, attributable Intent, Assessment, bounded projections, provenance and qualification. GT owns navigation, presentation, exploratory groupings and investigator annotations. Neither GT nor an agent may silently turn an exploratory grouping or interpretation into an AIP-established fact.

**Non-goal:** showing the existing nine rows in a prettier inspector. Technical interoperability is necessary but insufficient.

## 2. Fixed decisions and initial constraints

| Concern | Decision |
|---|---|
| Code location | Existing AIP repository, `docs/reference-integrations/glamorous-toolkit/0.8.0/` |
| GT version | Fresh official **v1.1.657**, bundled upstream gt4llm; do not import prior customized images/adapters |
| MCP | Existing upstream `GtLMcpClient` / `GtLMcpHttpTransport` and full `tools/call` result (`structuredContent`) |
| Starting source | Public read-only `https://mcp.daip.io/mcp` with frozen Sokol111 v0.8 observations |
| Additional evidence | Permitted if the existing Sokol111 dataset cannot demonstrate the objective; requirements in `4 |
| User workflow | Architect investigating distributed boundaries and an intended change |
| GT mechanisms | Pharo domain objects, contextual Phlow inspectors, existing GT visualization/navigation, GT Examples and Lepiter |
| Agent | Optional comparator/follow-on, not required to implement the deterministic GT workflow |
| AIP/GT changes | Only if a concrete unmet requirement is established and separately justified |

The integration must distinguish the **recorded pre-migration** hosted snapshot from any separately recorded or newly assembled dataset. It must not combine evidence refs or snapshot-scoped results across datasets.

## 3. Architect workflow: questions before tooling

The implementation must support a real, bounded investigation rather than a fixed screenshot:

1. **Orient:** Starting from a proposed change or a selected service, what other services, topics, APIs (where qualified data exists), brokers and established bounded contexts are relevant? Show the scope, observation time and missing coverage.
2. **Explore:** Follow dependencies in either direction. Identify which bindings cross an **established** boundary versus which are internal/outside its scope. Open the supporting declared and observed evidence without conflating the two.
3. **Question boundaries:** Formulate a possible alternate grouping or ownership hypothesis. Inspect relationships, source documentation and membership evidence that support or challenge it; keep its classification `CANDIDATE` / investigator-authored until independently established.
4. **Assess the change:** Select relevant bindings, identify the assumptions they challenge and express questions for responsible teams. Show what remains unverified (for example event handling, cross-broker delivery, coverage or actual ownership).
5. **Explain:** Produce a concise investigation outcome with references to the original AIP answers/evidence and separate human interpretations; distinguish facts, assumptions and recommended next checks.

The workflow must allow choosing a different service or change target without requiring code edits to hardcoded nine-row tables.

## 4. Scenario and evidence fitness gate (before GT feature work)

The public hosted Sokol111 binding picture is the **bootstrap**, not a mandatory final dataset. Before choosing views, inventory what its read-only tools, Sokol111 documents and any other independently available sources can actually establish.

A suitable scenario should expose, insofar as sources permit:
- at least two **independently supported** service/context groupings;
- meaningful cross-boundary relationships and some internal/outside-boundary context;
- multiple evidence roles or types (e.g. authored promises vs captured attachments; qualified API relationships only if actually available);
- an uncertain or disputed interpretation worth investigating;
- one proposed change whose relevance is not identical to “display every row.”

Record a **scenario card** with role, proposed change, question sequence, source inventory, established facts, candidate hypotheses, observation/snapshot boundaries, and independently checkable expected findings. Prefer an existing Sokol111 scenario; do not fabricate source facts to make a diagram interesting.

**Dataset decision:** If the public C1 capture cannot support useful situational awareness across boundaries, create a separately versioned, reproducible Sokol111 evidence package based on authentic source documentation/configuration and real or otherwise correctly labeled capture data. Record source URLs/revisions, capture times, authorship, mapping rules, assumptions and digests. Any synthetic/illustrative content must be labeled and excluded from claims of real-world validation. Qualify the resulting AIP ingestion/answers separately. A different hosted endpoint or local read-only replay may be used **only if explicitly identified**; it must not be presented as the unchanged `mcp.daip.io` dataset or silently alter the current public demo.

If no defensible scenario can be constructed, report `DATASET_INSUFFICIENT` and stop the demonstration rather than inventing architectural boundaries.

## 5. Functional requirements

### FR1 — MCP integration and raw-answer fidelity

Using GT v1.1.657, verify negotiated HTTPS MCP access, tool discovery, nested `inputSchema` preservation and complete `structuredContent` results with the existing client. AIP v0.8's experimental `get_binding_picture` (query/evidence) is the initial tool, not the sole possible source of architecture context. Other existing AIP tools may be composed **only within their documented applicability**.

The GT adapter must retain the original AIP `schema_version`, `producer`, `tool`, `mode`, `outcome`, `snapshot`, `data` and `limitations`. Refusal, empty data, pagination and errors must be visible, not rendered as successful completeness.

### FR2 — Question-driven situational model

Represent the relevant **selected** landscape as navigable domain objects with stable source-qualified identifiers and links to the raw responses. At minimum distinguish:
- service / topic / broker / established context membership;
- relationship direction and local context crossing where established;
- AIP promise, attachment, mapping and assessment roles, plus capture/source metadata;
- source-document/configuration facts used by GT but **not asserted by AIP**;
- unknown/partial coverage and candidate-boundary annotations.

Avoid constructing a purported complete enterprise graph from a bounded answer. The currently exposed `get_binding_picture` query requires an established `bounded_context_id`: it **does not discover new Bounded Contexts**. GT may explore source material and propose hypotheses but must not manufacture AIP context membership or assessment results.

### FR3 — Exploratory boundary navigation

Provide contextual views that permit users to pivot among a selected service, its evidence-backed relationships, a boundary view and neighboring services. Use existing Phlow tools and simple inspectors first; a graph view is optional only if it improves the target investigation.

At all times visually/textually distinguish:
1. **Established boundary:** membership from independently attributable sources/AIP context.
2. **Candidate grouping:** an investigator's tentative selection, with rationale and source links.
3. **Unknown membership:** insufficient evidence; do not force it into either category.

A changed candidate grouping must not recompute an authoritative `crossing` or `status`. When an established boundary is selected, display the **unmodified AIP crossing/status** for that query scope. Candidate overlays are explicitly non-authoritative and may be compared without being written into AIP.

### FR4 — Provenance-preserving evidence drill-down

For v0.8 `binding-evidence:` references, use `get_binding_picture` in `mode: "evidence"`, **not** the generic `get_evidence` tool. Retain the query's exact `snapshot_id`, `bounded_context_id`, `environment` and `broker_ids`. Keep `promise_evidence_refs`, `attachment_evidence_refs` and `mapping_evidence_refs` distinct; deduplicate/sort requested refs; enforce the 1–20-ref limit.

Verify returned snapshot, scope and requested/ref-returned correspondence. Display `RESOLVED` and `NOT_RESOLVED` faithfully. Never rebind a missing reference to a later snapshot. Data from different source snapshots or independently imported GT files must be labeled as distinct observations or documents, not merged into a single qualified AIP claim.

### FR5 — Interpretation and change lens

For a selected proposed change, provide a navigable investigation summary:
- **Established:** relevant AIP-qualified relationships with their exact scope and evidence.
- **Challenged assumptions:** statements from actual documents/plans with their origin, separately linked to countervailing or additional evidence.
- **Candidate interpretations:** tentative architecture/ownership grouping with investigator attribution.
- **Unknown / follow up:** evidence limitations, unanswered technical checks and team questions.

The interface must not claim delivery, event-type handling, present-day activity, absence of consumers, complete coverage, an established replication path or context ownership without adequate evidence. Declared producers and mappings are not observed traffic; missing EventCatalog coverage does not establish that no agreement exists.

The investigator/agent may propose next actions, but the system must never present them as AIP-issued authoritative decisions.

### FR6 — Executable narrative and reproducibility

Publish one executable Lepiter investigation rooted in the scenario card. It should support navigation and alternative pivots, not just play a fixed demo. Save reviewable Pharo source, GT Examples, reproducible loading instructions and a source/evidence manifest in Git. A clean GT v1.1.657 installation must work without importing the prior v0.4.2 compatibility adapter or v0.5.1 customized image.

Recorded MCP responses are allowed for isolated tests, labeled with snapshot/source/version. They do not replace real endpoint compatibility qualification.

## 6. Implementation sequence and exit gates

| Iteration | Focus | Exit condition |
|---|---|---|
| **I0 — Scenario and dataset fitness** | Define architect decision, discover available Sokol111 sources, compare to `4, decide hosted C1 vs separately versioned extension | Source inventory + scenario card + evidence/coverage gaps + dataset decision. No invented facts |
| **I1 — GT interoperability** | Clean GT 1.1.657 with upstream gt4llm; connect to chosen AIP read-only MCP endpoint; preserve original tool result | Negotiation, tool schema and full answer verified; failures reported separately |
| **I2 — Situational navigation** | Model relevant entities and relationships, add pivots, scope labels and provenance | Architect can orient from a service/change to its neighbors and inspect why each relationship is shown |
| **I3 — Boundary investigation** | Established/candidate/unknown grouping exploration and evidence drill-down | Candidate interpretations remain non-authoritative; established AIP assessments/refs unchanged |
| **I4 — Change lens and Lepiter** | Build reproducible interactive investigation and concise decision-oriented report | Relevant bindings, challenged assumptions, uncertainties and next checks linked to evidence |
| **I5 — Comparative evaluation** | Compare alternatives on identical bounded tasks; log effort and interpretation quality | Evaluation record with results and negative findings; technical and value outcomes reported separately |

Do not implement a general graph engine or custom GT core functionality before a specific v0.9 user question justifies it.

## 7. Evaluation: what GT and AIP each contribute

Define answer keys **independently of GT's UI and AIP's rendered output**, grounded in the source inventory. Use the same decision task and available source material for each comparison:

| Condition | Question tested |
|---|---|
| **A. Existing tools** (docs/repository/broker evidence as applicable) | What can an architect establish with current engineering means? |
| **B. GT without AIP** (same independently accessible sources) | Does contextual exploration alone help? |
| **C. GT + AIP** | What does AIP's qualified binding picture add inside GT? |
| **D. Coding agent + AIP directly** | Is GT needed if an agent can already interpret AIP's tools? |

Measure **correct relationships and boundary distinctions**, omissions/surprises, supported vs unsupported assertions, decision/change-plan quality, time/navigation effort and **total engineering/owner effort**. Record which facts were visible to each condition and any unequal assistance; compare like with like. Counterbalance order when possible and record learning effects. Avoid asserting statistical significance or imposing an arbitrary 20%-speed threshold.

**Pass gates are separate:**
- **Technical integration:** GT consumes the public contract and navigates source-qualified results reproducibly.
- **Situational awareness:** an architect completes the bounded investigation without upgraded claims, including explicit uncertainty and relevant change follow-ups.
- **Incremental value:** comparative evidence shows whether GT+AIP adds value beyond GT alone, existing tools and direct agent+AIP. Results may be `POSITIVE`, `NO_ADDED_VALUE` or `INCONCLUSIVE`.

A Sokol111 experiment is **evaluation preparation**, not customer proof of AIP H1/H2. Actual owner effort, avoided coordination and product viability require a target customer with multiple teams. An impressive visualization does not satisfy the v0.9 outcome.

## 8. Deliverables

```text
docs/reference-integrations/glamorous-toolkit/
├── README.md                          # Add versioned integration link
├── 0.4.2/                             # Historical; unchanged
├── 0.5.1/                             # Historical; unchanged
└── 0.8.0/
    ├── README.md                      # Scope, scenario/dataset decision, current status
    ├── SPEC.md                        # This draft
    ├── scenario.md                    # I0: role, question, answers, data fitness (future)
    ├── AIP-GToolkit-Sokol111.st        # Implementation/export (future)
    ├── SOKOL111_RUNBOOK.md             # Clean-image instructions (future)
    ├── validation-report.md            # Evidence of actual gates (future)
    └── lepiter/                        # Executable investigation (future)
```

The present PR is **documentation-only**. It must not label I0–I5 as completed.

## 9. Non-goals and decision policy

Do **not**:
- replay the v0.7 comparison, v0.8 migration/agent failures or post-migration acceptance results;
- hardcode the hosted nine-row response as a new architecture discovery algorithm;
- derive authoritative context ownership from graph clustering, common topics or proximity;
- create a full architecture repository, production GT app, new MCP tool or source adapter without a demonstrated need;
- mutate AIP/GT core, solve GT #5247/#4255, or perform agent-generated permanent code changes as part of this reference integration.

A documented limitation of the public v0.8 binding-picture scope is **not itself a reason to change AIP**. First test GT composition of existing qualified queries and source material. Propose AIP work only for a concrete unmet architecture question, preserving evidence/semantic contracts.

**Release decision:** Proposed AIP v0.9 remains conditional. If this integration uses existing interfaces without meaningful AIP-side changes, publish the reference work independently under the v0.8 contract and reconsider assigning an AIP v0.9 release. Do not create functionality merely to justify a version number.

## 10. Source-of-truth references

- [AIP roadmap — proposed v0.9](../../../../ROADMAP.md#v09--contextual-architecture-intelligence-integration-proposed)
- [Product doctrine / product-validation hypotheses](../../../product-doctrine-and-strategic-direction.md)
- [Sokol111 hosted demo](../../../../examples/sokol111-demo/TRY_IT_HOSTED.md)
- [MCP contract](../../../mcp.md)
- [v0.8 request schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-request.schema.json)
- [v0.8 answer schema](../../../../schemas/architecture_intelligence/v0.8/binding-picture-answer.schema.json)
- [Prior GT v0.5.1 integration](../0.5.1/README.md)
- [GT v1.1.657 release](https://github.com/feenkcom/gtoolkit/releases/tag/v1.1.657)

**Qualification rule:** every acceptance result must be observed and recorded; specification expectations and earlier PoC results do not count as validation for this integration.
