# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot cited throughout: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(binding picture, `catalog-management` / `local`, outcome PARTIAL, capture 2026-10-29T20:02:22Z).

## What moves

`ecommerce-catalog-service` and `ecommerce-image-service` (bounded context `catalog-management`) move to
Kafka. Tenant, product-query and category-query services stay on Redpanda. Today all five services use
`redpanda:29092`.

## Bindings across the new broker boundary

Sources: AIP, the local Helm values, the source code (`TopicFor` call sites) and
`rpk group describe` on the running Redpanda. All four agree.

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| catalog-service | tenant.tenant.events | inbound | no | yes |
| image-service | tenant.tenant.events | inbound | no | yes |
| product-query-service | catalog.product.events | outbound | yes (product-update-flow.md, by event name) | yes |
| product-query-service | catalog.attribute.events | outbound | no | yes |
| category-query-service | catalog.category.events | outbound | cannot tell (overview pairs "category events" only with a combined "Product and Category Query Services" node) | yes |
| category-query-service | catalog.attribute.events | outbound | no | yes |

`image-service × catalog.product.events` is INSIDE the context and moves with it. The query services'
own `tenant.tenant.events` bindings are NONE: they do not cross the boundary and stay on Redpanda.

Only one of the six crossing bindings is clearly documented. Five are UNRESOLVED / PROMISE_COVERAGE_MISSING
in AIP: observed, but not declared. A plan built from the docs alone would miss the attribute flow and the
tenant inbound flow.

## Design

- **Two MM2 flows, one direction per topic** (dedicated mode, one container `mm2-catalog`, Kafka
  image by digest):
  - `redpanda->kafka`: `tenant.tenant.events`
  - `kafka->redpanda`: `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`
- **IdentityReplicationPolicy**, so topic names do not change. The query services keep reading the
  existing Redpanda topics, and their committed offsets (120 / 20 / 4) stay valid because mirrored records
  are appended. The moved services keep their topic names on Kafka. Identity naming cannot detect
  cycles, so one direction per topic is essential, not just a rule. It is safe because, per the source,
  catalog.* is produced only by the two moving services and tenant.tenant.events only by tenant-service.
- Allow-lists are exact, anchored regexes, so `*.dlq` and internal topics are not mirrored.
  Checkpoints, group-offset sync, heartbeats, topic-config sync and ACL sync are off. This keeps MM2's
  footprint small and keeps it from changing Redpanda topic configs.
- Kafka topics are created up front with 1 partition, matching Redpanda. This keeps per-`product_id`
  order and a 0→0 partition mapping.
- New Kafka consumer groups start from **earliest**, the services' configured reset. No offset
  translation is used. The tenant history is replayed: duplicates are possible, nothing is skipped.

## Sequence and gates (details in plan.json)

1. **P01 / G0**: inventory both brokers, the groups, the containers and the live ConfigMaps. Kafka must be empty.
2. **P02**: create the 4 topics on Kafka.
3. **P03–P04**: write `mm2/mm2.properties` in the workspace and start MM2 from the local image (no pull).
4. **P05 / G1**: the tenant topic offsets match on both brokers, no prefixed topics exist, and the
   new internal topics are recorded by name.
5. **P06 / G2**: scale catalog-service to 0 (the outbox holds new events), drain image-service to lag 0 on
   Redpanda, scale it to 0, and record the end offsets E1. Draining matters: image-service starts a new
   group on an empty Kafka topic, so anything left unconsumed on Redpanda would be lost to it.
6. **P07**: change `kafka.brokers` to `kafka:29092` in the two local values files. Check that the live
   ConfigMap equals the file, then patch it. No Helm or Tilt redeploy, because the pods run Tilt image tags.
7. **P08 / G3**: scale both services up. On Kafka the groups are attached with lag 0, and the Redpanda
   groups are Empty.
8. **P09**: compare offsets in each direction, then `OPERATOR: please run the functional test` and wait.
   Compare again afterwards.
9. **P10**: MM2 stays running. Idle groups and pre-existing topics are not deleted. Rollback and abort
   delete only names recorded as created in P02 and P05.

Any failed check stops the run, with the result reported.

## What this does not establish

- Delivery between brokers. AIP never shows it, so it is shown only by the post-move offset deltas and the
  functional test. **There is no claim of lossless or exactly-once delivery.** It is at-least-once with
  possible duplicates.
- The consumer list may be incomplete: the capture covers only configured groups at one point in time.
  An attachment also does not show which event types are handled.
- Producers come from declarations and source only. The one-direction premise must be re-checked after the
  move by watching for non-mirrored writes.
- AIP has no capture of the new Kafka broker (its `kafka:sokol111-local` id is today's Redpanda).
- DLQs split by broker after the move.
- Brief write downtime for catalog and image while they are scaled to 0.
