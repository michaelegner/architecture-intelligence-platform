# Source provenance (I3 spec section 37, section 40)

This scenario's `input/declarations/` are verbatim copies of the already-frozen real Quarkus Super
Heroes declaration files this repository already carries, not a fresh real-system run (spec
section 39: no ingestion/correlation/identity/reconciliation semantics changed by I3).

```text
system:            quarkus-super-heroes
upstream pin:       8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce (docs/real-world-validation/quarkus-super-heroes/upstream.md)
frozen capture:     docs/real-world-validation/cross-system/artifacts/quarkus-actual.yaml
frozen capture blob: 656446cd79c4cefec8f1ac0124fbb6b34e993704 (spec section 37's cited id; verified via `git hash-object`)
```

Copied declaration files and their own git blob ids (source:
`docs/real-world-validation/quarkus-super-heroes/runtime/declarations/`):

```text
rest-fights/architecture.yaml    b1cdec636488083f9200c8f723e678c97a9454a9
rest-fights/openapi.yml          847ed5d03ae403930e2a2b59e45aa41dc2c3d9ea
rest-heroes/openapi.yml          628919b5602b928ce23f718fce6df77cbb3fd946
rest-villains/openapi.yml        422ceaa0dd48643db26422ddc3984a6cffe9540b
rest-narration/openapi.yml       6c5f86e423398d035632554a216b8e7478ad11b6
```

`input/telemetry/spans.py` is a *derived* fixture (spec section 40): it reproduces exactly the
three `declared: true, observed: true` `CALLS` facts the frozen capture already records for
`service:rest-fights` -> `rest-heroes GET /api/heroes/random`, `rest-narration POST /api/narration`,
`rest-villains GET /api/villains/random` - nothing invented, no unresolved/unsupported construct
upgraded to resolved, using the same OTLP CLIENT/SERVER span mechanism every other scenario in this
suite already uses (`sync-confirmed/input/telemetry/spans.py`), not a new production adapter.

Sibling scenarios sharing this same derived input: `quarkus-frozen-drift` (section 37.1's empty-drift
expectation), `quarkus-frozen-evidence` (resolves these three claims' evidence).
