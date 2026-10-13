# AIP v0.8.0 — Candidate Comparison, Round 3

**Status:** Completed  
**Input:** Round 2 survivors  
**Purpose:** Compare the remaining candidates with one concrete bounded change each and identify the best systems for the final v0.8 PoC.

## 1. Goal

Round 3 SHALL test:

> **With all relevant repositories and existing agent-readable context available, does independent distributed-system evidence change what a coding agent needs to inspect before making a bounded change?**

Teamscale is **not part of Round 3**. It belongs to the later technical spike / final PoC.

## 2. Candidates

Evaluate the seven Round 2 survivors:

- Sokol111 ecommerce workspace
- daonhan/Microservices-in-.NET
- sminerport/eCommerceMicroservices
- mehdihadeli/food-delivery-microservices
- JYC11/koupang
- dotnet/eShop
- hungCS22hcmiu/ecommerce-system

## 3. One concrete task per candidate

Choose one realistic bounded change per system, preferably an event or API contract change.

Example:

> Change the payload of a catalog, order, payment, or inventory event.

The change must have a plausible cross-service investigation boundary.

## 4. Compare two views

### Coding-agent/source baseline

Determine what a strong coding agent can establish using:

- all relevant repositories;
- source and configuration;
- `CLAUDE.md`, `AGENTS.md`, ADRs and repository documentation.

### Independent distributed evidence

Determine what evidence outside ordinary source dependency analysis can independently establish, such as:

- runtime producer/consumer spans;
- broker topic or queue relationships;
- runtime service identity;
- deployment topology;
- environment-specific configuration or routing.

No AIP implementation is required yet.

## 5. Candidate record

| Field | Content |
|---|---|
| Candidate | System |
| Change | Concrete bounded task |
| Expected investigation boundary | Relevant services/components |
| Coding-agent baseline | What source + agent context establishes |
| Distributed evidence | What independent evidence establishes |
| Material difference? | Yes / unclear / no |
| PoC effort | Low / medium / high |
| Verdict | Finalist / reject |
| Reason | Short justification |

The decisive field is **Material difference?**

## 6. Exit criteria

Reduce the seven candidates to approximately **2–3 finalists**.

A finalist must provide:

> **A realistic bounded change where independent distributed-system evidence plausibly changes the coding agent's investigation boundary beyond what all available source and repository-native context can safely establish.**

At least one finalist SHOULD have strong coding-agent-native context such as `CLAUDE.md` or `AGENTS.md`.

The finalists become the input for the Round 4 technical spike.
