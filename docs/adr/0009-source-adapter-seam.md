# 9. Source adapters are a registered seam, not a pipeline convention

Status: Proposed — see [`architecture-review-0.4.0.md`](../architecture-review-0.4.0.md#f1--the-adapter-extension-point-is-a-convention-not-a-seam)

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

- `app/ingestion/scanner.py`, `pipeline.py`, and the per-service loop in `graph/importer.py`
  (`import_all_sources`, `import_service`) change shape; the three existing adapters keep their
  current function signatures behind the new registry.
- `POST /api/import/service/{service_id}` needs a decision of its own: its `service_id` is today a
  source-layer directory slug. Either it keeps meaning "the source that declares this service" or it
  is superseded by a source-scoped endpoint.
- Existing graphs carry `.sources` values that are directory slugs. A full reimport rewrites them, so
  no data migration is required, but the reconciliation invariant must be re-proven by test for the
  many-services-per-source case — a source that stops declaring one of its services must expire
  exactly that service's facts and nothing else.
- [`adapter-development.md`](../adapter-development.md)'s "there's no plugin registry yet" section is
  replaced by the real contract, and the worked example is rewritten against it.
- The Adapter SPI that `v0.9` freezes becomes a designed interface rather than an inherited
  convention.
- Deliberately *not* decided here: whether adapters may be loaded from outside the repository
  (third-party plugins). This ADR keeps registration in-process and in-tree.
