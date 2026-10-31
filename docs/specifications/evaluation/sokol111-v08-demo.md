# Sokol111 demo: the architecture you thought you had

**Status:** Draft 0.6 — proposal, pending owner approval.
**Basis:** AIP v0.8.0 and the frozen Sokol111 evidence before wave 1
([v0.8 §3.5](../0.8.0/specification.md#35-expected-assessment-of-c1)).
The recorded after-wave-1 state ([§3.6](../0.8.0/specification.md#36-expected-assessment-after-wave-1))
supports optional follow-ups; it is **not** a prerequisite for the main story.

## 1. Audience, premise and decision

The audience is an architect, engineer or coding-agent user who has not seen AIP before.
[Sokol111](https://github.com/Sokol111/ecommerce-workspace) is an open-source, event-driven
multi-tenant e-commerce system whose services communicate through Redpanda.

**Starting belief:** Sokol111's architecture documents describe Catalog Management publishing
product and category events to Storefront. That seems to be the relevant integration picture.

**Discovery question:** *Does the available architectural evidence show relationships beyond
those documented flows?*

**Decision question:** *If we plan to move Catalog Management (Catalog and Image) from Redpanda to
Kafka, which relationships must the team investigate before changing the broker?*

This is a **read-only architectural investigation and planning exercise**. The viewer does not
execute a migration. One coherent storyline goes from a documented belief, through AIP's
evidence-qualified findings, to a practical migration checklist.

**Differentiator to demonstrate, not merely claim:** Repository and broker tools can reveal
individual facts too. AIP brings authored promises, independently captured attachments,
service/boundary mapping and evidence limitations together in a **question-specific binding
picture**. It does not prove delivery, event-type handling or that documentation is complete.

## 2. Core story: belief → discovery → consequence → decision

The **same binding picture** is the visual anchor for each stage. Show the relevant rows,
broker, consumer, topic, boundary direction, promise coverage and observation qualification.
Prefer everyday explanations before exposing AIP's reason/status codes.

### Step 1 — Show the documented picture

Present the two Sokol111 architecture documents used for the generated demo EventCatalog,
with their exact pinned revision and links (see [v0.8 §1 and §3.1](../0.8.0/specification.md#1-promise)).
Explain: the documented Catalog Management → Storefront product/category flow is a useful
starting point, but not a complete inventory of runtime attachments.

**Viewer sees:** what the team *believes* and where that view came from. Do not say that
undocumented bindings are impossible to discover from source or configuration.

### Step 2 — Reveal the wider binding picture

Ask:

> “What does the available evidence establish about the bindings crossing Catalog
> Management's boundary, including relationships not covered by the EventCatalog?”

Run `get_binding_picture` against the frozen **pre-wave-1 C1** snapshot, scoped to
`bounded_context_id: catalog-management`, `environment: local` and
`broker_ids: [kafka:sokol111-local]`. Record exact optional arguments and output contract
from the running tool; do not invent schema fields.

**Expected nine rows** from the frozen v0.8 specification:

| Consumer | Topic | Boundary relative to Catalog Management | Promise assessment |
|---|---|---|---|
| Product Query | `catalog.product.events` | OUTBOUND | `PROMISED_AND_OBSERVED` |
| Image | `catalog.product.events` | INSIDE | `PROMISED_AND_OBSERVED` |
| Catalog | `tenant.tenant.events` | INBOUND | `UNRESOLVED` |
| Image | `tenant.tenant.events` | INBOUND | `UNRESOLVED` |
| Category Query | `catalog.category.events` | OUTBOUND | `UNRESOLVED` |
| Product Query | `catalog.attribute.events` | OUTBOUND | `UNRESOLVED` |
| Category Query | `catalog.attribute.events` | OUTBOUND | `UNRESOLVED` |
| Product Query | `tenant.tenant.events` | NONE | `UNRESOLVED` |
| Category Query | `tenant.tenant.events` | NONE | `UNRESOLVED` |

**Two rows are promised and observed; seven have no matching promise in the generated catalog.**
Only some cross the Catalog Management boundary: do not present INSIDE/NONE as migration
dependencies *of this boundary*. In plain language, tenant attachments into Catalog and
Image and attribute attachments toward the query services are missing from the generated
promise picture. In particular, **Category Query × `catalog.category.events` is `UNRESOLVED` even though the
architecture documents describe category events reaching Storefront**: the fixed catalog
generation rule produces no `receives` promise for Category Query. This is a *catalog coverage*
gap, not evidence that the relationship is absent from the documents. The clearer additional
relationships are the tenant and attribute topic attachments. Topic attachments do not by
themselves prove processing of particular events. `UNRESOLVED` means *no matching promise in
this demo catalog*, not that no agreement exists elsewhere.

**Viewer learns:** the documented picture is incomplete relative to the captured, mapped
relationships, and AIP preserves which kind of evidence supports each statement.

### Step 3 — Make the discovery relevant to an engineering change

Introduce the proposed move **only now**: Catalog and Image from Redpanda to Kafka.

Ask:

> “Which observed inbound and outbound attachments need investigation if Catalog
> Management changes brokers, and which ones are internal or outside this boundary?”

Use the **same snapshot and row IDs**, not a fresh unexplained perspective switch. Highlight:

- **Inbound:** Catalog and Image attached to `tenant.tenant.events` from Store Provisioning.
  The moving services need a plan for this input.
- **Outbound:** Product Query and Category Query attached to Catalog-owned
  `catalog.attribute.events`; Category Query to `catalog.category.events`; Product Query
  to `catalog.product.events`. The services remaining on the other broker need investigation.
- **Not all rows cross:** Image's product-topic attachment is internal to Catalog Management;
  the tenant attachments of Product Query/Category Query are outside this boundary. They remain
  visible for context without being mislabeled as boundary crossings.

**Viewer learns:** the picture changes the set of questions and stakeholders considered
before planning a migration; it does not by itself design or validate the broker cut-over.

### Step 4 — Inspect a surprising claim and its limits

Ask:

> “Why does AIP show Catalog consuming the tenant topic, and what exactly establishes that?”

Resolve the Catalog × `tenant.tenant.events` row's evidence references with the experimental
binding-picture evidence interface. **That lookup resolves the captured topic attachment and
the group-to-service mapping only**; this unresolved row has no promise reference. Explain
the separately authored producer declaration and bounded-context membership using the
**binding-picture answer row**, not as if the evidence lookup had returned them. Show the
snapshot and observation scope. The walkthrough gives the exact evidence request, row refs
and the result the reader should see.

In the same view, explain what remains unestablished: event-type handling, message
delivery, offsets/lag, any future attachment, complete consumer coverage and correctness
of any proposed replication mechanism. Declare producers as **authored**, not observed.
Avoid treating non-observation as proof of absence.

**Viewer learns:** each surprising row is inspectable, but its provenance and limitations
matter as much as its visibility.

### Step 5 — Finish with the migration decision, not a tool summary

Show the checklist derived explicitly from the displayed boundary-crossing rows:

1. Coordinate with the owners of **Catalog and Image** (inbound tenant topics), **Product
   Query** and **Category Query** (outbound product/category/attribute topics), and **Store
   Provisioning** as the tenant producer; verify actual ownership rather than assuming
   that a business-area label identifies every owner.
2. Inventory the required inbound and outbound topics and plan the intended routing across
   brokers, including both directions where needed. AIP has **not** established a bridge or
   successful replication.
3. Validate actual event handling, consumer offsets/lag, replication progress and application
   behavior using appropriate broker/application tools and tests; those are not established
   by the binding picture.
4. Clarify missing promise coverage in the generated EventCatalog and consult the responsible
   teams for agreements outside it.
5. Recheck fresh state before cut-over; the showcased evidence is a frozen capture.

**Final visible takeaway (after the checklist):**

> Sokol111's documentation shows a few event flows. AIP brings additional captured
> attachments and their evidence into one boundary-specific picture, distinguishing what
> is promised, observed and unresolved. The migration team can now see **which services
> and broker paths to investigate before changing Catalog Management**—without mistaking
> an observed attachment for proven end-to-end delivery.

This is a demonstration of a **capability**, not proof that AIP produces better plans in
real organizations.

## 3. Hosted walkthrough — runnable now

Update the **existing Sokol111** [`TRY_IT_HOSTED.md`](../../../examples/pitstop-demo/TRY_IT_HOSTED.md).
The Pitstop instructions are already in `TRY_IT_LOCALLY.md`. This is a narrative/content
improvement, not a new demo deployment or qualification exercise.

The hosted instance at `https://mcp.daip.io/mcp` already serves the frozen **pre-wave-1 C1**
package, as recorded in the [hosted deployment record](../../release-validation/v0.8.0-hosted-record.md)
(2026-10-30). The record identifies the snapshot as `aip:snapshot:v1:7f171aea…`
(abbreviated); include the **complete identifier from the actual response** in the
walkthrough. It exposes seven read-only MCP tools, including experimental
`get_binding_picture`.

Keep the reader's practical reproduction details:

- A brief Sokol111 introduction and a visual comparison of documented flows and the existing
  nine-row binding picture.
- The endpoint and copyable connection command:
  `claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp`.
- The package and complete hosted snapshot IDs, tool inventory and capture time; use the
  existing verified package, not a new import.
- For each step, the **exact prompt, tool name, argument values and recognizable result**;
  this includes `get_binding_picture` for `catalog-management`, `environment: local`
  and `broker_ids: [kafka:sokol111-local]`, followed by the exact evidence-mode
  request for the Catalog tenant-topic row.
- Everyday interpretation next to each finding: which relationships cross the boundary,
  how the Category Query category-topic row differs from the truly additional
  tenant/attribute attachments, and which sources the evidence lookup actually resolves.
- Practical troubleshooting: unavailable tool, connection problem, and unexpected snapshot
  or row count. Explain what a wrong snapshot would look like without introducing a new
  verification workflow.
- A row-derived migration checklist and the §2 takeaway at the end.

The walkthrough describes the **nine visible rows** and their limits; it does not need
another formal expected-output qualification or a new reader acceptance test.

## 4. Existing hosted evidence

The [hosted record](../../release-validation/v0.8.0-hosted-record.md) already documents
the installed C1 package, deployment, external MCP checks and evidence drill-down.
Use that established baseline. No new digests, fixture matching, re-import, local replay,
tool-contract qualification or hosted-switch decision is part of this follow-up.

The generated EventCatalog entries are treated as confirmed promises by a disclosed
demo assumption (`PROMISES_ASSUMED_CONFIRMED`), not because real service owners signed
them. The source/config-derived declarations and service mapping are authored.
The broker capture is frozen, not continuous monitoring.

## 5. Optional recorded stories (not hosted interactive demos)

The public endpoint serves **C1 only**. The after-wave-1 two-broker captures (`a-r`, `a-k`)
are in [`i4-evidence/captures`](../0.8.0/i4-evidence/captures/), **not** loaded on the
hosted endpoint. No reader-facing local Sokol111 import walkthrough is supplied by this
spec. Do not suggest that the following stories can currently be queried from the host.
They are **recorded case studies** until an explicit runnable route is provided.

### A. Wave 1 — what happened after migration?

Present the frozen before/after findings from the
[v0.8 release notes](../../release-validation/v0.8.0-release-notes.md) and
[I4 evidence](../0.8.0/i4-evidence/README.md), clearly labeled **recorded results,
not a rerunnable hosted session**. Show attachment changes on Kafka/Redpanda and explain
that separate broker tools and functional tests, not AIP, established replication
progress and application behavior.

### B. Wave 2 — who relies on Store Provisioning?

Use the recorded after-wave-1 picture: Product Query and Category Query are attached
on Redpanda, Catalog and Image on Kafka. The producer is declared on Redpanda; AIP's
`cross_broker_producers: true` identifies a cross-broker path **to investigate**, not
verified delivery or a proven bridge. Show the limits and a concrete owner/checklist
outcome.

**Presentation route:** link to the frozen I4 answers and captures; mark the example
**recorded, not interactive**. If a separate runnable Wave-2 walkthrough is later
published, it must supply its own executable queries, both broker IDs, snapshot/package
IDs and recognizable outputs, and say where that package runs. None of that is required
to deliver the primary demo now.

### C. Coding agent comparison (optional recorded exhibit)

If shown, disclose a fixed task prompt, model and settings, repository revisions and
starting context, with AIP access as the only intended difference. Link the actual
published transcripts, if available. This is an illustration from one session per
condition, **not** evidence of improved plan quality. It is neither a requirement for
the primary walkthrough nor another qualification study.

## 6. Deliverable

Revise the existing hosted Sokol111 page to include the documented architecture picture,
the boundaries that matter for the proposed Catalog Management change, accurate evidence
attribution for one surprising row, the Category Query catalog-coverage explanation and
a practical migration checklist. Keep the existing runnable connection and question flow,
including exact tool arguments, results, snapshot identification and reader troubleshooting.

The published instructions should produce the **described C1 binding picture** on the
recorded hosted instance. The main story closes with specific AIP-supported findings
and their limitations, rather than test results or an agent comparison. Optional stories
are clearly labeled **recorded** until a supported execution route exists.

## 7. Disclosures

- Frozen public-system snapshots and an authored demonstration catalog, **not** live
  monitoring or complete production knowledge.
- Broker attachment ≠ event-type handling, reliable delivery or application correctness.
- Producers are declared, not observed. Missing catalog coverage ≠ missing human agreement.
- Actual broker migration behavior was tested separately; AIP never established
  replication or end-to-end delivery.
- Reproduction may depend on source paths and therefore change snapshot IDs; record the
  deployed identifiers instead of assuming portable equality.
- Showcase capability is not product-value qualification.

## 8. Proposed decisions for the owner

| # | Decision | Status |
|---|---|---|
| D1 | Primary story: documented belief → C1 discovery → wave-1 impact decision | proposed |
| D2 | Use one nine-row binding picture throughout the primary story | proposed |
| D3 | Use the existing hosted C1 endpoint and Sokol111 walkthrough; no new deployment/replay | proposed |
| D4 | Present wave-1 after-state, wave-2 and agent comparison as optional recorded exhibits, not hosted interactive demos | proposed |
