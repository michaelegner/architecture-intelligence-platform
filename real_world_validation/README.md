# AIP Real-World Validation Contract

Implements Iteration 1
([`i1-real-world-validation-contract.md`](../docs/specifications/0.3.0/i1-real-world-validation-contract.md),
`v0.3.0-alpha.1`) of the `v0.3.0` release
([`specification.md`](../docs/specifications/0.3.0/specification.md)).

> **I1 validates no external system yet.** It exists to freeze the methodology — ground-truth
> independence, the finding vocabulary, the `expected.yaml` shape, and deterministic comparison
> semantics — before Quarkus Super Heroes (I2) or Apache Airflow (I3) are evaluated. See
> [`docs/real-world-validation/README.md`](../docs/real-world-validation/README.md) for the
> validation-track documentation (ground-truth rule, dossier structure, how a real system's
> validation is expected to run).

## What this module does

`real_world_validation` compares a frozen, independently authored `expected.yaml` against an
already-produced capture of AIP's actual canonical facts, and classifies every difference into one
of six fixed categories:

```text
CORRECT
MISSING_SUPPORTED
INCORRECT_SUPPORTED
UNSUPPORTED
UNRESOLVED_IDENTITY
INSUFFICIENT_EVIDENCE
```

It never queries Neo4j and never generates ground truth from AIP output — both inputs are handed to
it as data (I1 §16/§19). Wiring this comparator up to a real system's live results is I2/I3's job.

## Running

```bash
uv run python -m real_world_validation compare --expected path/to/expected.yaml --actual path/to/actual.yaml
```

Exit codes: `0` no release-blocking (`CRITICAL`-severity) finding, `1` at least one, `2` invalid
`expected`/`actual` input (never `0` on failure).

## `expected.yaml` shape

```yaml
system: quarkus-super-heroes
upstream_revision: "<pinned-sha>"

scope:
  entities:
    - service:rest-fights
  relation_types:
    - CALLS

expected:
  relations:
    - id: qsh-rest-fights-calls-heroes
      type: CALLS
      source: service:rest-fights
      target: operation:service:rest-heroes:GET:/api/heroes
      status: CONFIRMED
      evidence:
        declared: true
        observed: true

unsupported:
  - id: qsh-grpc
    mechanism: grpc
    description: Present upstream but outside the current AIP supported scope.

unresolved_identity:
  - id: qsh-worker-identity-01
    description: Runtime process name cannot be mapped safely to a logical service.

insufficient_evidence:
  - id: qsh-unclear-flow
    description: Independent evidence does not establish this fact strongly enough.
```

`unsupported`, `unresolved_identity`, and `insufficient_evidence` entries are dossier-authored, not
comparator-derived — they describe what the independent ground truth itself could or couldn't
establish (I1 §12.4-12.6), and pass through into the finding list unchanged.

An actual-facts capture uses the same relation shape without `id` (actual graph facts have no
dossier-authored finding id):

```yaml
relations:
  - type: CALLS
    source: service:rest-fights
    target: operation:service:rest-heroes:GET:/api/heroes
    status: CONFIRMED
    evidence:
      declared: true
      observed: true
```

## v0.5.0 additions (I5 Slice 1)

For v0.5.0 I5 ([`i5-cross-system-qualification.md`](../docs/specifications/0.5.0/i5-cross-system-qualification.md)
§7) the vocabulary gains two optional sections, so every v0.3 `expected.yaml` stays valid unchanged.

**`expected.deployments`.** These are public `Service -[DEPLOYED_AS]-> Workload` outcomes. The
Workload is named the way an upstream manifest names it, never by a production id:

```yaml
expected:
  deployments:
    - id: qsh-rest-fights-deployment
      service: service:rest-fights          # or null
      workload: {namespace: heroes, kind: DEPLOYMENT, name: rest-fights}   # or null
      status: RESOLVED_CONFIGURED           # RESOLVED_EXPLICIT | RESOLVED_CONFIGURED | RESOLVED_OBSERVED | CONFLICT | AMBIGUOUS | UNRESOLVED
      supporting_methods: [RESOLVED_CONFIGURED]   # optional; canonical strength order
```

**`forbidden`.** These are negative expectations. A present forbidden fact is `INCORRECT_SUPPORTED`
(CRITICAL), reported under the forbidden entry's id. An absent one is `CORRECT`, so the negative
proof is visible in the report.
- A forbidden relation must be in scope.
- A forbidden deployment is violated by any `RESOLVED_*` outcome for its (Service, Workload) pair.

```yaml
forbidden:
  relations:
    - {id: qsh-no-fights-queue, type: SENDS, source: service:rest-fights, target: queue:fights}
  deployments:
    - id: qsh-no-name-only
      service: service:rest-fights
      workload: {namespace: heroes, kind: DEPLOYMENT, name: rest-fights}
```

**Capture.**
- `capture` covers every admitted endpoint-label pair of each relation type deterministically, for
  example `RECEIVES_FROM` to both Queue and Subscription.
- `PUBLISHES_TO` carries the same runtime status as `SENDS`.
- `--aip-config <config.yaml>` (which requires `--until`) also captures public `DEPLOYED_AS`
  outcomes for the scoped services. They are read through `ArchitectureIntelligenceService`, built
  exactly as the app builds it (`app.mcp.wiring.production_service_kwargs`), and written under
  `deployments:`. Without `--aip-config` the capture has no `deployments:` key, and `compare`
  rejects a dossier with deployment expectations against it (exit `2`) rather than reporting them
  missing.

## Classification rules

- Every `expected.relations` entry is matched by canonical identity (`type`, `source`, `target`)
  against the actual facts: no match → `MISSING_SUPPORTED`; a match whose asserted `status`/
  `evidence` fields differ → `INCORRECT_SUPPORTED`; otherwise → `CORRECT`. A field the dossier
  leaves unset is not part of the assertion (no fuzzy matching, I1 §13.3).
- An actual fact that falls inside the declared `scope` but matches no expected relation is
  reported as `INCORRECT_SUPPORTED` with no expected side — the frozen six-category vocabulary has
  no separate "unexpected" bucket, and I1 §12.3's own example list for `INCORRECT_SUPPORTED`
  includes "invented relation" (I1 §35 forbids silently dropping it).
- Severity defaults by classification (`INCORRECT_SUPPORTED`→`CRITICAL`, `MISSING_SUPPORTED`→
  `MAJOR`, `UNRESOLVED_IDENTITY`/`INSUFFICIENT_EVIDENCE`→`MINOR`, `CORRECT`/`UNSUPPORTED`→`INFO`) —
  I1 has no real findings yet to calibrate per-case severity from (I1 §14).
- Output is sorted by `(classification, severity, relation type, source, target, finding id)` (I1
  §21) using the rank tables in `model.py`, so repeated comparison of identical inputs produces
  byte-identical output.

## Module internals (for contributors)

```text
model.py        the six classifications, severity, RelationFact/ExpectedDocument/Finding records
loader.py       strict expected.yaml / actual-facts-capture parsing (I1 §17/§31/§43)
comparator.py   deterministic classification + sort (I1 §16/§19-21/§34-35)
reporter.py     plaintext report with I1 §22-23's count fields, no composite score
capture.py      live Neo4j relation capture, plus public DEPLOYED_AS capture (v0.5.0 I5)
__main__.py     `compare`/`capture` CLI subcommands and exit codes (I1 §32-33)
```
