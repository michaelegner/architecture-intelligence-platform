# DEMO-CONTRACT-001 — External marketplace withdrawal processing

**Status:** `DEMO_CONTRACT_ASSUMED` — **independent fictional external marketplace offer**, not a contract or policy of any real marketplace  
**Modeled offeror:** external marketplace platform role (separate from Sokol111)  
**Audience:** permitted third-party listing publishers  
**Scope and version:** hypothetical demonstration marketplace, fixture v3

## Capability offered

A permitted publisher may submit an authenticated withdrawal request for an existing listing within its authorized merchant/channel scope. The marketplace **accepts or rejects** the request according to this fictional contract. **For an accepted, valid request, the marketplace offers processing and a queryable outcome: completed (the listing is no longer publicly visible) or failed (with an indication that further action may be necessary).**

This contract **does not promise a fixed time from request acceptance to completed withdrawal**. Request acceptance and externally visible listing removal are distinct stages; neither an acknowledgement nor a pending status establishes withdrawal.

## Applicability, exclusions and independent authority

- Only valid, authenticated, correctly scoped and accepted requests fall under the fictional processing promise.
- A rejection, unavailable endpoint, request never received, or no accepted request creates no processing commitment under this offer.
- Completion means **the external listing is no longer visible**, which is distinct from acceptance, a pending status, or merely initiating withdrawal.

## Evidence and provenance

This is deliberately invented exercise data, **not grounded in Sokol111 implementation or a real marketplace**.

**Evolution:** Only the modeled marketplace role may revise this fictional offer.
