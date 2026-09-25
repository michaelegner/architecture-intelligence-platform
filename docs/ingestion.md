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

The manifest never mints a Service either. Its caller (resolved from its own `x-aip-service-id`,
a configured mapping, or an identity binding) must be declared by a phase-0 source, normally the
caller's own OpenAPI or AsyncAPI. If no discovered source declares it, the manifest is
`REJECTED_UNSUPPORTED` with `MANIFEST_CALL_SOURCE_UNRESOLVED` (pointer `/x-aip-service-id`, or `""`
when the identity came from elsewhere), exactly like an unresolved call target
(`MANIFEST_CALL_TARGET_UNRESOLVED`). A manifest without calls emits no CALLS and is not checked.

## Canonical validation

After every source is mapped and merged, discovery validates the merged model against the canonical
invariants (V1-V8, `app/validation/canonical_validation.py`) before any reconciliation plan exists
(I1 §7). Each violation names the elements it implicates: entity ids, and relations as
`TYPE:source_id:target_id`. It is attributed to every source that emitted one of them:
- each such source gets a `CANONICAL_MODEL_INVALID` diagnostic per violation, pointing at the
  lowest implicated element it emitted, and becomes `REJECTED_INVALID` (unless it was already
  rejected);
- the run is `PARTIAL`, or `FAILED` if some violation cannot be attributed to any source (it is then
  a run-level diagnostic);
- nothing commits, and every source keeps exactly one result (I1 §6, §10).

This is a safety net behind the adapters' own checks. Before v0.5.0 I5 finding F1, the importer ran
the validation after the commit gate, and a violation escaped `POST /api/import` as HTTP 500 with no
per-source result.

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

## Import report (v1)

`POST /api/import` and `POST /api/import/service/{serviceId}` return the versioned I1 §10 import
report, `report_version: "aip-import-report/1"` (v0.5.0 I5 finding F2). Its models are in
`app/ingestion/import_report.py`, and the JSON Schemas are committed under `schemas/import/v0.5/`.
The schemas are regenerated with `uv run python -m app.ingestion.import_report_schema`, and a test
fails if the committed schemas drift from the models.

The report is **additive**. `import_id`, `committed` (true only if every configured run committed)
and `sources` (the per-source reconciliation stats) keep their pre-v1 meaning. `runs` adds one
entry per configured source run, ordered by `(kind, configured_source_id)`:

| Field | Meaning |
| --- | --- |
| `kind`, `configured_source_id` | `filesystem` or `kubernetes`, and the configured source's id |
| `discovery_scope_id`, `scope_definition_digest` | the run's scope identity (I1 §6), or null when discovery could not compute it |
| `inventory_status`, `committed` | `COMPLETE`, `PARTIAL` or `FAILED`, and whether the run committed |
| `inventory_revision` | the inventory revision the run committed; null when it did not commit |
| `source_results` | **every** discovered source's own result (I1 §10: exactly one per source), including the rejected sources of a run that did not commit. Each entry is described in the next table. |
| `removals` | each source the run removed, with its `effects` (only `expired` and `ownership_removed` can be non-empty) |
| `tombstones` | each in-scope tombstone's decision: `accepted`, and `reason` (`STALE_PRIOR_REVISION`, `NO_COMMITTED_INVENTORY` or `SCOPE_MISMATCH`) when it was rejected |
| `diagnostics` | the run-level diagnostics |

Each `source_results` entry, sorted by `source_instance_id`:

| Field | Meaning |
| --- | --- |
| `source_instance_id`, `source_kind`, `locator` | the source's identity, its kind, and its root-relative locator (null if it has none) |
| `result` | `ACCEPTED`, `ACCEPTED_WITH_LIMITATIONS`, `REJECTED_INVALID`, `REJECTED_UNSUPPORTED` or `REJECTED_CONFLICT` |
| `adapter_identity`, `mapping_rule_version` | the adapter that claimed the source (for example `openapi-adapter@1`); null when no adapter claimed it |
| `dialect_version` | the document's declared `openapi`/`asyncapi`/`apiVersion` value; null when it has none or it is not a short version token |
| `semantic_input_digest` | the adapter's semantic input digest (I1 §5.3); null when the source never reached a normalized projection |
| `service_ids` | the Service ids the source emits, sorted. An Architecture Manifest emits CALLS only, so its list is empty. |
| `emitted` | what the adapter mapped, before reconciliation: counts of `services`, `operations`, `schemas`, `messages`, `queues`, `topics`, `subscriptions`, `relations`, `infrastructure_entities` and `infrastructure_claims` |
| `effects` | the source's canonical committed effects, described below. Null when the run did not commit. |
| `diagnostics` | the source's own diagnostics |

**Canonical effects.** `effects` is built from the source's claim reconciliation, by stable
identity. It is not a count of writes: `sources` still counts MERGE operations, which an unchanged
replay also executes. It has `graph_revision_advanced` and four effect sets:
- `added`: claims the source owns now but did not own before the run;
- `changed`: retained claims this source changed. For a node, its properties differ (ignoring
  the owner list, which is reported through the other sets). For a relation, it gained evidence
  this source emits;
- `expired`: claims the source stopped emitting that no other source will own after the run, so
  they expire;
- `ownership_removed`: claims the source stopped emitting that another source will still own after
  the run; they survive for those owners, without this source's DECLARED evidence.

Every set is attributed to its own source and does not depend on the order in which a run's
sources are reconciled. Whether a dropped claim expires is decided by its owners **after the whole
run**: its committed owners outside the run, plus the run's sources that still emit it. The run's
sources include those an authorized removal takes out in the same COMPLETE run, which are decided
before any source is reconciled. So a claim that two sources of one run both stop emitting, or that
one stops emitting while its co-owner is removed, expires for each. `graph_revision_advanced` is the
importer's revision-fence decision for the source. It can also reflect a co-owner's change within
the same run (for example, a shared Operation whose owner-scoped schema ids another co-owner last
wrote).

Each set lists public canonical facts as sorted `node_ids` (Services, Operations, Schemas,
Messages, Queues, Topics, Subscriptions) and `relation_keys` (`TYPE:source_id:target_id`).
Internal-only facts (Kubernetes infrastructure entities, contributions and claims, Pub/Sub
carriers, and Evidence) appear only as `internal_count`, because I2 §9 keeps them out of every
public payload. An unchanged replay has four empty sets and `graph_revision_advanced: false`.

Internal-only facts are reported only as counts, here and in `emitted`. I2 §9's exposure table
routes scope and ingestion diagnostics to the I1 ingestion report, and a count exposes no id,
property or evidence of the fact it counts.

So a FAILED run (for example a missing root: no source results and a `SOURCE_ROOT_UNAVAILABLE`
diagnostic), a PARTIAL run (a rejected source) and a `REJECTED_CONFLICT` can be told apart, and
each names the source it concerns.

**How I1 §10's report categories map onto v1:**
- discovered sources and inventories: `source_results`, `inventory_status`, `inventory_revision`;
- dialects and identities: `dialect_version`, `adapter_identity`, `mapping_rule_version`,
  `source_instance_id`, `service_ids`, and the run's scope identity;
- emitted counts: `emitted`;
- unsupported constructs, unresolved references and conflicts: diagnostic codes (for example
  `SCHEMA_COMPOSITION_UNINTERPRETED`, `K8S_RESOURCE_UNSUPPORTED`, `MANIFEST_CALL_TARGET_UNRESOLVED`,
  `SERVICE_IDENTITY_UNRESOLVED`, `SERVICE_IDENTITY_CONFLICT`) and the `REJECTED_*` results;
- planned mutations and expirations, and the canonical committed effects: `effects` and
  `removals`. A run that does not commit has no planned mutations, because I1 §6 commits nothing
  for a PARTIAL or FAILED run, so its `effects` are null and its `removals` empty;
- tombstones: `tombstones`;
- final commit status: `committed`.

I1 §10's dry run (a SHOULD) is not implemented.

**What a diagnostic exposes.** Only a stable `code`, the `source_instance_id`, and a sanitized
`source_pointer` are exposed. A `source_instance_id` that is not a well-formed AIP source id (a
rejected tombstone's operator-supplied target, for example) is reported as null. The pointer is
decided from its text and code alone, never from what exists on the host:
- the configured root, or a path under it, becomes relative to it (`.` for the root itself);
- a Windows absolute or UNC path, any backslash, a URL, or a `..` segment becomes null;
- a value starting with `/` is kept only for the codes whose pointer is always an RFC 6901 JSON
  Pointer (`DOCUMENT_POINTER_CODES` in `app/ingestion/import_report.py`; a test re-checks every
  site that emits them). For every other code, it could be an absolute host path, so it becomes
  null;
- anything else (a relative locator, an entity or resource id) is kept.

Diagnostic messages are never part of the report, because they can contain absolute paths and
snippets of rejected input (the I2 §5 sanitization rule). They are not logged either: the import
log records only per-source results and counts (v0.5.0 I5 finding F8, deferred). Every value
the report copies from operator input is sanitized rather than validated, so building the report
cannot fail after a run has committed.

`runs` carries no capture ids, timestamps or byte-level content digests, and every list in it is
sorted. It is the deterministic semantic projection of I1 §10. MCP has no import tool (I1 §12).

## Runtime observation adapter

Independently of the three above, `app/telemetry/adapter.py` maps OpenTelemetry spans into observed
facts. It's architecturally a different kind of adapter — it produces an `ObservationBatch`
(possibly-new entities + evidence-backed facts + unresolved observations), not an
`ArchitectureModel` — see [`opentelemetry.md`](opentelemetry.md) for its full contract and
[`adapter-development.md`](adapter-development.md) for how it fits the general extension point.
