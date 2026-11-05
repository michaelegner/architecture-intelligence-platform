# DEMO-ADR-002 — Image offers promoted-image information

**Status:** `DEMO_ASSUMED_CONFIRMED` — fictional decision of the modeled Image owner; **not** Sokol111 maintainer confirmation  
**Modeled decision owner:** Image service role  
**Audience:** existing shop image-read/projection consumers  
**Scope and version:** simulated local e-commerce environment, fixture v1

## Context

Sokol111's Image service manages product-media promotion and delivery. Its documentation describes `ProductImagePromotedEvent`; Product Query handles these messages to update projected image URLs. This is **implementation evidence**, not a real promise.

## Decision and local offer (+)

**In this fictional experiment**, Image offers information about successfully promoted product images to its modeled existing shop projection consumers through image-promotion events.

**Conditions and scope:** Promotion succeeds for the relevant image/tenant; an image-promotion event concerns that lifecycle transition. The local offer is distinct from Catalog's product changes. It does not determine which new consumers may accept the interface or how their downstream presentation is implemented.

## Rationale and consequences

Separating media promotion from product writes allows an independent media lifecycle. A consumer evaluating an additional product presentation channel should examine the meaning, applicability and evidence of this offer alongside any other service capabilities, rather than treating product attributes as an all-in-one contract.

## Evidence and limitations

- [Image service architecture](https://github.com/Sokol111/ecommerce-image-service/blob/master/AGENTS.md)
- [Product Query architecture and image-event handling](https://github.com/Sokol111/ecommerce-product-query-service/blob/master/AGENTS.md)

These sources support a candidate service behavior, not real owner approval or a complete AIP promise assessment. Pin exact source SHAs and AIP snapshot before evaluation.

**Evolution:** Only the modeled Image owner can revise this fictional offer; other participants' acceptance remains independent.
