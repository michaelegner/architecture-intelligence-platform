# DEMO-CONTRACT-001 — External marketplace withdrawal processing

**Status:** `DEMO_CONTRACT_ASSUMED` — **independent fictional external marketplace offer**, not a contract or policy of any real marketplace  
**Modeled offeror:** external marketplace platform role (separate from Sokol111)  
**Audience:** permitted third-party listing publishers  
**Scope and version:** hypothetical demonstration marketplace, fixture v2

## Capability offered

A permitted publisher may submit an authenticated withdrawal request for an existing listing within its authorized merchant/channel scope. The marketplace **accepts or rejects** the request according to this fictional contract. **For an accepted, valid request, the marketplace offers processing and a queryable outcome: completed (the listing is no longer publicly visible) or failed (with an indication that further action may be necessary).**

This contract **does not promise a fixed time from request acceptance to completed withdrawal**. Request acceptance and externally visible listing removal are distinct stages; neither an acknowledgement nor a pending status establishes withdrawal. Any end-to-end merchant deadline therefore requires further locally attributable commitments and evidence, not subtraction from an invented marketplace SLA.

## Applicability, exclusions and independent authority

- Only valid, authenticated, correctly scoped and accepted requests fall under the fictional processing promise.
- A rejection, unavailable endpoint, request never received, or no accepted request creates no processing commitment under this offer; this contract supplies **no assertion about another service detecting changes or reaching the marketplace**.
- The contract does not provide a promise from Catalog, Product Query, a future Marketplace Connector or any consumer. It does not establish what credentials a new consumer actually has.
- Completion means **the external listing is no longer visible**, which is distinct from acceptance, a pending status, or merely initiating withdrawal. A failed outcome leaves the merchant's requested result unmet.

## Why this independent contract matters

A marketplace is a separate autonomous participant. An end-to-end merchant requirement depends on commitments and behavior at **multiple** boundaries. This fictional contract allows the architect to distinguish a valid request, its acceptance, subsequent completion or failure, and what remains unpromised. It is **not** a preset SLA budget or a prescription to use events, polling, retries, an authorization arrangement or a particular connector design.

## Evidence and provenance

This is deliberately invented exercise data, **not grounded in Sokol111 implementation or a real marketplace**. Keep it separate from AIP's frozen C1 evidence; AIP v0.8 does not qualify this contract or observe a future connector-to-marketplace binding.

**Evolution:** changes to this fictional offer belong to the modeled marketplace role, not to a Catalog owner, a Product Query owner or AIP.
