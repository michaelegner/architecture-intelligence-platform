# DEMO-ADR-003 — Product Query accepts changes and offers product reads

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of the modeled Product Query owner, **not** approval by Sokol111 maintainers  
**Modeled decider:** Product Query service role  
**Scope and version:** demo fixture v2, independently versioned Product Query decision for the simulated tenant-scoped shop environment  
**Audience:** `PQ-ACCEPT-01` concerns Catalog events for the existing shop projection; `PQ-READ-01` concerns approved tenant-scoped product-display clients, potentially including a separately provisioned sales-channel integration

## Context

Sokol111's Product Query service is the read side of the product CQRS split. Its source documentation describes consumption of Catalog product-update/deletion events and Image promotion events, version-aware projection updates, and Connect-RPC queries. A fictional owner could make independent commitments based on this design. The **implementation is evidence, not owner approval**.

## Decision and independently applicable local promises

### `PQ-ACCEPT-01` — Product-change acceptance (−)

**Promiser/acceptor:** modeled Product Query owner. **Counterparty:** Catalog's offered product-change event capability, for the existing shop projection.

**Fictional commitment:** accept and process the relevant Catalog product-update and deletion event formats according to the supported version/tenant semantics **when the messages are delivered and processable**.

**Applicability:** existing configured shop projection inputs. This is Product Query's own acceptance, not an obligation imposed on Catalog or a commitment to a future connector. It does not independently establish topic reachability, which event types were actually processed, delivery latency or read-side freshness.

### `PQ-READ-01` — Product-read offer (+)

**Promiser/provider:** modeled Product Query owner. **Audience:** tenant-scoped product-display clients **whose use has been separately provisioned**, including a sales-channel adapter *if* its tenant and purpose access is explicitly approved under this fictional offer.

**Fictional commitment:** provide tenant-scoped product-list and product-detail reads through the published Product Query API, reflecting the product projection state at query time.

**Applicability:** provisioned read clients requesting supported tenant products. Unlike `PQ-ACCEPT-01`, the **read offer is not restricted to existing event-projection consumers**, but it does **not grant credentials, marketplace rights or read consistency with Catalog's latest committed state**. Source-level API reachability does not prove authorization for the proposed connector.

**Separation:** the two promises have different audiences, input/output boundaries, applicability and potential evidence. `PQ-ACCEPT-01` may be compatible with Catalog's offered events while `PQ-READ-01` remains unavailable to an unprovisioned consumer, or vice versa. An observed event-topic attachment supports neither a particular query result nor authorization of a new sales-channel adapter.

## Why this decision

A read-optimized projection decouples storefront query load from Catalog writes. Accepting events and offering read APIs are separate choices, each with its own audience, conditions and stable local promise ID. The ADR does **not** pick a future connector's architecture.

## Supporting evidence and qualification limits

- [Product Query architecture and event-handler documentation](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/AGENTS.md)
- [Product Query API repository](https://github.com/Sokol111/ecommerce-product-query-service-api)
- [Product Query registered event consumers](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/internal/infrastructure/inbound/kafka/fxconfig/module.go)
- The frozen AIP v0.8 C1 binding picture has a qualified Product Query attachment to `catalog.product.events` relative to Catalog Management, with separate **demo-assumed EventCatalog** semantics. This may be relevant when questioning `PQ-ACCEPT-01`'s **topic-attachment premise only**; it does not qualify event-type handling, the acceptance itself, `PQ-READ-01`, read freshness, or new-client authorization.

Pin source revisions, AIP package/snapshot and actual evidence request before using these references in evaluation. `DEMO_ASSUMED_CONFIRMED` is not an AIP qualification status.

**Evolution:** revise or supersede `PQ-ACCEPT-01` and `PQ-READ-01` **independently** under the fictional Product Query owner; altering one does not silently alter the other or any Catalog/Image promise.
