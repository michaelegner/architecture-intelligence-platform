# Ingestion & Source Adapters

Three source adapters map declared architecture documents into the Canonical Model
(`app/canonical/model.py`). A fourth, the Kubernetes adapter (below), maps a different category —
internal-only infrastructure facts, not application-level architecture. None of them ever writes to
Neo4j directly — see [`architecture.md`](architecture.md) for where they sit in the pipeline.

## OpenAPI adapter (`app/ingestion/openapi_adapter.py`)

Extracts the **provider** side only: service metadata, HTTP method/path, `operationId`, and
request/response schemas. It cannot know who *calls* an operation — OpenAPI documents describe
what a service offers, not who consumes it.

## AsyncAPI adapter (`app/ingestion/asyncapi_adapter.py`)

Extracts queue-based communication: queue/channel name, send/receive direction, message name and
version, payload schema, and dead-letter-queue mapping. `Queue` and `Message` are deliberately kept
as **separate entities** — queue/DLQ/transport semantics stay independent of message payload
semantics so they can be analyzed and versioned independently. Competing consumers (multiple
runtime instances of the same logical service) are not modeled as separate nodes in this static
model.

### Topic and Subscription (v0.5.0 I4)

An AsyncAPI Channel is a source-language construct. It is never automatically a Queue, a Topic or a
Subscription.

**Kind.** `x-aip-destination-kind` admits exactly `queue` and `topic`.
- **Topic eligibility:** a Topic needs **both** positive Topic-kind evidence and a qualified Topic
  identity.
  - Positive evidence is `x-aip-destination-kind: topic`, or a valid `topicMappings` entry at the
    Channel pointer.
  - A qualified identity is a stable broker id from `x-aip-broker-id` together with the namespace
    (the AMQP `virtualHost`, else empty), or an agreeing configured full `topic:` id.
- **Never Topic evidence:** protocol, vendor, a `publish` or `subscribe` operation, AMQP
  `is: routingKey`, and the absence of Queue evidence never establish a Topic.
- **Contradictions:** contradictory Queue and Topic evidence is `REJECTED_CONFLICT`.
- **Other kind values:** any other value, such as `pubsub`, keeps I1's behaviour. It is a non-Queue
  vote, and the Channel is omitted with `QUEUE_EVIDENCE_MISSING`. It becomes a Topic only if a valid
  `topicMappings` entry also exists at that Channel.

**Publish and subscribe.** For a qualified Topic:
- A `publish` operation maps to `Service -[PUBLISHES_TO]-> Topic` and `Topic -[CARRIES]-> Message`.
- A `subscribe` operation needs an explicit Subscription identity. That is `x-aip-subscription-name`,
  or a `subscriptionMappings` entry at that exact subscribe-operation pointer. When both are present,
  their names and Topic ids must agree.
  - It maps to `Subscription -[SUBSCRIPTION_OF]-> Topic` and `Service -[RECEIVES_FROM]-> Subscription`.
  - Without an explicit identity, AIP never synthesizes one from the Service name, Channel name,
    `operationId` or consumer group (for example `x-aip-consumer-group`). The subscribe side is
    omitted, the source is `ACCEPTED_WITH_LIMITATIONS`, and the diagnostic is
    `SUBSCRIPTION_IDENTITY_MISSING` at the subscribe pointer.

**Dead-letter configuration.** A Subscription dead-letter configuration is declared on the subscribe
operation as `x-aip-subscription-dead-letter: {target, targetKind?}`. It is kept only as an internal
`SubscriptionDeadLetterConfiguration` token. It never becomes a `DEAD_LETTERS_TO` relation or a
target entity, because broker dead-letter semantics differ.

**Diagnostics and scope.** I4 added exactly three diagnostic codes: `TOPIC_IDENTITY_CONFLICT`,
`SUBSCRIPTION_IDENTITY_CONFLICT` and `SUBSCRIPTION_IDENTITY_MISSING`. Parameterized channel addresses
such as `orders/{region}` are literal identity inputs. AsyncAPI 3.x remains `REJECTED_UNSUPPORTED`.
See spec `docs/specifications/0.5.0/i4-source-independent-pubsub-semantics.md` §8 and ADR 0017.

### Shared-identity mapping artifact

Operators can configure versioned mapping files under `sources.migrations` in the config. They are
loaded by `app/sources/migration_mappings.py`, and each has `apiVersion: aip.dev/v1` and
`kind: AipSharedIdentityMappings`.
- **What an entry does:** each entry binds an exact `(sourceInstanceId, documentPath, pointer)` to a
  full canonical id.
- **Arrays:** `schemaMappings`, `messageMappings` and `queueMappings` come from v0.5.0 I1.
  `topicMappings` (`topicId`) and `subscriptionMappings` (`topicId`, `subscriptionName`,
  `subscriptionId`) come from I4.
- **Kind evidence:** a `topicMappings` entry is also positive Topic-kind evidence for its Channel.
- **Agreement:** a configured id must agree with the derived id, or the source is rejected with the
  matching `*_IDENTITY_CONFLICT`. Malformed entries use the `MIGRATION_MAPPING_*` diagnostics.
- **Digest:** every mapping array always contributes to the `mapping_context_digest`. Empty
  `sharedTopicMappings` and `sharedSubscriptionMappings` keys are included too, so adopting I4 changed
  every pre-I4 context digest once.

## Architecture Manifest adapter (`app/ingestion/manifest_adapter.py`)

Reads `architecture.yaml` — the only source that can close the "who calls this REST operation" gap,
since OpenAPI alone only describes providers. The manifest is deliberately minimal: it must only
contain information not already reliably derivable from OpenAPI/AsyncAPI. `ManifestSourceAdapter`
runs at `dependency_phase=1` (`app/sources/registry.py`), so it resolves each declared call against
an `operation_index` it builds from `upstream_model` — every phase-0 adapter's merged real
`Operation.id` values — the manifest adapter itself never constructs an operation id independently,
so it can never drift out of sync with however operation ids are actually minted.

## Kubernetes adapter (`app/ingestion/kubernetes_adapter.py`)

`OFFLINE_ONLY` (v0.5.0 I2): maps a frozen, versioned Kubernetes resource snapshot envelope — never a
live cluster connection, kubeconfig, watch, or cluster write — into internal-only infrastructure
entities/claims (`app/canonical/infrastructure.py`), not the application-level `ArchitectureModel`
lists above. Two immutable per-source evidence modes: `DECLARED_MANIFEST` (attributable declarations,
no claim of API presence) and `CAPTURED_RESOURCE` (presence in a bounded capture, requiring real
`uid`/`resourceVersion`, never fabricated). Admits eight resource kinds (`Namespace`, `Deployment`/
`StatefulSet`/`DaemonSet`, `Pod`, `ReplicaSet` — an internal owner-chain bridge only, never promoted
to its own entity — `Service`, `Ingress`) and produces four entity kinds and four claim kinds:
`WORKLOAD_EXISTS`, `WORKLOAD_OWNS_POD`, `NETWORK_SERVICE_SELECTS_WORKLOAD`,
`INGRESS_ROUTES_TO_NETWORK_SERVICE`. It never establishes application interaction (no `CALLS`/
`SENDS`/`RECEIVES_FROM`/`DEPLOYED_AS`) and never evaluates the
`architecture-intelligence.io/service-id` annotation into an AIP Service identity — that annotation
is retained verbatim as unqualified input. v0.5.0 I3's deployment reconciliation
(`app.architecture_intelligence.deployment_reconciliation`, "Path A") is what actually evaluates it
against declared Service identity to produce a public `DEPLOYED_AS` claim, at query time, never at
ingestion time — see [`evidence.md`](evidence.md) and [`graph-model.md`](graph-model.md) for the
resulting public shape. See the governing spec
(`docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md`) and
[`canonical-model.md`](canonical-model.md#infrastructure-entities-and-claims-appcanonicalinfrastructurepy--internal-only)
for the full contract, limitations, and internal-only exposure boundary.

## Service-Workload mapping artifact (`app/sources/service_workload_mapping.py`, v0.5.0 I3 Path B)

A sibling configured input to the Kubernetes adapter above, not a Kubernetes resource itself: exactly
one local, versioned YAML artifact (`SourcesConfig.service_workload_mapping`) naming explicit
Service↔Workload identity mappings the Kubernetes adapter's own annotation reading (Path A) doesn't
cover.

```yaml
apiVersion: aip.dev/v1
kind: ServiceWorkloadIdentityMappings
metadata:
  id: v0.5.0-service-workload-identities
  revision: <non-empty version/revision>
mappings:
  - mappingId: checkout-runtime
    serviceId: service:checkout
    kubernetesSourceId: checkout-cluster
    clusterUid: 599e90a5-7ab8-426f-807f-92a65dcc8822
    workload:
      apiGroup: apps
      kind: Deployment
      namespace: checkout
      name: checkout
```

Every property shown above is required; unknown top-level or entry fields are rejected outright, and
remote references, environment substitution, templating, shell execution, and implicit aliases are
all prohibited — this is a plain, fully self-contained declaration, not a template. Supported
`workload.kind` values are exactly `Deployment`, `StatefulSet`, `DaemonSet`.

A mapping entry resolves (`RESOLVED_CONFIGURED`) only when its `serviceId` names exactly one existing
declared AIP Service, its `kubernetesSourceId`/`clusterUid` identify the currently configured I2
source, and its `(apiGroup, kind, namespace, name)` identifies exactly one current I2 Workload — a
mapping to a missing Service or Workload is `UNRESOLVED`. Two entries naming the same Workload but
different Services are `CONFLICT`; file ordering never selects a winner. Identical duplicate entries
are normalized deterministically, never treated as two separate mappings. See
[`graph-model.md`](graph-model.md#deployed_as-v050-i3--computed-not-a-stored-graph-edge) for how this
combines with Path A/C into the public `DEPLOYED_AS` claim, and [`evidence.md`](evidence.md) for how
a mapping entry's own evidence is encoded and exposed.

## Runtime observation adapter

Independently of the three above, `app/telemetry/adapter.py` maps OpenTelemetry spans into observed
facts. It's architecturally a different kind of adapter — it produces an `ObservationBatch`
(possibly-new entities + evidence-backed facts + unresolved observations), not an
`ArchitectureModel` — see [`opentelemetry.md`](opentelemetry.md) for its full contract and
[`adapter-development.md`](adapter-development.md) for how it fits the general extension point.
