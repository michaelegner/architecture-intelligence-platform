# 15. Bounded multi-file `$ref` resolution is hand-rolled, not delegated to `referencing`

Status: Accepted — implemented in v0.5.0 I1 (PR3b: `app/sources/reference_resolution.py`,
`app/ingestion/_shared.py`, `app/ingestion/openapi_adapter.py`, `app/ingestion/asyncapi_adapter.py`)

## Context

PR3a (see [ADR 0009](0009-source-adapter-seam.md)) migrated all three adapters onto the registry
seam and to owner-scoped RFC 8785 identity, but deliberately froze `$ref` handling at "today's
single-file, name-only lookup": OpenAPI's `resolve_schema_ref` was a flat
`ref.rsplit("/", 1)[-1]` name lookup into `components.schemas` with no real pointer resolution at
all, and AsyncAPI's `_resolve_ref` was a real but independent, same-document-only RFC 6901 pointer
walker. Neither followed a `$ref` across files, neither had any notion of a "reference closure," and
`normalized_definition_document_path` — the cross-file identity parameter already present in
`schema_owned_id`/`message_owned_id`/`inline_payload_schema_id` — was hardcoded to `""` at every
call site.

I1 spec §8.1 requires a specific, exact resolution order (parse URI → reject remote → percent-decode
once → reject absolute → resolve relative to the containing document's directory → normalize dot
segments → resolve symlinks to the real path → containment + regular-file check → resolve the RFC
6901 fragment), with an invented bounded closure (max depth 16, max 128 distinct files, max 8 MiB
total bytes) and a precise diagnostic taxonomy distinguishing malformed percent-encoding, an absolute
decoded path, a traversal/symlink escape, a missing/non-file target, a dangling pointer, a remote
reference, and a reference cycle — each a materially different rejection category
(`REJECTED_INVALID` vs. `REJECTED_UNSUPPORTED`), not a single generic "bad ref" error.

`referencing` 0.37.0 was already present as a transitive dependency (via `jsonschema`) and was
evaluated as an alternative to hand-rolling this.

## Decision

**Hand-roll the resolver in `app/sources/reference_resolution.py`; do not adopt `referencing`.**

`referencing`'s exception/resolution model is built for JSON-Schema `$id`/`$anchor` resolution, not
for this spec's exact diagnostic taxonomy or its invented depth/file-count/byte bounds — concepts
`referencing` has no notion of at all. Adopting it would only replace the smallest, already-solved
part of this problem (walking a resolved fragment) while leaving every security-relevant, novel part
(percent-decoding exactly once, absolute-path rejection, dot-segment normalization, symlink-safe
containment, cycle detection, the three closure limits) hand-rolled regardless — for a real added
dependency-surface risk, since a future `referencing` version bump could silently change edge-case
behavior underneath an identity-bearing hash.

One shared module, not two independent resolvers: §9 requires AsyncAPI to reuse "the complete OpenAPI
containment, URI/pointer normalization, cycle handling... contract from §8" by literal code sharing,
not just behavioral parity. `app/ingestion/_shared.py` builds on it with the one recursive
normalization/composition pass (`resolve_and_normalize_schema`) both adapters call for every
top-level schema/payload slot.

**Depth is a closure-wide `$ref` hop count from the root**, not per-branch composition nesting (a
same-file chain A → B → C is 2 hops even though it touches only 1 file). The spec does not define
depth's unit precisely; this is a deliberate, documented resolution of that ambiguity.

**Cycle detection is path-stack-based (ancestors on the current resolution chain), not a global
"visited" set.** A "visited" set would incorrectly reject a legitimate diamond or shared reference
(two branches both referencing the same file) as a cycle. The discoverer's best-effort closure walk
(`walk_transitive_closure`, used only to compute the `dependency_closure_digest` provenance value)
deliberately skips same-document (fragment-only) `$ref`s — it never recurses into that branch, so it
has no infinite-loop risk to guard against there. Same-document composition cycles (e.g. a schema's
`allOf` referencing itself via a fragment-only `$ref`) are instead caught by the adapter's own
recursive schema-normalization walk (`_normalize_schema_node`), which does expand fragment-only refs
and therefore needs its own guard.

**The discoverer's closure walk is best-effort and non-fatal; the adapter's own resolution during
`map()` is authoritative.** Both walk the identical graph via the identical shared primitives; having
two independent walks that could disagree about what failed would be worse than the discoverer
staying silent (`dependency_closure_digest = None`) on any failure and letting the adapter's `map()`
raise the real `REJECTED_*` outcome with the correct diagnostic.

**Version enforcement.** While implementing this, the bundled `docs/real-world-validation/
quarkus-super-heroes/` fixtures (pinned byte-identical to a real upstream commit) were found to
declare `openapi: 3.1.2`, outside the spec's original literal accepted set (`3.0.3`, `3.1.0`).
`3.1.2` is a published OAS patch release with a schema identical to `3.1.0`; the spec was amended
(Draft 0.3, see `docs/specifications/0.5.0/i1-source-ingestion-foundation.md` §12) to add it, using
the real Quarkus fixtures as the amendment's own conformance evidence rather than a silent code-level
tolerance widening.

## Consequences

- `normalized_definition_document_path` is now real everywhere `schema_owned_id`/
  `message_owned_id`/`inline_payload_schema_id` are called, instead of PR3a's unwired `""`
  placeholder. This is a disclosed identity-format correction, not just new-fixture wiring: it
  changed owner-scoped Schema/Message IDs for every existing single-file source, not only new
  cross-file ones. Inline (non-`$ref`) schemas also get a real `Schema` entity for the first time
  (previously silently dropped by OpenAPI's old flat-lookup resolver).
- A remote/scheme-qualified `$ref` is `REJECTED_UNSUPPORTED` + `REMOTE_REFERENCE_UNSUPPORTED` for
  the whole source, distinct from every other structural validation failure's `REJECTED_INVALID` -
  found and fixed via `tests/unit/test_pr3b_multifile_end_to_end.py`'s real discoverer+adapter
  pipeline test, after the generic `_dangling_ref_errors` structural check was initially still
  catching it as `REJECTED_INVALID`.
- A valid `allOf`/`oneOf`/`anyOf` composition is represented structurally in the canonical hash
  (branches sorted by canonical hash, since their order has no architectural meaning) but not
  interpreted as an effective object shape — the source is accepted with
  `ACCEPTED_WITH_LIMITATIONS` + `SCHEMA_COMPOSITION_UNINTERPRETED`.
- Deliberately *not* decided here: interpreting composition as an effective merged object shape,
  remote/network `$ref` resolution, and third-party/configured shared-identity mappings for a
  cross-source schema merge (PR3a already deferred the config surface; PR3b's owner-scoped default
  ID path is sufficient without it).
