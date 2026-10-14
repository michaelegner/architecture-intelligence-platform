# Round 4 — Result: neither finalist is suitable

**Spec:** [spec-round4-finalist-technical-spike.md](spec-round4-finalist-technical-spike.md) §10, §12, §13  
**Date:** 2026-10-13

Per §13: *"If neither candidate is fair and technically viable, record that result rather than
weakening the baseline or changing AIP semantics to force a selection."* That is the result.

## Verdicts

| Candidate | Verdict | Deciding reasons |
|---|---|---|
| Sokol111 ecommerce workspace | **Reject** | Semantic gap: Product Query and Image consume `catalog.product.events` as separate Kafka consumer groups, and current AIP (even with perfectly conformant spans) leaves consumers unresolved by design. Ingestion gap: emitted spans use legacy `messaging.destination` and no `messaging.operation.type`, so AIP ignores them. Live run needs the tenant service, Logto and MinIO (setup cost high). Details: [feasibility](round4-sokol111-feasibility.md) |
| sminerport/eCommerceMicroservices | **Reject** | Semantic gap: headers-exchange binding predicates cannot be represented. Ingestion gap: no RabbitMQ topology source. No OpenTelemetry at all. Details: [spike](round4-sminerport-spike.md) |

No fallback is nominated: neither candidate meets selection rule §10 items 3 and 5 (a cross-boundary
question beyond source that independent evidence answers *and* current AIP can represent).

## What was established (handoff material, §12)

- **Both coding-agent baselines were strong** ([Sokol111](round4-sokol111-baseline.md),
  [sminerport](round4-sminerport-spike.md)): the static producer/consumer boundary was found from
  source and config alone. The open questions each left are genuine and runtime-only: whether
  consumers/bindings are live, deployed versions, undeclared consumers.
- **Those open questions are consumer-side or broker-state questions.** For Kafka, AIP cannot
  attribute consumers (consumer group ≠ Subscription); for RabbitMQ headers exchanges it has no
  representation of routing predicates or a topology source. The same shape that makes these
  scenarios interesting is the shape AIP currently cannot express.
- **Producer→Topic observation does work** with conformant keys (Sokol111 variant D), so a system
  whose consumers are attributable (Pub/Sub or Service Bus style subscriptions, or Kafka with a
  qualified consumer-attribution rule) is the shape current semantics support.
- **Real systems rarely emit the keys AIP reads.** Sokol111's hand-written spans were not
  recognised at all; a candidate screen should check emitted `messaging.operation.type` /
  `messaging.destination.name` before the spike.
- **"Standalone" configs and READMEs are not evidence of a runnable slice.** Sokol111's services
  hard-require multi-tenancy.

## Decision for the owner (not made in Round 4)

Round 4 does not decide the v0.8 direction. The options this result leaves, none implemented:

1. **Return to the Round 2–3 reserves** with the new screen (attributable consumers; conformant or
   mappable span keys; runnable minimal slice), e.g. a candidate with Pub/Sub-style subscriptions.
2. **Treat Kafka consumer attribution as a v0.8 product question** (a semantic change, which
   Round 4 may not make) and re-run Sokol111 afterwards; its source baseline and frozen revisions are
   reusable.
3. **Use an existing AIP-supported demo system** (Pitstop, already in AIP) as the v0.8 validation
   system, accepting that it is not an independent third-party system.

## Exit criteria (§13)

| Criterion | Status |
|---|---|
| Selected system or explicit "neither suitable" | Done: neither |
| Frozen bounded-change scenario | Done for both (`ProductUpdatedEvent`; `product.update`) |
| Exact repository revisions | Done: freeze docs |
| Documented coding-agent/source boundary | Done: both baselines |
| Independent distributed evidence identified | Done: Kafka/OTel spans (source-derived, not live); RabbitMQ topology (not captured) |
| Reproducible evidence-capture path | Partial: Sokol111 live attempt scripts and replay probe in `round4-evidence/`; live capture failed at the stop condition; sminerport not captured |
| What AIP can / cannot establish | Done |
| Gaps classified | Done |
| Select / fallback / reject rationale | Done |

## Limitations of this round

- One agent run per baseline; plugins visible but unused (disclosed in each baseline).
- Sokol111 spans are source-derived; no live telemetry was captured.
- sminerport feasibility rests on reading AIP docs/code, not on an ingestion experiment, because no
  topology source or spans exist to ingest.
