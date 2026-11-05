# DEMO-CONTRACT-001 — External marketplace withdrawal processing

**Status:** `DEMO_CONTRACT_ASSUMED` — **independent fictional external marketplace offer**, not a contract or policy of any real marketplace  
**Modeled offeror:** external marketplace platform role (separate from Sokol111)  
**Audience:** permitted third-party listing publishers  
**Scope and version:** hypothetical demonstration marketplace, fixture v1

## Capability offered

A permitted publisher may submit an authenticated withdrawal request for an existing listing within its authorized merchant/channel scope. The marketplace **accepts or rejects** the request according to the fictional interface contract and reports an outcome. **For an accepted, valid withdrawal during the modeled normal service conditions, the marketplace promises the listing will cease to be publicly visible no later than 5 minutes after request acceptance.**

The **5-minute period begins at acceptance**, not at the shop product change or when a caller first attempts to submit a request. This invented figure is solely a bounded promise for the exercise—not a fact about a real marketplace.

## Applicability, exclusions and independent authority

- Only valid, authenticated, correctly scoped and accepted requests fall under the fictional processing promise.
- A rejection, unavailable endpoint, request never received, or no accepted request does not activate the processing deadline; this contract supplies **no assertion about another service detecting changes or reaching the marketplace**.
- The contract does not provide a promise from Catalog, Product Query, a future Marketplace Connector or any consumer. It does not establish what credentials a new consumer actually has.
- Completion means **the external listing is no longer visible**, which is distinct from receiving an acknowledgement or merely initiating withdrawal.

## Why this independent contract matters

A marketplace is a separate autonomous participant. An end-to-end merchant requirement depends on commitments and behavior at **multiple** boundaries. The purpose of the fictional contract is to let architects inspect and assess that independence, **not** to prescribe events, polling, retries, request timing, an authorization arrangement or a guaranteed connector design.

## Evidence and provenance

This is deliberately invented exercise data, **not grounded in Sokol111 implementation or a real marketplace**. Keep it separate from AIP's frozen C1 evidence; AIP v0.8 does not qualify this contract or observe a future connector-to-marketplace binding.

**Evolution:** changes to this fictional offer belong to the modeled marketplace role, not to a Catalog owner, a Product Query owner or AIP.
