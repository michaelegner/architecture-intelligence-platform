# 9. Source adapters are a registered seam, not a pipeline convention

Status: Accepted — implemented in v0.5.0 I1 (PR3a: `app/sources/registry.py`,
`app/ingestion/orchestrator.py`, `app/ingestion/filesystem_discoverer.py`); see
[`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f1--the-adapter-extension-point-is-a-convention-not-a-seam)

## Context

[ADR 0002](0002-canonical-model.md) established that adapters map into the Canonical Model instead of
writing to Neo4j. That decoupling held. What was never decided is how a *new* adapter is discovered,
selected, and scoped for reimport — today that is a convention:

- `app/ingestion/pipeline.py:58` (`parse_sources`) hardcodes one block per source type.
- `app/ingestion/scanner.py:20` hardcodes filenames in `FILE_KIND_BY_NAME`, models a source as a
  filesystem path (`SpecificationSource.path`), and takes `service_id` from the directory name.
- `app/graph/importer.py:168` uses that same directory slug as the atomic reimport scope, tagged onto
  every node and relation as `.sources`.

[`adapter-development.md`](../adapter-development.md) already documents the intended
`ArchitectureSourceAdapter` (`supports()`/`load()`) and states honestly that no registry exists.

`v0.5`'s first named source is Kubernetes discovery: no spec file, no per-service directory, and one
source instance yielding many services. It fits neither the source shape nor the reimport scope.
gRPC/protobuf and Kafka Connect are files, but files per *interface*, not per service directory. If
three more adapters are added under the current convention, the convention becomes the de-facto SPI
that `v0.9` is then asked to freeze.

## Decision

Make the extension point real before the next adapter is written:

1. **A source descriptor that is not file-bound.** A source instance is identified by its kind and a
   locator meaningful to its adapter (a directory, a cluster/context, an API endpoint), plus
   adapter-specific configuration — not by `Path` alone.
2. **A registry.** Adapters declare `supports(source)` and `load(source) -> ArchitectureModel`, and
   are registered rather than branched on. `pipeline.parse_sources` orchestrates
   discover → adapt → merge → canonical-validate without naming any source type.
3. **Reimport scope becomes the source instance, not the directory name.** The `.sources` tag
   identifies which *source instance* declared a fact, so one source may legitimately declare many
   services, and a service may be declared by more than one source. Atomicity stays per import unit;
   what changes is what the unit is.
4. **Filesystem scanning becomes one discoverer among several**, keeping today's
   `openapi.yaml`/`asyncapi.yaml`/`architecture.yaml` conventions intact for existing users.

This ADR fixes the seam, not any particular adapter. No new source format is approved here.

## Consequences

- `app/ingestion/pipeline.py` is deleted, replaced by `app/ingestion/orchestrator.py`, which wires
  discover → per-source load/validate/map → merge → canonical-validate → reconciliation-plan →
  atomic commit without branching on source kind. `app/ingestion/scanner.py` is replaced by
  `app/ingestion/filesystem_discoverer.py` for source-adapter purposes (it survives only because
  `evaluation/loader.py` still uses `scan_directory` for an unrelated directory check). The three
  existing adapters became `SourceAdapter`-implementing classes
  (`OpenApiSourceAdapter`/`AsyncApiSourceAdapter`/`ManifestSourceAdapter`), registered in
  `app.ingestion.orchestrator.default_registry()`; the per-source loop in `graph/importer.py` is
  `import_source()`/`import_all_sources()`.
- `POST /api/import/service/{service_id}` was re-keyed to the canonical Service ID: it reimports
  every configured source and confirms the requested service now exists, since under I1 a service
  may be declared by more than one source and a single-source-scoped reimport is no longer a
  meaningful unit.
- `.sources` became `.owner_source_ids`, holding `SourceInstanceId` values instead of directory
  slugs. A full reimport rewrites every value, so no data migration was required. The
  many-services-per-source and many-sources-per-service reconciliation invariants are proven by
  `tests/integration/test_importer.py`.
- [`adapter-development.md`](../adapter-development.md) documents the real `SourceAdapter` contract
  and registry, replacing its former "there's no plugin registry yet" section.
- The Adapter SPI that `v0.9` freezes is now a designed interface (`app/sources/registry.py`)
  rather than an inherited convention.
- Deliberately *not* decided here: whether adapters may be loaded from outside the repository
  (third-party plugins). Registration stays in-process and in-tree.
