# Plan: move Catalog Management from Redpanda to Apache Kafka

AIP snapshot cited throughout: `aip:snapshot:v1:18d59102a7c451ae8e84d3acaf3d2c6b036ff105ec14a59f255c2be0ffda906e`
(bounded context `catalog-management`, environment `local`).

## What moves, and what crosses the boundary

`ecommerce-catalog-service` and `ecommerce-image-service` move to Kafka (`kafka:29092`). The tenant
service and both query services stay on Redpanda. Once the move is done, the catalog-management context
is also the boundary between the two brokers.

AIP's binding picture and my own `rpk group describe` agree on every attachment. They give these crossing bindings:

| Consumer | Topic | Direction | Documented | Observed |
|---|---|---|---|---|
| ecommerce-catalog-service | tenant.tenant.events | inbound | no | yes |
| ecommerce-image-service | tenant.tenant.events | inbound | no | yes |
| ecommerce-product-query-service | catalog.product.events | outbound | yes (product-update-flow.md) | yes |
| ecommerce-product-query-service | catalog.attribute.events | outbound | no | yes |
| ecommerce-category-query-service | catalog.category.events | outbound | cannot tell (platform-overview.md lumps "Product and Category Query Services") | yes |
| ecommerce-category-query-service | catalog.attribute.events | outbound | no | yes |

`ecommerce-image-service × catalog.product.events` is INSIDE. Both producers of that topic (catalog
for ProductUpdated, image for ProductImagePromoted, per the `topics.go` files) and its consumer move
together, so that binding needs no mirroring. It does need both services switched in the same
window (see "Cutover order"). The query services' tenant bindings are NONE and are not affected.

Five of the six crossing bindings have no catalog promise (`PROMISE_COVERAGE_MISSING`). Only the
broker capture and the Helm values show them. The two attribute-event bindings in particular are
named in no document.

## Mirror flows (MirrorMaker 2, one process, two flows)

- **redpanda → kafka:** `tenant.tenant.events` only. The producer, tenant-service, stays on Redpanda.
  Group-offset sync is on for `ecommerce-catalog-service` and `ecommerce-image-service`, so they
  resume at their translated position instead of replaying from earliest.
- **kafka → redpanda:** `catalog.product.events`, `catalog.category.events`, `catalog.attribute.events`.
  These are mirrored back into the existing Redpanda topics, where the query services keep their
  groups and committed offsets.

No topic appears in both allow-lists. `IdentityReplicationPolicy` keeps topic names unchanged, which
the query services need because their config names the topics literally. Heartbeats are disabled.
With identity naming, a `heartbeats` topic would exist on both sides and could be mirrored in both
directions. The allow-lists are explicit escaped names, not wide regexes.
`sync.topic.configs` and ACL sync are off, so MM2 does not alter the Redpanda topics.
Offset-syncs go to the target, and the kafka→redpanda flow emits no checkpoints or offset-syncs.
This keeps the extra internal topics on Redpanda to a minimum.

**Deliberately not done: copying Redpanda history of `catalog.*` into Kafka.** It would mean mirroring
those topics redpanda→kafka as well as kafka→redpanda, which is forbidden. The Kafka copies start empty.
This is safe only if the image service has consumed everything on Redpanda before it switches. The plan
checks that.

MM2 runs as container `mm2-catalog-move` from
`apache/kafka:4.1.2@sha256:5cc2a2fd…772e0e` with `--pull never` on `shared-network`. Its config is
`mm2/mm2.properties` in the workspace.

## Cutover order

1. Run preflight checks: the Redpanda baseline, Kafka being empty, pods able to reach `kafka:29092`,
   and the image being present. I could not list Kafka from this session, so emptiness is a real check,
   not a formality.
2. Create the Kafka topics with 1 partition each, because Kafka has `auto.create.topics.enable=false`:
   the three `catalog.*` topics, `tenant.tenant.events`, and `tenant.tenant.events.dlq`. Both moved
   services enable a DLQ for tenant events, and the DLQ name defaults to `{topic}.dlq`.
3. Scale catalog-service to 0. That stops new catalog events on Redpanda. Wait for the image-service
   lag on `catalog.product.events` to reach 0, then scale image-service to 0. If the lag is not 0,
   stop. Any event left unconsumed on Redpanda would never reach the image service on Kafka.
4. Start MM2. Check that the tenant topic copy reaches the Redpanda end offset, and that translated
   offsets exist on Kafka for both moved groups. If either check fails, stop and let the operator decide.
   The fallback is replay from earliest, which means duplicate tenant events.
5. Switch `kafka.brokers` to `kafka:29092` for the two services. Do this in the live ConfigMaps
   (`<name>-config`, mounted via subPath) and in the workspace values files, so a later Tilt run keeps
   the change. Do not re-render the Deployments with Helm, because the pods run Tilt-built
   `localhost:5000/...` images that the values file does not reference.
6. Scale both services back to 1. Check that their groups attach on Kafka.
7. Verify end to end with broker tools. After a catalog change, offsets grow on Kafka and then on
   Redpanda, and the query-service lag returns to 0. After a tenant event, it appears on the Kafka copy.
   Then ask the operator to run the functional test and wait for the result.

Every check in this list stops the run and is reported if it fails.

## Rollback and cleanup

Rollback: scale the moved services to 0, restore `redpanda:29092` in the two ConfigMaps and values
files, scale them back up, and stop MM2 last. Anything they produced on Kafka in the meantime is
already on Redpanda through the mirror. The image service will then re-read some product events
from Redpanda, so duplicates are possible.

Cleanup deletes only what the plan created, and each name is checked before it is deleted: the
`mm2-catalog-move` container, the Kafka topics from step 2, the MM2 internal topics (found by diffing
against the baseline topic lists), and `mm2/mm2.properties`. Pre-existing Redpanda topics and groups
are never deleted.

## Limits

The move is not claimed to be lossless or exactly-once. MM2 is at-least-once, and a consumer
attachment does not show that events are handled. AIP never establishes delivery between brokers.
Its broker id `kafka:sokol111-local` is the declared id of the current broker, which is Redpanda,
not of the new Kafka container. The capture covers only configured groups at one moment, so the
binding list may be incomplete. Producers are declared, not observed. More detail is in
`answers.json` under q5.
