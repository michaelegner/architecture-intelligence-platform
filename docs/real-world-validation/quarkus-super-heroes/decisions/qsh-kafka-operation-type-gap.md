# Finding `qsh-kafka-operation-type-gap`

## System

quarkus-super-heroes

## Independent evidence

A dedicated diagnostic re-run of the qualifying I2.3 profile (`runbook.md` phases 1-9, unchanged;
`runtime/docker-compose.yml`'s Collector temporarily given a `verbosity: detailed` debug exporter
for this diagnosis only — no committed file was changed) captured the actual OTLP span `rest-fights`
exports for its Kafka `fights` publish:

```text
Attributes:
  messaging.kafka.offset: 0
  messaging.destination.name: fights
  messaging.operation: publish
  messaging.client_id: kafka-producer-fights
  messaging.system: kafka
```

(`docs/real-world-validation/quarkus-super-heroes/evidence/messaging.md` records the full context;
`results.md`'s "Kafka telemetry-recognition gap" section records this run.)

## Current AIP behavior

`app/telemetry/adapter.py::correlate_queue_observations()` reads the operation kind exclusively
from `messaging.operation.type` (`app/telemetry/semconv/messaging.py`'s `MESSAGING_OPERATION_TYPE`
constant), expecting the value `send`/`receive`/`process`. Quarkus's SmallRye Reactive Messaging
Kafka connector (at least at this Quarkus 3.39.1 pin) instead emits the plain `messaging.operation`
attribute with value `publish` — a real, valid OpenTelemetry messaging span, but keyed under an
attribute name AIP's allowlist does not check. `correlate_queue_observations()`'s own code comment
is explicit that a span with no recognized `operation.type` "is not a candidate observation at all
and is silently skipped, not reported as unresolved" — so this span never reaches `resolve_queue()`
at all, and produces no graph fact and no diagnostic trace of any kind.

## Classification

`INSUFFICIENT_EVIDENCE` — specifically for the narrower claim "this qualifying run validated that
AIP safely refuses to map the Kafka `fights` topic onto Queue semantics." The dossier's original
`UNSUPPORTED` classification for the Kafka mechanism itself (`qsh-kafka-fights-topic` in
`expected.yaml`) is **not** changed by this finding — Kafka topics remain outside AIP's supported
scope regardless. What changes is the *strength of the evidence* behind "AIP correctly emitted zero
`SENDS`/`RECEIVES_FROM` facts": that observation is real, but it does not by itself demonstrate a
safe rejection of *recognized* Kafka messaging telemetry, because no span with AIP-recognizable
`messaging.operation.type` semantics was ever produced by this profile to test that path.

## Severity

`MINOR` — bounded incompleteness in what this run's evidence establishes, with no false
architecture claim: AIP did not invent a relation, did not report a wrong direction, and did not
mislabel anything it actually processed. It simply never received the specific attribute shape that
would exercise the Topic-vs-Queue safety question at all.

## Decision

`DEFER`

## Rationale

Per the parent v0.3 spec's model-hardening rule (§23), a canonical/semantic correction is justified
only when it is general, precisely stated, and independently evidenced — and per §38, a new
protocol/attribute-recognition capability is exactly the kind of change I4 (cross-system model
hardening, informed by both Quarkus and Airflow findings) exists to evaluate, not a single I2.3 run
in isolation. Two considerations specifically argue for deferring rather than fixing now:

1. **One system's evidence is not enough to generalize an attribute-recognition change.** Whether
   AIP should also recognize the older, non-suffixed `messaging.operation` attribute (and under what
   values) is a question best answered after Airflow's own messaging/telemetry findings (I3) are
   available too, per the standing "one external system != sufficient evidence for a broad canonical
   redesign" principle.
2. **Widening recognition here is not merely additive — it activates the exact boundary this
   finding could not test.** If `correlate_queue_observations()` were changed to also accept
   `messaging.operation: publish`/`receive`/`process`, the very next qualifying run could have AIP
   map this Kafka topic onto `SENDS`/`RECEIVES_FROM` facts — which is precisely the "Queue semantics
   SHALL NOT be stretched to represent Topic semantics incorrectly" question the parent spec (§26)
   says should not be decided reflexively inside a single-iteration attribute fix. That question
   deserves its own explicit decision, informed by real evidence of what AIP would actually do once
   it can see these spans — not a side effect of closing a telemetry-recognition gap.

## Canonical-model impact

None in I2.3. A future iteration (I3/I4) may need to decide: (a) whether to widen
`MESSAGING_OPERATION_TYPE` recognition to accept the legacy `messaging.operation` attribute name,
and (b) — contingent on (a) — whether/how to prevent that widening from mapping topic/fan-out
messaging systems onto AIP's competing-consumer Queue model, per the parent spec's Topic/Subscription
model boundary (§26).

## Compatibility impact

None — no production code changed in this decision record.

## Required implementation change

None in I2.3. Deferred to I3/I4 as described above.

## Regression coverage

None required now (no implementation change). If a future iteration widens attribute recognition,
it SHALL add: (1) a regression test proving the legacy `messaging.operation` attribute is now
recognized, and (2) a regression test proving the resulting fact does not silently violate the
Topic-vs-Queue safety boundary (e.g. an explicit `UNSUPPORTED`/refusal path for topic-shaped
messaging systems, or a documented, deliberate decision to accept the risk).
