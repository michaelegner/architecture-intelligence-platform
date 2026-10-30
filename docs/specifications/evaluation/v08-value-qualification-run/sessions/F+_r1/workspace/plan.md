# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(binding picture for `catalog-management`, `local`, outcome PARTIAL, captured 2026-10-29T20:02:22Z).
In AIP, the broker id `kafka:sokol111-local` is the Redpanda broker that runs today.

## What moves, and what crosses the new boundary

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka. Everything else stays on
Redpanda. The binding picture, the Helm values and `rpk group describe` agree on these bindings:

| Consumer | Topic | Crossing | Documented | Observed |
|---|---|---|---|---|
| catalog-service | tenant.tenant.events | inbound | no | yes |
| image-service | tenant.tenant.events | inbound | no | yes |
| product-query | catalog.product.events | outbound | yes (product-update-flow.md) | yes |
| product-query | catalog.attribute.events | outbound | no | yes |
| category-query | catalog.category.events | outbound | yes (platform-overview.md, aggregate) | yes |
| category-query | catalog.attribute.events | outbound | no | yes |
| image-service | catalog.product.events | inside (moves along) | yes | yes |

Five of the six crossing bindings carry no promise in the event catalog (`PROMISE_COVERAGE_MISSING`),
and three are not in the docs at all. A plan built only from documentation would drop the
attribute topic and the tenant feed.

## Key design decisions

1. **Both services cut over together.** `catalog.product.events` has two producers, catalog
   (ProductUpdated/Deleted) and image (ProductImagePromoted). Both are in the moving context. If
   only one moved, the topic would have producers on both brokers and would have to be mirrored in
   both directions, which is forbidden. Both Deployments go to 0 and come back on Kafka in one step.
2. **Two one-way MM2 flows in a single MM2 process** (`mm2-catalog-move`, apache/kafka:4.1.2 image
   by digest, on `shared-network`):
   - `redpanda->kafka`: `tenant.tenant.events` only.
   - `kafka->redpanda`: `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`.
   No topic appears in both lists.
3. **`IdentityReplicationPolicy`**, because the services use fixed topic names (from the `-api`
   `topics.go` files). Without the source-alias prefix, MM2 has no cycle protection. So:
   - `emit.heartbeats.enabled=false`. MM2 always replicates `heartbeats`, which with the identity
     policy would flow both ways.
   - `emit.checkpoints.enabled=false`, `sync.group.offsets.enabled=false`. Offsets are set
     explicitly instead (see 5).
   - `sync.topic.configs.enabled=false`, `sync.topic.acls.enabled=false`, so Redpanda topic configs
     are not touched.
   - All replication factors are 1 (single-node brokers).
4. **Drain before switch.** With both moving services scaled to 0, every group must show lag 0 on
   Redpanda before anything is switched. This also confirms that nothing else is still producing to
   `catalog.*` on Redpanda: the log-end offsets must stay put. Unsent events in the transactional
   outbox (MongoDB) are published to Kafka after restart and reach Redpanda through the mirror.
5. **Offsets on Kafka.** The Kafka topics are created fresh with 1 partition, like Redpanda.
   `tenant.tenant.events` is copied from offset 0 with log-start 0, so the offsets should line up
   1:1. The executor checks this. Then, while the groups are empty, it sets
   `ecommerce-catalog-service` and `ecommerce-image-service` on Kafka `tenant.tenant.events` to the
   Redpanda committed offsets (1 at planning time). `ecommerce-image-service` on Kafka
   `catalog.product.events` starts at 0 of an empty topic. If the offsets do not line up, stop.
6. **Config change scope.** Only `config.kafka.brokers` changes, from `redpanda:29092` to
   `kafka:29092`, for the two moving services: in the local values files and in the live
   ConfigMaps. Tilt deployed with `helm template` and Tilt-built image tags, so re-rendering would
   change the images. The live ConfigMap is patched and the Deployment scaled back up instead.

## Sequence (see plan.json)

P00 preflight → P01 record live state → P02 scale catalog and image to 0, verify lag 0, record
offsets → P03 create Kafka topics → P04 write mm2.properties → P05 start MM2, verify the tenant
copy and that no heartbeats topic exists, record the created internal topics → P06 verify the
kafka→redpanda flow is up → P07 seed the Kafka group offsets → P08 switch brokers and scale up →
P09 verify groups on both brokers → P10 `OPERATOR: please run the functional test`, then verify
that the Redpanda catalog.* offsets advance and query-service lag returns to 0 → P11 rollback only on
failure → P12 leave MM2 running and delete nothing the plan did not create.

Every check is a gate. If one fails, the executor stops and reports it, and does not continue.

## mm2.properties (to be written by the executor in its workspace)

```
clusters = redpanda, kafka
redpanda.bootstrap.servers = redpanda:29092
kafka.bootstrap.servers = kafka:29092
redpanda->kafka.enabled = true
redpanda->kafka.topics = tenant\.tenant\.events
kafka->redpanda.enabled = true
kafka->redpanda.topics = catalog\.product\.events, catalog\.category\.events, catalog\.attribute\.events
replication.policy.class = org.apache.kafka.connect.mirror.IdentityReplicationPolicy
emit.heartbeats.enabled = false
emit.checkpoints.enabled = false
sync.group.offsets.enabled = false
sync.topic.configs.enabled = false
sync.topic.acls.enabled = false
replication.factor = 1
offset-syncs.topic.replication.factor = 1
checkpoints.topic.replication.factor = 1
heartbeats.topic.replication.factor = 1
config.storage.replication.factor = 1
offset.storage.replication.factor = 1
status.storage.replication.factor = 1
```

## What this does not establish

- MM2 is at-least-once. The move is **not** claimed to be lossless or exactly-once. Handler
  idempotency is unknown.
- Attachment is not handling: AIP and rpk show group assignments, not which events are processed.
- Producers are declared only. Only the drain check in P02 tests for unknown producers.
- Delivery across the bridge is unproven until P10.
- The planning session could not query Kafka itself (the command was denied). Kafka's emptiness and the image's
  presence come from TASK.md and are re-checked in P00.
- DLQ topics (`{topic}.dlq`) split across the brokers after the move and are deliberately not mirrored.
  None exist today.
