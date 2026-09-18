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
`SENDS`/`RECEIVES_FROM`/`DEPLOYED_AS`) and never evaluates the `architecture-intelligence.io/
service-id` annotation into an AIP Service identity — that annotation is retained verbatim as
unqualified input for I3. See the governing spec
(`docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md`) and
[`canonical-model.md`](canonical-model.md#infrastructure-entities-and-claims-appcanonicalinfrastructurepy--internal-only)
for the full contract, limitations, and internal-only exposure boundary.

## Runtime observation adapter

Independently of the three above, `app/telemetry/adapter.py` maps OpenTelemetry spans into observed
facts. It's architecturally a different kind of adapter — it produces an `ObservationBatch`
(possibly-new entities + evidence-backed facts + unresolved observations), not an
`ArchitectureModel` — see [`opentelemetry.md`](opentelemetry.md) for its full contract and
[`adapter-development.md`](adapter-development.md) for how it fits the general extension point.
