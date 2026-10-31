# Sokol111 demo: the next migration wave

**Status:** Draft 0.3, lightweight.
**Basis:** AIP v0.8.0 and the frozen v0.8 Sokol111 state after wave 1
([v0.8 §3.6](../0.8.0/specification.md#36-expected-assessment-after-wave-1)).

## 1. Story

**The change.** Sokol111 moves from Redpanda to Kafka in waves. Wave 1 moved Catalog Management to Kafka.
Next, the Store Provisioning team moves the producer of the tenant events, the tenant service.

**The risk.** The consumers of the tenant events are in other teams' services, and since wave 1 they are on
two brokers. The team's own repositories do not show them. A plan made from those repositories can miss a
consumer, or miss that a consumer reads on the other broker.

**The question:**

> **Who relies on my events, on which broker, and what must we check before the move?**

**The decision it supports:** whom to involve and what to verify before the producer moves.

## 2. Demo outcomes

| Step | # | Outcome | Shown by |
|---|---|---|---|
| Discovery | O1 | **Hidden consumers.** Four services consume the tenant events: Product Query and Category Query on Redpanda, Catalog and Image on Kafka | `get_binding_picture`, `store-provisioning`, both brokers |
| Discovery | O2 | **Missing promises.** All four bindings are observed, but no promise documents them | the same answer: `UNRESOLVED`, `PROMISE_COVERAGE_MISSING` |
| Investigation | O3 | **A cross-broker path to check.** The producer is declared on Redpanda. Catalog and Image are attached on Kafka. AIP flags this; how the events reach Kafka (for example a bridge) is a hypothesis to investigate | `get_binding_picture`, `catalog-management`: the tenant rows are `INBOUND` on Kafka with `cross_broker_producers: true` |
| Investigation | O4 | **Evidence per row.** The capture, the mapping and the declaration behind a row | the evidence mode of `get_binding_picture`, on the row's refs |
| Limits | O5 | **Where AIP stops.** AIP does not establish delivery across brokers, event handling or completeness | the limitations: `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED`, `EVENT_HANDLING_NOT_ESTABLISHED`, `CAPTURE_SCOPE_LIMITED` |
| Decision | O6 | **The plan changes.** The agent plans the move once without AIP and once with AIP | the two plans, side by side |

**Takeaway**, the last visible line of the demo:

> Repository analysis can explain the tenant service; AIP exposes observed consumer attachments and
> missing promises across team and broker boundaries, with links to evidence and clear limits—so the
> migration team knows whom to involve and what to verify before moving the producer.

For Sokol111, that means: involve the Catalog Management and Storefront teams (the four consumers), agree
the missing promises, and check the cross-broker path to Catalog and Image before the move.

## 3. Walkthrough

The new `examples/pitstop-demo/TRY_IT_HOSTED.md` replaces the current page. It contains:
- **Prerequisites:** an MCP client with streamable HTTP and the URL `https://mcp.daip.io/mcp`.
- **Connect:** the command to copy, for example
  `claude mcp add --transport http aip-hosted https://mcp.daip.io/mcp`.
- **Which package:** the snapshot id and package id of the after-wave-1 package. The first answer shows the
  snapshot id, so the viewer can see which package the endpoint serves.
- **Four questions**, each with the natural-language prompt, the exact arguments and a representative
  expected answer (rows and statuses):

| # | Prompt | Arguments | Outcome |
|---|---|---|---|
| 1 | "Which bindings cross the Store Provisioning boundary, on both brokers?" | `get_binding_picture`: `bounded_context_id: store-provisioning`, `environment: local`, `broker_ids: [kafka:sokol111-local, kafka:sokol111-kafka]` | O1, O2 |
| 2 | "Where do Catalog Management's tenant events come from?" | `get_binding_picture`: `bounded_context_id: catalog-management`, same brokers | O3 |
| 3 | "Show the evidence for the Catalog row." | `get_binding_picture` in evidence mode, with the row's refs | O4 |
| 4 | "What does this answer not establish?" | the limitations of answer 1 or 2 | O5 |

- **Known limits:** the disclosures of §7.
- **Close:** the takeaway of §2 and a link to the plan comparison.

## 4. Hosted instance

The instance serves one package, the state after wave 1:
- the v0.8 declarations for both brokers;
- the captures `a-r` (Redpanda) and `a-k` (Kafka) from
  [`../0.8.0/i4-evidence/captures/`](../0.8.0/i4-evidence/captures/);
- one mapping per broker;
- the EventCatalog;
- the `experimental.binding-picture` flag.

The current package is replaced. The owner does the switch, as on 2026-10-30.

## 5. Plan comparison (O6)

- **Same for both sessions:** the task prompt, the repository revisions, the model (`claude-opus-5-5`) and
  its settings, and the starting context. Only the AIP access differs.
- **Task:** "Store Provisioning moves the tenant service from Redpanda to Kafka. Wave 1 moved Catalog
  Management to Kafka. Plan the move. Do not change anything."
- **Workspace:** the tenant team's repositories only: `ecommerce-tenant-service`,
  `ecommerce-tenant-service-api`, `ecommerce-commons`, `ecommerce-workspace`, at the v0.7.2 freeze commits.
  No broker commands, no web, nobody to ask.
- **Sessions:** one without AIP, one with the hosted AIP.
- **Shown:** the unedited prompts, outputs and environment of both sessions, and the plans side by side.
  The annotations name concrete differences: which consumers, brokers and checks each plan names. They do
  not rate a plan as better because it names more services.
- One session per side is an illustration. It is not evidence that AIP improves planning.

## 6. Deliverables and acceptance

One PR after this spec:
- the package and its config;
- the new `TRY_IT_HOSTED.md` (§3);
- the plan comparison page (§5).

Then the owner switches the hosted instance.

**Acceptance criteria** for that PR:
1. The walkthrough runs as written: copy-paste commands, exact arguments, expected outputs, the package and
   snapshot id.
2. O3 is phrased as a path to check everywhere. No text presents cross-broker delivery as established.
3. The takeaway of §2 is the final visible line of the walkthrough and of the comparison page, and the rows
   shown support it.

## 7. Disclosures

- The declarations and the EventCatalog are generated for the demo. The promises are a demo assumption
  (`PROMISES_ASSUMED_CONFIRMED`).
- The state is frozen. It is not live Sokol111 traffic.
- The repositories show the state before wave 1.
- AIP does not ingest the cross-broker replication configuration.
- One session per side, one model, one public system. The demo shows a capability. It is not proof of
  product value.

## 8. Decisions

| # | Decision | Status |
|---|---|---|
| D1 | One story: the Store Provisioning team before wave 2 | proposed |
| D2 | The hosted instance serves only the after-wave-1 package | proposed |
| D3 | `TRY_IT_HOSTED.md` becomes the walkthrough of §3 | proposed |
| D4 | The plan comparison is one session without AIP and one with AIP, as an illustration | proposed |
