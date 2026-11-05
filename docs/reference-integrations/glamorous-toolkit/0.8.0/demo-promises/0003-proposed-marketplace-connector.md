# DEMO-ADR-003 — Marketplace Connector proposes listing maintenance

**Status:** `DEMO_PROPOSED` — unaccepted fictional future-consumer decision, **not** an existing Sokol111 service or owner commitment  
**Modeled promiser:** proposed Marketplace Connector service role  
**Prospective beneficiaries:** merchant using an additional sales channel  
**Scope:** fictional merchant request, demo fixture v1

## Context

A merchant wants product listings on a marketplace to reflect its shop's catalog, without maintaining a second catalog. In addition to product details, images, prices and availability, it requires a disabled or deleted product to disappear from the marketplace **within 15 minutes**. This is an invented business requirement for the demonstration, not a real marketplace policy.

## Proposed decision, acceptance (−) and outward promise (+)

**Proposed acceptance (−):** consume or otherwise obtain sufficient catalog and media information from the existing autonomous platform participants, **only where suitable offers and authorizations can be established**.

**Proposed merchant-facing promise (+):** maintain marketplace listings from the shop catalog and withdraw a listing within 15 minutes after the merchant disables or deletes the associated product.

**Status:** Neither acceptance nor outward promise is adopted or observed. The architect must determine whether compatible upstream promises and connector-owned mechanisms could make these commitments credible.

## Rationale, alternatives and consequences

Reusing existing capabilities avoids separate merchant data entry. The team may need an agreed provider contract, an independently verifiable connector-controlled freshness/reconciliation mechanism, a weaker merchant commitment, or a **defer** decision. No particular solution is presumed.

## Evidence / limitations

- Hypothetical business brief in [the experiment specification](../specification.md).
- Existing Sokol111 source and AIP binding evidence establish **existing** implementation and attachments only; they do not establish marketplace permissions, publication deadlines or this connector's presence.
- This document is a proposed demo decision; it must **never** be displayed as a confirmed local service promise or AIP Current State.

**Evolution:** accept, change or decline only as an explicit **fictional** next-stage demo decision, with reason and conditions recorded.
