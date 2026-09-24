# I4 broker-semantic qualification fixtures

v0.5.0 I4 spec §13.3 requires three deterministic fixtures, authored independently of production
logic:

| Fixture | Role | Disclosure |
|---|---|---|
| [`azure-service-bus/`](azure-service-bus/PROVENANCE.md) | Positive: Queue competing consumers, and Topic fan-out through two Subscriptions | `PROVENANCE.md` |
| [`google-pubsub/`](google-pubsub/PROVENANCE.md) | Positive: one Topic with two Subscriptions, and several subscriber instances on one Subscription | `PROVENANCE.md` |
| [`kafka/`](kafka/PROVENANCE.md) | Negative boundary: a consumer group never becomes a Subscription | `PROVENANCE.md` |

Each fixture directory has four parts:
- `declarations/<service>/asyncapi.yaml`: AsyncAPI 2.6.0 source documents.
- `spans.yaml`: authored OpenTelemetry messaging spans.
- `expected.yaml`: the hand-authored expected result. It gives facts, OBSERVED facts, entities, dead-letter carriers, the per-source result and diagnostics, and the claims in each answer. It uses names only, never production ids. Anything not listed is forbidden, because the fact multiset is compared exactly.
- `PROVENANCE.md`: sources and retrieval date, authored data, expected and forbidden facts, and unsupported constructs.

The fixtures are executed by `tests/integration/test_i4_pubsub_qualification.py`. `SHA256SUMS` pins
every fixture file, and `tests/unit/test_pubsub_fixture_digests.py` checks it, so any change to a
fixture has to be deliberate. The sources are S1–S7 in
[`docs/specifications/0.5.0/i4-decision-evidence.md`](../../../docs/specifications/0.5.0/i4-decision-evidence.md),
all retrieved on 2026-09-23.
