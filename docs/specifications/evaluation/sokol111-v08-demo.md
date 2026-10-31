# Sokol111 demo: the next migration wave

**Status:** Draft 0.4 — decision-driven demo specification.
**Basis:** AIP v0.8.0 and the frozen Sokol111 state after wave 1
([v0.8 §3.6](../0.8.0/specification.md#36-expected-assessment-after-wave-1)).

## 1. Audience, change and question

This demo addresses an engineer or architect who has never used AIP. It must make sense without
reading this specification or interpreting AIP status codes.

[Sokol111](https://github.com/Sokol111/ecommerce-workspace) is an open-source, event-driven,
multi-service e-commerce system. Its migration from Redpanda to Kafka is staged: wave 1 already
moved Catalog Management to Kafka; wave 2 proposes moving Store Provisioning's tenant-event
producer. Other services may still be attached to the tenant topics on either broker.

**Decision to make before wave 2:** Who else must be involved, which broker paths need checking,
and which assumptions must be clarified before moving the producer?

The Store Provisioning team's source repositories explain its producer implementation, but
cannot by themselves establish the current attachments of consumers owned by other teams.
AIP brings separate authored declarations, captured broker attachments and bounded-context
membership into **one evidence-qualified cross-boundary binding picture**.

**Narrative rule:** Follow the producer's migration decision throughout. Any consumer-side view
must answer a question raised by the producer-side binding picture; never pivot context without
explaining why.

## 2. Main demo: discover → verify → decide

The binding picture is the **centerpiece**, not an incidental tool response. Present a readable
diagram or compact table before explaining internal fields. Its rows should show the source
context/producer, consumer service, broker, what was observed, promise coverage and remaining
uncertainty, and remain visible/referenced throughout the walkthrough.

### Step 1 — Discover the affected relationships

Ask: **“We plan to move Store Provisioning's tenant-event producer to Kafka. Which other
services are attached to its topics on each broker?”**

Query `get_binding_picture` for `bounded_context_id: store-provisioning`,
`environment: local`, and both broker IDs:
`[kafka:sokol111-local, kafka:sokol111-kafka]`.

Show these **four captured consumer attachments**, not unverified event handling:

| Consumer service | Broker | What AIP can establish from this evidence |
|---|---|---|
| Product Query | Redpanda | Consumer attachment in the frozen capture |
| Category Query | Redpanda | Consumer attachment in the frozen capture |
| Catalog | Kafka | Consumer attachment in the frozen capture |
| Image | Kafka | Consumer attachment in the frozen capture |

Also explain in plain language that these four rows have **missing promise coverage in the
demo's authored EventCatalog** (`UNRESOLVED` / `PROMISE_COVERAGE_MISSING`). This is not proof
that no human/team agreement exists. A consumer attachment to a topic does not prove it handles
a specific event type or that messages are delivered successfully. Show the actual supporting
rows and their scope, not just this expected summary.

**Viewer learns:** there are potentially affected services on *both* brokers, and the available
catalog does not document the corresponding promises.

### Step 2 — Follow one consequential uncertainty

Ask: **“The tenant producer is declared on Redpanda, yet Catalog and Image are attached on
Kafka. What path would need to exist, and what can AIP actually confirm?”**

Start with the Store Provisioning rows discovered in step 1. Only then explain why a
`catalog-management` consumer-side binding picture is useful: it inspects the Kafka-side
attachment from Catalog's perspective. Query `get_binding_picture` with
`bounded_context_id: catalog-management`, the same environment and broker IDs.

The relevant tenant rows are `INBOUND` on Kafka and report
`cross_broker_producers: true`. AIP identifies a **cross-broker path that requires verification**;
a replication bridge is a *possible explanation*, not a proven component. Preserve the
`CROSS_BROKER_DELIVERY_NOT_ESTABLISHED` limitation visibly beside this finding.

**Viewer learns:** moving the producer has dependencies beyond its own broker, but AIP cannot
claim that the end-to-end replication path works.

### Step 3 — Challenge the evidence and its boundaries

Ask: **“What proves Catalog was attached on Kafka at this snapshot, and what does that not
prove?”**

Resolve the Catalog row's evidence references using the supported binding-picture evidence
mode (document the precise call syntax and IDs in the executable walkthrough). Show the
captured attachment and the relevant mapping/declaration **with source, snapshot and scope**.
Do not suggest evidence references prove more than they contain.

Explain the limitations alongside the claim: `EVENT_HANDLING_NOT_ESTABLISHED`,
`CAPTURE_SCOPE_LIMITED` and `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED`. A frozen attachment
is not proof of event-type processing, continuous consumption, successful delivery or a complete
inventory.

**Viewer learns:** AIP lets them inspect *why* a relationship appears and precisely where
verification still needs to happen.

### Step 4 — Turn findings into a migration decision

Close the **main walkthrough** with this concrete, row-derived action list:

1. Identify owners of **Product Query and Category Query** (Redpanda) and **Catalog and Image**
   (Kafka), and coordinate the proposed producer move with them. Do not collapse all four into
   “the Catalog Management and Storefront teams” without showing the ownership mapping.
2. Verify the topic subscriptions and actual event handling with those owners; the broker
   attachments alone are insufficient.
3. Investigate the Redpanda → Kafka route used for the Kafka-side consumers, including whether
   replication exists and is working. AIP has **not** proven delivery.
4. Clarify and document the missing promises in the demo EventCatalog; do not infer that
   agreements outside that catalog are absent.
5. Re-check the relevant broker state and evidence before cut-over: the showcased snapshot is
   frozen and cannot establish the current production state.

**Final visible takeaway, grounded in the displayed rows:**

> Without cross-team broker evidence, the producer migration plan may miss four attached
> consumers across two brokers. AIP brings those relationships together, shows what supports
> them and what remains unresolved, so the team knows **whom to involve and what to verify**
> before changing the producer.

This is a demonstration of decision support and evidence qualification, **not** evidence that
AIP guarantees migration safety or improves planning quality.

## 3. Executable hosted walkthrough

The follow-up implementation replaces
`examples/pitstop-demo/TRY_IT_HOSTED.md` with the main four-step story above, **not** with a
tool catalog or a list of six unrelated outcomes.

It must include:

- One-sentence Sokol111 introduction, the two migration waves and the decision at stake.
- Prerequisites: an MCP client supporting streamable HTTP; for Claude Code, the copyable
  `claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp` command.
- The exact **hosted package identifier and snapshot identifier** for the after-wave-1 data,
  including a way to confirm the endpoint serves them. Do not invent IDs; capture them from
  the deployed package.
- For each of steps 1–3: a natural-language question, exact MCP tool name/arguments and
  evidence mode (including concrete broker and row/reference IDs), representative expected
  output, and a short **“what we learned / what is not established”** explanation.
- A legible binding-picture table/figure showing the four attachments and both brokers;
  subsequent steps must refer back to its rows. Distinguish *captured*, *declared*, *inferred*
  and *unresolved* facts in everyday words before optional status-code explanations.
- Step 4's action list and final takeaway, visibly connected to the same rows.
- Fail-fast troubleshooting for missing experimental tool, wrong package/snapshot and changed
  results. State clearly that the endpoint serves frozen demonstration data.

**Audience test:** Without reading this spec, a newcomer can say (a) what is being migrated,
(b) which four attachments appear on which two brokers, (c) why the cross-broker path is
unverified, and (d) whom to involve and what to check next, citing at least one piece of
evidence for the claims.

## 4. Hosted state and reproducibility

The owner switches `https://mcp.daip.io/mcp` to one identified **after-wave-1** package:
the v0.8 two-broker declarations, captures `a-r` and `a-k` from
[the frozen evidence directory](../0.8.0/i4-evidence/captures/), the corresponding mappings,
the demo EventCatalog, and `experimental.binding-picture` enabled.

Record package/snapshot IDs, relevant capture identifiers, exact tool arguments and expected
row/status output in versioned documentation. If the hosted instance is not switched, the
walkthrough must **not** imply its questions reproduce these results. The repository fixtures
and documented setup must make the frozen scenario inspectable even if hosted state changes.
No live monitoring, actual bridge configuration or verified event delivery is claimed.

## 5. Optional supporting exhibit — agent plan comparison

This is **not step 5**, not the demo climax and not necessary to understand AIP. Link it after
the main story for readers interested in possible coding-agent use.

If implemented, show one run without AIP and one with the frozen hosted AIP, using the
**same** prompt, repository revisions, model/settings and starting context; only AIP access
differs. Restrict the workspace to `ecommerce-tenant-service`,
`ecommerce-tenant-service-api`, `ecommerce-commons` and `ecommerce-workspace`, with
their pinned freeze SHAs; no broker commands, browsing or external consultation.
Preserve exact prompts, raw outputs and environment. Annotate whether each plan identifies
the four attachments, their brokers, the unverified cross-broker path and follow-up checks.
Do not rank a plan as better solely because it mentions more services. One session per side
illustrates possible differences; it does **not** establish product value or improved plans.

## 6. Deliverables and acceptance

Implementation can follow this spec in a separate PR:

1. Deployable, versioned after-wave-1 hosted package and documented identification.
2. Main `TRY_IT_HOSTED.md` with exact calls, expected rows, evidence and limitations.
3. Optional plan-comparison page, clearly outside the main walkthrough.

**Acceptance criteria:**

- An unfamiliar engineer can reproduce the frozen result with the documented commands and
  verify they have the expected package and snapshot.
- The four attachments on two brokers appear in one visible, evidence-qualified picture;
  each subsequent question refers back to it.
- No claims that topic attachment proves event handling, that missing catalog coverage means
  no agreement exists, or that cross-broker delivery is established.
- The walkthrough makes the producer → consumer-side perspective change explicit.
- The final visible section names **specific services, checks and uncertainties** drawn from
  the binding picture, rather than ending with status codes or an agent comparison.
- The optional agent exhibit is isolated, reproducible and clearly non-qualifying.

## 7. Disclosures

- Declarations and EventCatalog are generated for the demo; promises are a demo assumption
  (`PROMISES_ASSUMED_CONFIRMED`).
- Broker captures are frozen snapshots, not live Sokol111 traffic; repository revisions
  represent the state before wave 1.
- AIP does not ingest the cross-broker replication configuration. No bridge or delivered
  events are demonstrated.
- Captured topic attachment does not establish event-type handling or all consumers.
- A reproducible showcase demonstrates capability, not product-value qualification.

## 8. Decisions proposed for the owner

| # | Decision | Status |
|---|---|---|
| D1 | One Store Provisioning producer-migration story, with a visible binding picture as its centerpiece | proposed |
| D2 | Host only the versioned after-wave-1 package for this walkthrough | proposed |
| D3 | Use four decision-driven steps: discover, investigate, verify evidence, decide | proposed |
| D4 | Make the agent plan comparison an optional, separate exhibit | proposed |
