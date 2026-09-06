# Source provenance (I3 spec section 38, section 40)

This scenario's `input/declarations/airflow-apiserver/openapi.yml` is a genuine but deliberately
trimmed subset of the already-frozen real Apache Airflow declaration file this repository already
carries, not a fresh real-system run (spec section 39: no ingestion/correlation/identity/
reconciliation semantics changed by I3). The full file is 16,402 lines across 88 real paths; only
two real, verbatim `get_assets`/`get_asset_aliases` operations are kept here (`info`/`openapi`
fields unchanged) - this scenario and its `airflow-frozen-drift` sibling assert only the service's
*outgoing* CALLS/SENDS surface (which the frozen capture already records as zero), never any of its
individual PROVIDES facts, so the full 88-path enumeration adds bulk without adding coverage. Every
kept line is real content copied from the pinned upstream file, nothing invented.

```text
system:            apache-airflow
upstream release:   3.3.1 (docs/real-world-validation/apache-airflow/upstream.md)
frozen capture:     docs/real-world-validation/cross-system/artifacts/airflow-actual.yaml
frozen capture blob: 8891289baa9facaf70a0cc0c6b9b2e0fdd9c838a (spec section 38's cited id; verified via `git hash-object`)
```

Trimmed from the full declaration file and its own git blob id (source:
`docs/real-world-validation/apache-airflow/runtime/declarations/airflow-apiserver/openapi.yml`,
blob `34068eab85b936036b3304fae1985e86230c7fb0`) - not verbatim, see above.

No derived telemetry is needed: the real frozen capture (all 88 paths) records 9 `PROVIDES` facts
and 0 `CALLS`/`SENDS`/`RECEIVES_FROM` for `service:airflow-apiserver` in the bounded profile - this
scenario's own trimmed graph has only the 2 `PROVIDES` facts above, but asserts nothing about that
count; it asserts only the (correctly empty) outgoing-dependency/drift surface, per I3 spec section
38.1 ("I3 SHALL NOT invent an Airflow outgoing dependency merely because the release wants a
positive tool scenario"). The frozen unsupported/unresolved/insufficient findings recorded in the
v0.3 dossier remain external-system findings, not converted into false direct-dependency claims -
this evaluator scenario does not re-assert them.

Sibling scenario sharing this same input: `airflow-frozen-drift` (section 38.1's empty-drift
expectation). No `airflow-frozen-evidence` scenario - nothing in the frozen outgoing-dependency
scope needs one.
