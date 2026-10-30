# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(the AIP broker id `kafka:sokol111-local` is the current Redpanda broker). Consumer groups come from
request R1. R2 (the Helm values and topic configs) was not available.

## What moves

`ecommerce-catalog-service` and `ecommerce-image-service` move to Apache Kafka (`kafka:29092`).
Every other service stays on Redpanda, so the Catalog Management context boundary becomes a broker
boundary.

## Bindings that cross the boundary

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| product-query | catalog.product.events | outbound | yes (product-update-flow.md) | yes |
| product-query | catalog.attribute.events | outbound | no | yes |
| category-query | catalog.category.events | outbound | cannot tell | yes |
| category-query | catalog.attribute.events | outbound | no | yes |
| catalog-service | tenant.tenant.events | inbound | no | yes |
| image-service | tenant.tenant.events | inbound | no | yes |

Four of these six are undeclared in AIP (`PROMISE_COVERAGE_MISSING`). Only the broker attachments
show them, so the plan bridges every observed binding, not just the declared ones.

Two kinds of row need no bridge:
- **Inside the boundary:** image-service consumes `catalog.product.events`. It moves with its
  producers.
- **Outside the boundary:** both query services consume `tenant.tenant.events`. They stay on
  Redpanda with its producer.

## Bridge design

One MirrorMaker 2 process, `mm2-catalog-move`, runs from the pinned `apache/kafka:4.1.2@sha256:5cc2…`
image and has two one-way flows:

- `redpanda->kafka`: `tenant.tenant.events`
- `kafka->redpanda`: `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`

No topic is in both lists. `IdentityReplicationPolicy` keeps the topic names unchanged, so the
Redpanda consumers keep reading the topics they read today. The Kafka topics are new and empty, so
the outbound flow copies only events produced after the cutover. Nothing old is copied a second
time.

These features are turned off: heartbeats, checkpoints, group-offset sync, offset-syncs, ACL sync
and topic-config sync. That keeps the set of created objects small (container, four Kafka topics,
MM2's own internal topics). It also leaves Redpanda topic configs untouched.

## Why the cutover is ordered this way

`catalog.product.events` has producers in both services and an inside consumer (image-service).
It cannot be mirrored back into Kafka, because it is already mirrored out. So the steps are:

1. Stop catalog-service. Its unsent outbox rows wait in MongoDB.
2. Drain image-service on Redpanda to lag 0, then stop it.
3. Set the Kafka offsets explicitly:
   - tenant topic: the Redpanda committed offset 1, but only if the end offsets match;
   - image-service on `catalog.product.events`: earliest.
4. Point both services at Kafka. Start image-service first, then catalog-service.

Offsets are set explicitly and not left to auto-offset-reset, which is unknown (R2). The tenant
handler runs migrations and cleanups, so both skipping and replaying an event matter.

## Stop rules

Every check in P01, P02, P06, P08, P11 and P12 is a gate. If one fails, stop and report. Do not
continue.

## Verification and limits

P12 asks for the functional test (`OPERATOR: please run the functional test`). It then compares
the growth of end offsets on both brokers and checks lag 0 for every crossing group. The move is
not claimed to be lossless or exactly-once. MM2 is at-least-once, and delivery between the brokers
is not established beforehand.

Still open (see answers q5):
- the Helm file paths and keys, DLQ settings and partition counts (R2 not available);
- the point-in-time coverage of the consumer picture;
- the declared-only producers.

## Cleanup

MM2 stays running as the bridge. On an abort before P07, remove only `mm2-catalog-move` and the
topics recorded as created in P03 and P05, checking each name first. Never delete any existing
Redpanda group or topic.
