# Sokol111 demo: the next migration wave

**Status:** Draft 0.2, lightweight.
**Basis:** AIP v0.8.0 and the frozen v0.8 Sokol111 state after wave 1
([v0.8 §3.6](../0.8.0/specification.md#36-expected-assessment-after-wave-1)).

## 1. Story

Sokol111 moves from Redpanda to Kafka in waves. Wave 1 is done: Catalog Management runs on Kafka.

The Store Provisioning team is next. It owns the tenant service, and it asks one question before the move:

> **Who relies on my events, and on which broker?**

The team's own repositories cannot answer this. The consumers are in other teams' services, and since
wave 1 they are on two brokers. AIP answers from the declarations, the promises in the EventCatalog and one
consumer capture per broker.

## 2. Demo outcomes

| # | Outcome | Shown by |
|---|---|---|
| O1 | **Hidden consumers.** Four services consume the tenant events: Product Query and Category Query on Redpanda, Catalog and Image on Kafka | `get_binding_picture` for `store-provisioning`, both brokers |
| O2 | **Nothing is promised.** All four bindings are observed, but no promise documents them | the same answer: `UNRESOLVED`, `PROMISE_COVERAGE_MISSING` |
| O3 | **A bridge nobody declared.** Catalog and Image read the tenant events on Kafka, but the producer writes to Redpanda. They depend on a bridge between the brokers | `get_binding_picture` for `catalog-management`: the tenant rows are `INBOUND` on Kafka with `cross_broker_producers: true` |
| O4 | **Every row has its evidence.** The capture, the mapping and the declaration behind a row | `get_evidence` on a row's refs |
| O5 | **AIP says where it stops.** It does not claim delivery across the bridge, event handling or completeness | the limitations: `CROSS_BROKER_DELIVERY_NOT_ESTABLISHED`, `EVENT_HANDLING_NOT_ESTABLISHED`, `CAPTURE_SCOPE_LIMITED` |
| O6 | **The plan changes.** The agent plans the move once without AIP and once with AIP | the two plans, side by side |

## 3. Demo script

The viewer connects an MCP client to `https://mcp.daip.io/mcp` and asks:

1. "Which bindings cross the Store Provisioning boundary, on both brokers?" → O1, O2
2. "Where do Catalog Management's tenant events come from?" → O3
3. "Show the evidence for the Catalog row." → O4
4. "What does this answer not establish?" → O5

Then the viewer opens the plan comparison → O6.

The new `examples/pitstop-demo/TRY_IT_HOSTED.md` is this script. Per question, it gives:
- the request, with the ids it needs (`bounded_context_id`, `broker_ids`);
- what the answer shows.

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

- **Task:** "Store Provisioning moves the tenant service from Redpanda to Kafka. Wave 1 moved Catalog
  Management to Kafka. Plan the move. Do not change anything."
- **Workspace:** the tenant team's repositories only: `ecommerce-tenant-service`,
  `ecommerce-tenant-service-api`, `ecommerce-commons`, `ecommerce-workspace`. No broker commands, no web,
  nobody to ask.
- **Sessions:** one without AIP, one with the hosted AIP. Agent `claude-opus-5-5`.
- **Shown:** the two plans side by side. The page marks where each plan names the consumers, their
  brokers and the bridge. It shows the plans as they are.

## 6. Deliverables

One PR after this spec:
- the package and its config;
- the new `TRY_IT_HOSTED.md`;
- the plan comparison page.

Then the owner switches the hosted instance.

## 7. Disclosures

- The declarations and the EventCatalog are generated for the demo. The promises are a demo assumption
  (`PROMISES_ASSUMED_CONFIRMED`).
- The state is frozen. It is not live Sokol111 traffic.
- The repositories show the state before wave 1.
- One session per side, one model, one public system. The demo shows a capability. It verifies nothing
  and is not proof of product value.

## 8. Decisions

| # | Decision | Status |
|---|---|---|
| D1 | One story: the Store Provisioning team before wave 2 | proposed |
| D2 | The hosted instance serves only the after-wave-1 package | proposed |
| D3 | `TRY_IT_HOSTED.md` becomes the demo script | proposed |
| D4 | The plan comparison is one session without AIP and one with AIP | proposed |
