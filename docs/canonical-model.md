# Canonical Model

Source adapters (OpenAPI, AsyncAPI, Architecture Manifest, and — for runtime data — the
OpenTelemetry adapter) never write directly to Neo4j. Each first maps its input into a shared
**Canonical Model** (`app/canonical/model.py`, Pydantic v2), decoupling parsers, graph persistence,
and different data sources from one another.

## Entities (`app/canonical/model.py`)

| Entity | Key fields |
|---|---|
| `Service` | `id`, `name`, `version` |
| `Operation` | `id`, `service_id`, `operation_id` (the OpenAPI `operationId`, optional), `method`, `path`, `request_schema_ids`, `response_schema_ids` |
| `Queue` | `id`, `name`, `protocol`, `namespace`, `queue_type` |
| `Message` | `id`, `name`, `version`, `schema_id` |
| `Schema` | `id`, `name`, `version`, `format`, `canonical_hash` (a content hash used to detect payload drift) |
| `Relation` | `type`, `source_id`, `target_id`, `evidence_ids` |
| `Provenance` / `Evidence` | see [`evidence.md`](evidence.md) |

`ArchitectureModel` is the container all of the above are collected into and passed between
pipeline stages: `services`, `operations`, `queues`, `messages`, `schemas`, `relations`,
`provenance`.

## Infrastructure entities and claims (`app/canonical/infrastructure.py`) — internal-only

v0.5.0 I2 (Kubernetes discovery) added the Canonical Model's *capacity* to carry Kubernetes
infrastructure facts, a category distinct from the application-level entities above. As of this
writing no adapter populates them yet (that begins with I2's own later increments) — but the whole
shared path they will travel already exists and is exercised: `merge_models`' dedup, cross-source
content-conflict detection, `validate_canonical_model`'s referential integrity, and the importer's
per-source ownership, write, reconciliation, and expiry machinery all handle them today.

| Entity | Key fields |
|---|---|
| `InfrastructureEntity` | `id`, `entity_kind` (`KUBERNETES_WORKLOAD` \| `KUBERNETES_POD` \| `KUBERNETES_NETWORK_SERVICE` \| `KUBERNETES_INGRESS`), `cluster_uid`, `api_group`, `resource_kind`, `namespace`, `name`, plus `service_type`/`ports` (meaningful only for `KUBERNETES_NETWORK_SERVICE`) |
| `InfrastructureContribution` | one source's own claim about an `InfrastructureEntity`: `entity_id`, `source_instance_id`, `evidence_mode` (`DECLARED_MANIFEST` \| `CAPTURED_RESOURCE`), `resource_semantic_digest`, `evidence_refs`, `mapping_rule_id`, `mapping_rule_version` |
| `InfrastructureClaim` | `kind` (`WORKLOAD_EXISTS` \| `WORKLOAD_OWNS_POD` \| `NETWORK_SERVICE_SELECTS_WORKLOAD` \| `INGRESS_ROUTES_TO_NETWORK_SERVICE`), `subject_id`, `object_id` (`None` for the unary `WORKLOAD_EXISTS` claim — no sentinel entity or self-edge), `evidence_refs`, `mapping_rule_id`, `mapping_rule_version` |

`ArchitectureModel` carries these as `infrastructure_entities`, `infrastructure_contributions`, and
`infrastructure_claims` alongside the application-level lists above.

They are persisted as their own Neo4j node labels (`:InfrastructureEntity`,
`:InfrastructureContribution`, `:InfrastructureClaim`), each carrying `owner_source_ids` exactly
like every other canonical node, so a source that stops emitting one retires it through the same
reconciliation path. All three are **nodes**, never relationships — `WORKLOAD_EXISTS` is a
first-class *unary* claim and §7.2 forbids inventing a sentinel entity or self-edge to force it into
a binary-relation shape, and keeping them off the relationship graph is also what stops them
reaching the deliberately untyped relation projection behind every MCP answer.

They remain **internal-only**: not exposed via REST or MCP, and absent from
`docs/graph-model.md`'s public node/relationship model. The one visible surface they do reach is
the ordinary `Evidence` record a Kubernetes source writes for its own provenance, which §9's
exposure table does not list among the non-exposed items. See the governing spec
(`docs/specifications/0.5.0/i2-kubernetes-discovery-vertical-slice.md` §7, §9) before assuming any
further exposure.

## Deterministic IDs (`app/canonical/ids.py`)

Every entity id is a stable, deterministic string, never a database-generated surrogate key and
never dependent on a local filesystem path — this is what lets imports from multiple repositories
merge conflict-free and lets a repeated import of the same source not create duplicates.

| Id kind | Format | Example |
|---|---|---|
| Service | `service:<slug>` or `service:<namespace>:<slug>` | `service:order-service` |
| Operation | `operation:<full-service-id>:<METHOD>:<path>` | `operation:service:product-service:GET:/products/{id}` |
| Queue | `queue:<name>` or `queue:<namespace>:<name>` | `queue:payment-q` |
| Message | `message:<name>` or `message:<name>:<version>` | `message:PaymentRequested:v2` |
| Schema | `schema:<name>` or `schema:<name>:<version>` | `schema:PaymentRequested:v2` |
| Evidence (declared) | `evidence:<source_type>:<service_slug>[:<revision>]` | `evidence:manifest:order-service` |
| Evidence (observed) | `evidence:otel:<environment>:<day>:<fact-hash>` | `evidence:otel:production:2026-08-26:b1d283d583bd` |

One detail worth calling out because it was the source of a real bug this project fixed
(11H-D): the `operation:` id is **always built from the full opaque service id** (e.g.
`service:product-service`), never from the bare source-layer slug (e.g. `product-service`). Every
place that mints an operation id — the OpenAPI adapter for declared operations
(`app/ingestion/openapi_adapter.py`) and the runtime resolver for a route it discovers but has
never seen declared (`app/telemetry/operation_resolver.py`) — must agree on this convention, or a
runtime-discovered operation and its later real OpenAPI declaration silently land on two different
graph nodes instead of reconciling onto one. See [`graph-model.md`](graph-model.md) for the
resulting `OBSERVED PROVIDES` reconciliation guarantee this enables.
