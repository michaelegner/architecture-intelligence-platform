# DEMO-ADR-003 — Product Query accepts changes and offers product reads

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of the modeled Product Query owner, **not** approval by Sokol111 maintainers  
**Modeled decider:** Product Query service role  
**Scope and version:** existing shop projection/read environment, fixture v1  
**Audience:** Catalog as an event provider; existing shop clients as read consumers

## Context

Sokol111's Product Query service is the read side of the product CQRS split. Its source documentation describes consumption of Catalog product-update/deletion events and Image promotion events, version-aware projection updates, and Connect-RPC queries. A fictional owner could make independent commitments based on this design. The **implementation is evidence, not owner approval**.

## Decision and local promises

**Acceptance (−), made independently by the fictional Product Query role:** consume the relevant published Catalog product-update and deletion event formats for the existing shop projection, applying supported version/tenant semantics where events are successfully delivered and processed. This is an **assumed demo acceptance**, not a claim that AIP witnessed specific event-type processing.

**Offer (+), made by the same fictional role to shop read clients:** provide tenant-scoped product-list and product-detail reads from the maintained projection through the published Product Query API, reflecting successfully applied updates/deletions according to its supported read semantics.

**Applicability and limits:** the accepted event input and the offered read projection are **distinct local promises**. A read response describes projection state; this ADR does not establish that the projection is always synchronized with Catalog's latest committed state. Query API reachability alone does not authorize use for unrelated external purposes. Querying the projection is not a substitute for separately examining deployment, access, initialization, lag, recovery and the new consumer's proposed responsibilities.

## Why this decision

A read-optimized projection decouples storefront query load from Catalog writes. Accepting events and offering read APIs are separate choices, each with its own audience and conditions. The ADR does **not** pick a future connector's architecture.

## Supporting evidence and qualification limits

- [Product Query architecture and event-handler documentation](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/AGENTS.md)
- [Product Query API repository](https://github.com/Sokol111/ecommerce-product-query-service-api)
- [Product Query registered event consumers](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/internal/infrastructure/inbound/kafka/module.go)
- The frozen AIP v0.8 C1 binding picture has a qualified Product Query attachment to `catalog.product.events` relative to Catalog Management, with separate **demo-assumed EventCatalog** semantics. This can support **topic attachment** only; it does not validate the acceptance or read-offer behavior described here.

Pin source revisions, AIP package/snapshot and actual evidence request before using these references in evaluation. `DEMO_ASSUMED_CONFIRMED` is not an AIP qualification status.

**Evolution:** revise or supersede this fictional ADR independently of Catalog's and Image's decisions; neither owner can accept or extend the other's promise on their behalf.
