# Broker qualification: google-pubsub

**Spec:** v0.6.1 §6.1. **Role:** deterministic Broker-semantic expectations over the existing
`tests/fixtures/pubsub/google-pubsub` declarations.
**Retrieval date:** not applicable (authored; nothing is retrieved from a live system).

## Why this is a sibling of `tests/fixtures/pubsub/google-pubsub`

v0.6.1 spec §6.1 says to *extend* the existing broker-semantic fixtures. The Pub/Sub fixture trees
are frozen by the v0.5.0 I5 digest pin (`docs/real-world-validation/v0.5.0/coverage-matrix.md`,
`tests/unit/test_i5_lifecycle_freeze.py`, the fixtures' own `SHA256SUMS` and the golden path's
`SHA256SUMS`), so any added or edited file there would break those pins. The Broker expectations
are therefore sibling files over the **untouched** declarations at
`tests/fixtures/pubsub/google-pubsub/declarations`; the declarations, spans and I4 `expected.yaml` are not
edited, and `tests/integration/test_broker_qualification.py` re-asserts the I4 facts/entities
alongside the Broker expectations. This is a deliberate, documented deviation from "extend in place".

## Authored scenario data

Everything is authored. The scenario data are the existing declarations; every service declares one
server with `x-aip-broker-id: gcp-pubsub:projects/shop`.

## Expected facts

- the three services of the I4 Google Cloud Pub/Sub fixture all use the one project `gcp-pubsub:projects/shop`;
- exactly one Broker, `gcp-pubsub:projects/shop`, and one `Service -[USES_BROKER]-> Broker` per service listed in
  `expected.yaml` (`uses_broker`);
- each Broker claim's evidence resolves through `get_evidence` at the same snapshot to that exact
  fact; a Broker-aware answer is the v0.6 shape, drift stays v0.5;
- the Queue/Topic/Subscription entities and the in-scope relation facts are exactly the I4
  `expected.yaml` ones (the Broker adds no destination semantics);
- repeated runs (and reversed span order) are byte-identical for the Broker section.

## Forbidden facts

- a Broker per topic or subscription: the project is one Broker;
- any `USES_BROKER` for a service not listed, or a second Broker;
- a Queue, Topic, Subscription or Message beyond what the I4 `expected.yaml` establishes;
- the Broker standing in for a Subscription or consumer.

## Unsupported / deferred

Live broker discovery, `destinationBrokerMappings`, a generic `CONNECTED_TO` relation and
runtime-minted Brokers are not part of v0.6.1 and appear nowhere in this fixture.
