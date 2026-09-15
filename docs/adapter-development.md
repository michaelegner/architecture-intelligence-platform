# Adapter Development

AIP has two kinds of extension point — one for a new *declared* architecture source, one for a new
*runtime observation* source.

A declared-source adapter is registered, not branched on (ADR 0009). The real interface, from
`app/sources/registry.py`:

```python
class SourceAdapter(Protocol):
    adapter_identity: str
    mapping_rule_version: str
    dependency_phase: int

    def supports(self, loaded: LoadedSource) -> bool: ...

    def map(
        self,
        loaded: LoadedSource,
        *,
        service_identity: ServiceIdentityResolver,
        upstream_model: ArchitectureModel,
        mapping_context_digest: str,
    ) -> AdapterOutcome: ...


class ObservationSourceAdapter(Protocol):
    def ingest(self, source: Any) -> ObservationBatch: ...
```

Today's three declared adapters (`OpenApiSourceAdapter`, `AsyncApiSourceAdapter`,
`ManifestSourceAdapter`, in `app/ingestion/openapi_adapter.py`/`asyncapi_adapter.py`/
`manifest_adapter.py`) and the runtime adapter (`app/telemetry/adapter.py`) already implement this
shape — a plugin registry exists (`app.sources.registry.SourceAdapterRegistry`,
`app.ingestion.orchestrator.default_registry()`), so a new declared-source adapter is registered
alongside them, not hand-wired into a pipeline function. `dependency_phase` is the sole mechanism
for a later-phase adapter (e.g. the Architecture Manifest adapter, `dependency_phase=1`) to see an
earlier phase's merged result via `upstream_model` — the orchestrator never branches on source kind
to decide this.

## What a declared-source adapter must produce

An `AdapterOutcome` (`app/sources/registry.py`) wrapping an `ArchitectureModel`
(`app/canonical/model.py`) — never a partial or adapter-specific shape. `map()` must not raise for
a source/construct-level problem; instead it returns `AdapterOutcome(result=..., diagnostics=...)`
with an `IngestionResult` (ACCEPTED / ACCEPTED_WITH_LIMITATIONS / REJECTED_INVALID /
REJECTED_UNSUPPORTED / REJECTED_CONFLICT — I1 spec §10: "each source receives exactly one result").
In practice that means:

- Every entity id must be built with `app/canonical/ids.py`'s deterministic formatters (or, for
  Schema/Message/Queue, `app/sources/owner_ids.py`'s owner-scoped RFC 8785 identity — I1 spec §8/§9)
  — never an ad-hoc string and never anything derived from a local filesystem path (see
  [`canonical-model.md`](canonical-model.md) for why, including the specific bug class this
  prevents).
- Every construct's Service identity must be resolved through the injected `service_identity`
  closure (`app.sources.service_identity.resolve_service_identity`'s three evidence paths — an
  `x-aip-service-id` extension, a configured mapping, or an `ArchitectureIdentityBindings` manifest
  binding), never derived from a directory/file slug.
- Every `Relation` must carry `evidence_ids` pointing at a real `Provenance`/`Evidence` record the
  same adapter call also returns in `ArchitectureModel.provenance` — an adapter must never produce
  a fact with no supporting evidence (see [`graph-model.md`](graph-model.md)'s fact/evidence
  invariant).
- An adapter should only extract information it can reliably derive from its own source format — see
  how `manifest_adapter.py` deliberately extracts *only* REST-caller information OpenAPI can't
  express, rather than duplicating anything OpenAPI/AsyncAPI already cover
  ([`ingestion.md`](ingestion.md)).

## What a runtime-source adapter must produce

An `ObservationBatch` (`app/telemetry/model.py`): possibly-new entities (`ObservedOnlyEntity` stubs
for anything not already declared), evidence-backed `ObservedFactCandidate`s, and
`UnresolvedObservation`s for anything that couldn't be resolved with confidence. The existing
OpenTelemetry adapter's own rules are the model to follow for a new runtime source:

- Never guess an identity from an unreliable signal — report an `UnresolvedObservation` with a
  reason code instead (see [`opentelemetry.md`](opentelemetry.md)'s no-guessing rule and fixed
  reason-code set).
- Only read from an explicit, documented attribute/field allowlist — never persist a raw payload
  (see [`security-model.md`](security-model.md)).
- Emit deterministic evidence ids (`app/canonical/ids.py::observed_evidence_id`) so repeated
  observations of the same fact merge into one evidence bucket instead of accumulating duplicates.

## Wiring a new adapter in

A new declared-source adapter is a new module under `app/ingestion/` implementing `SourceAdapter`,
added to `app.ingestion.orchestrator.default_registry()`'s adapter list. `supports()` inspects the
loaded document's *content* to decide whether this adapter claims it (e.g. `"openapi" in
loaded.document`) — never the filename; discovery (`app/ingestion/filesystem_discoverer.py`) only
uses filename conventions as an enumeration convenience, and dispatch itself is
`SourceAdapterRegistry.adapter_for()`'s job. A runtime-source adapter is still wired directly into
its own request handler (e.g. `app/api/telemetry.py`'s OTLP endpoint) — the registry above only
covers declared sources.

## Worked example: a tiny declared-source adapter

The following is a deliberately small, non-production example. It shows the complete shape of a
declared-source adapter without adding another real source format to AIP.

Imagine a toy format called `toy-arch.json`:

```json
{
  "service": "checkout",
  "operations": [
    {"method": "GET", "path": "/orders"}
  ]
}
```

A toy adapter could resolve the declaring Service's identity, construct canonical IDs, attach
provenance, and return an `AdapterOutcome`:

```python
from app.canonical import ids
from app.canonical.model import ArchitectureModel, Operation, Relation, Service
from app.provenance.model import Provenance
from app.sources.model import IngestionResult, LoadedSource
from app.sources.registry import AdapterOutcome, ServiceIdentityResolver
from app.sources.service_identity import ServiceIdentityOutcome


class ToySourceAdapter:
    adapter_identity = "toy-adapter@1"
    mapping_rule_version = "v1"
    dependency_phase = 0

    def supports(self, loaded: LoadedSource) -> bool:
        return "service" in loaded.document and "operations" in loaded.document

    def map(
        self,
        loaded: LoadedSource,
        *,
        service_identity: ServiceIdentityResolver,
        upstream_model: ArchitectureModel,
        mapping_context_digest: str,
    ) -> AdapterOutcome:
        document = loaded.document
        source_instance_id = loaded.descriptor.source_instance_id

        resolution = service_identity.resolve(
            source_instance_id=source_instance_id,
            construct_pointer="",
            extension_value=document.get("x-aip-service-id"),
        )
        if resolution.outcome is not ServiceIdentityOutcome.RESOLVED:
            return AdapterOutcome(
                result=IngestionResult.REJECTED_UNSUPPORTED,
                model=ArchitectureModel(),
                diagnostics=resolution.diagnostics,
                semantic_input_digest=None,
            )
        service_id = resolution.service_id

        operations = [
            Operation(
                id=ids.operation_id(service_id, entry["method"], entry["path"]),
                service_id=service_id,
                method=entry["method"].upper(),
                path=entry["path"],
            )
            for entry in document.get("operations", [])
        ]

        evidence = Provenance(
            id=ids.evidence_id("TOY", source_instance_id, loaded.descriptor.content_sha256),
            source_type="TOY",
            source_file=loaded.descriptor.locator,
            source_revision=loaded.descriptor.content_sha256,
        )

        relations = [
            Relation(
                type="PROVIDES",
                source_id=service_id,
                target_id=operation.id,
                evidence_ids=[evidence.id],
            )
            for operation in operations
        ]

        model = ArchitectureModel(
            services=[Service(id=service_id, name=document["service"])],
            operations=operations,
            relations=relations,
            provenance=[evidence],
        )
        return AdapterOutcome(
            result=IngestionResult.ACCEPTED,
            model=model,
            diagnostics=(),
            semantic_input_digest=ids.evidence_id("TOY", source_instance_id),
        )
```

### Why this satisfies the adapter contract

The example follows the same contract as the existing adapters:

- `Service`/`Operation` use `ids.service_id()`/`ids.operation_id()`, keyed off the resolved
  canonical Service id — never a filename or directory slug.
- Service identity is resolved through the injected `service_identity` closure, exactly like
  `OpenApiSourceAdapter`/`AsyncApiSourceAdapter`/`ManifestSourceAdapter` do (I1 spec §4.1) — an
  unresolvable identity is a diagnostic and `REJECTED_UNSUPPORTED`, never an exception.
- The adapter returns an `AdapterOutcome`, never raises for a source-level problem.
- Source provenance is returned with the model.
- No local filesystem path is used to construct entity IDs.
- The example does not introduce a new production source format.

### Wiring the adapter into the registry

A real adapter is registered in `app.ingestion.orchestrator.default_registry()` alongside the
existing OpenAPI, AsyncAPI, and manifest adapters:

```python
from app.ingestion.toy_adapter import ToySourceAdapter

_DEFAULT_ADAPTERS = (
    OpenApiSourceAdapter(),
    AsyncApiSourceAdapter(),
    ManifestSourceAdapter(),
    ToySourceAdapter(),
)
```

`SourceAdapterRegistry.adapter_for()` then picks it by content (`supports()`), not by filename or
configuration — `app/ingestion/filesystem_discoverer.py`'s `CANDIDATE_FILENAMES` only needs a new
entry if the toy format uses a filename convention discovery wouldn't otherwise read.

This example is illustrative only. It does not require creating `toy_adapter.py` or registering the
toy format in production.
