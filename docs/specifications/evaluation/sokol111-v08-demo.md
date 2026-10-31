# Sokol111 demo: the architecture you thought you had

**Status:** Draft 0.5 — proposal, pending owner approval.
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

**Two rows are promised and observed; seven are unresolved for missing catalog coverage.**
Only some cross the Catalog Management boundary: do not present INSIDE/NONE as migration
dependencies *of this boundary*. In plain language, tenant attachments into Catalog and
Image and attribute attachments toward the query services are missing from the generated
promise picture. Topic attachments do not by themselves prove processing of particular
events. `UNRESOLVED` means *no matching promise in this demo catalog*, not that no agreement
exists elsewhere.

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

Resolve the relevant binding/evidence references with the experimental binding-picture
evidence interface. Display the attributable group-to-service mapping, captured topic
attachment and declared topic/context information, with the snapshot and observation scope.
The runnable walkthrough must give the **exact evidence request**, IDs/refs obtained from
the answer and representative response excerpts.

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

## 3. Reproducible main walkthrough

Implement the primary narrative in
`examples/pitstop-demo/TRY_IT_HOSTED.md`, or a clearly linked dedicated Sokol111 page if
replacing the existing Pitstop instructions would remove another working demo.

The page must be usable without this spec:

- Introduce Sokol111, Redpanda, Catalog Management and the proposed move in plain language.
- Show a pinned documented picture (with source-document links) next to the **nine-row
  evidence-qualified binding picture**; keep the comparison visually intelligible.
- Provide client prerequisites and copyable MCP connection instructions, e.g.
  `claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp`.
- State the exact package and snapshot IDs, pinned capture/repository revision, available
  tool set and how to check the deployed endpoint serves the expected **pre-wave-1 C1** data.
  Obtain real IDs from the assembled package, never fabricate them.
- For each tool step: give the natural-language prompt, precise tool and argument values,
  expected response/row evidence, plain-English interpretation and limitations.
- Explain statuses only after the reader sees what each finding means.
- Make the actionable checklist and final takeaway the **end** of the main walkthrough,
  not a list of MCP commands or experimental results.
- Explain missing/disabled tools, wrong hosted snapshot, and unsupported response fields.
  If the hosted endpoint cannot serve C1, provide the precise local frozen replay path
  instead and **do not claim** the hosted questions reproduce it.

**Cold-reader acceptance test:** Someone new to AIP can identify the documented belief,
the new tenant/attribute attachments, which rows actually cross Catalog Management, the
evidence behind one surprising row, and the concrete migration checks—without reading
the implementation spec.

## 4. Hosted package and data constraints

The hosted endpoint is currently a constrained, frozen MCP demonstration. **Switching its
package is a separate owner-controlled action**. The main story must not depend on an
unverified assumption that it already serves the pre-wave-1 state.

Use the versioned C1 evidence
([v0.7.2 C1](../0.7.2/i2-evidence/sokol111/c1/kafka-consumer-state.json))
and the corresponding v0.8 authored declarations, service mapping and EventCatalog.
Document input digests, package/snapshot IDs, tool contracts, frozen expected rows and
replay instructions. The generated EventCatalog is an explicit assumption
(`PROMISES_ASSUMED_CONFIRMED`); its entries are not claims made by the Sokol111 teams.
Source/configuration-derived declarations and mapping are authored evidence.

Do not erase or overwrite a different hosted demo without the owner's decision. The
implementation PR must describe whether it hosts C1, uses a separate endpoint, or relies
on a local deterministic replay. No live traffic or complete architecture inventory is
implied.

## 5. Optional advanced stories (not prerequisites)

### A. Wave 1: what did the change produce?

Using the already frozen **after-wave-1** two-broker captures, compare the before/after
attachments for the Catalog Management boundary. Explain which rows now appear on Kafka,
which remain on Redpanda and which are outside each capture scope. Show the difference
between AIP's broker-attachment evidence and the **separate** broker commands/functional
tests that established replication progress and application behavior
([release notes](../../release-validation/v0.8.0-release-notes.md)).
No unsupported claim of delivery or universal detachment.

### B. Wave 2: who relies on Store Provisioning?

Preserve the former Draft 0.4 scenario as a follow-up using the frozen after-wave-1 state:
Store Provisioning proposes moving the tenant producer. Two consumer attachments (Product
Query, Category Query) are on Redpanda; two (Catalog, Image) are on Kafka. The producer is
declared on Redpanda, so Kafka-side attachments expose a **cross-broker path to verify**
(`cross_broker_producers: true`), not proven delivery or a confirmed bridge. Show missing
demo-catalog promises, row evidence, limitations and an owner/checklist outcome.

Only offer this when the reader understands the primary single-broker story. Record
exact queries, package/snapshot IDs and expected outputs independently.

### C. Coding agent with and without AIP (optional exhibit)

A tightly controlled, **non-qualifying illustration**, not the demo climax. Hold prompt,
model/settings, pinned repositories and initial context fixed; vary only AIP access.
Retain unedited transcripts and annotate specific context differences. One session per
condition does not establish better planning quality or real-world product value.

## 6. Deliverables and acceptance

Implementation follow-up:

1. A versioned, reproducible **pre-wave-1 C1** package/replay route and a truthful account
   of hosted deployment state.
2. A copyable primary walkthrough with documented source picture, the nine-row binding
   picture, exact evidence calls, and a row-derived migration checklist.
3. Optional separate advanced pages for after-wave verification, wave 2, or agent comparison.

**Acceptance criteria:**

- Main story is understandable to a first-time viewer and runs against the **identified**
  snapshot/package with the documented tool interface.
- Nine expected rows match the frozen evidence; **INSIDE/NONE** are not counted as crossing
  Catalog Management, and missing promise coverage is explained without overclaim.
- Evidence is attributable and limitations are visible at the point of each claim.
- The main story finishes with the actionable checklist and the specific, evidence-grounded
  AIP contribution; no agent comparison interrupts the narrative.
- Advanced stories are optional, independently reproducible and do not confuse the
  main C1 snapshot with the after-wave-1 captures.

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
| D3 | Treat hosting/replay of C1 as an explicit implementation decision | proposed |
| D4 | Offer wave-1 before/after, wave-2 migration and agent comparison only as extensions | proposed |
