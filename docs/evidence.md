# Evidence & Provenance

Every architecture fact — every `Relation` in the Canonical Model, every relation in the graph —
must carry provenance. `Provenance` (`app/provenance/model.py`) is the base shape:

| Field | Meaning |
|---|---|
| `id` | Deterministic id (see [`canonical-model.md`](canonical-model.md)) |
| `source_type` | `OPENAPI` \| `ASYNCAPI` \| `MANIFEST` \| `OPENTELEMETRY` \| `KUBERNETES` (internal-only — see [Internal-only evidence](#internal-only-evidence)) |
| `source_file` | Where this came from (a spec file path, or `opentelemetry` for observed evidence) |
| `source_revision` | Optional — a git revision or similar, if known |
| `evidence_type` | `DECLARED` \| `OBSERVED` (`INFERRED` is reserved for a future documents/LLM/rules-derived phase and is not populated by anything today) |

`ObservedEvidence` extends `Provenance` with the fields a runtime observation needs: `environment`,
`bucket_start`/`bucket_end` (a one-day bucket), `first_seen`/`last_seen`, `observation_count`,
`sample_trace_ids` (capped at 5), `service_version`, and `correlation_mode` (below).

## The `Evidence` node

`Evidence` is its own Neo4j node label, queryable via `GET /api/evidence`, `GET /api/evidence/{id}`,
`GET /api/services/{id}/evidence`, `GET /api/queues/{id}/evidence`. There is no direct graph edge
from a relation to the `Evidence` node(s) that back it — every relation instead carries an
`evidence_ids: list[str]` property naming them; look them up with
`MATCH (e:Evidence) WHERE e.id IN r.evidence_ids`. This is what makes provenance fully traceable
end-to-end, not just produced in-memory during ingestion and discarded.

## Internal-only evidence

A Kubernetes source (`app/ingestion/kubernetes_adapter.py`, v0.5.0 I2) writes ordinary
`Evidence`/`Provenance` records — `source_type: KUBERNETES` — for the facts it contributes, using
the exact same `Evidence` node label and shape described above. They are real, committed graph
nodes, not a separate mechanism.

They are also, deliberately, the one category of `Evidence` this doc's own public query surface
never returns: I2 Draft 0.2's §9 amendment keeps evidence supporting only internal-only Kubernetes
infrastructure facts (`InfrastructureEntity`/`Contribution`/`Claim` — see
[`canonical-model.md`](canonical-model.md#infrastructure-entities-and-claims-appcanonicalinfrastructurepy--internal-only))
off `GET /api/evidence`, `GET /api/evidence/{id}`, and the canonical snapshot projection every MCP
answer's `snapshot_id` is computed from. Exposing that evidence while hiding everything it supports
would leak the existence, count, and source attribution of those internal-only facts indirectly —
and would make merely *configuring* a Kubernetes source change the public snapshot fingerprint for
every existing consumer, a public-surface change I2 does not otherwise make. Exposure of Kubernetes
evidence requires its own explicit, versioned exposure amendment before implementation, exactly as
the governing spec already requires for the infrastructure claims themselves.

## `correlation_mode`

For `OBSERVED` evidence produced by the OpenTelemetry pipeline, `correlation_mode` records *how*
the observation was correlated (`app/telemetry/model.py::CorrelationMode`):

- `CLIENT_SERVER` — the strongest signal: a matched CLIENT+SERVER span pair, whether they arrived
  in the same OTLP batch or were matched across two separate batches via the correlation buffer.
- `CLIENT_ONLY` — a CLIENT span whose target service identity is stable (`peer.service`) but whose
  SERVER counterpart never arrived (partial instrumentation).
- `SERVER_ONLY` — a SERVER span whose caller was never identifiable — this never produces a `CALLS`
  fact on its own (see [`opentelemetry.md`](opentelemetry.md)); it's recorded as an unresolved
  observation, not guessed.
- `MESSAGING_SEND` / `MESSAGING_RECEIVE` / `MESSAGING_PROCESS` — messaging spans, which never need
  correlation (each is independently derivable), but still record which of the three operation
  kinds produced the evidence.

When two observation seeds land in the same evidence bucket, the merge keeps the *stronger* of the
two modes (`app/telemetry/aggregator.py::merge_evidence`) — `CLIENT_SERVER` outranks
`CLIENT_ONLY`/`SERVER_ONLY`, which outrank the `MESSAGING_*` modes, which outrank no mode at all.

## Declared vs. observed, and why both matter

`DECLARED` evidence comes from a spec (OpenAPI, AsyncAPI) or the architecture manifest — it says
"this is the intended architecture." `OBSERVED` evidence comes from real OpenTelemetry traffic — it
says "this actually happened." A fact can carry either, both, or (for a moment, during a stale
reimport) transition between them; see [`graph-model.md`](graph-model.md) for the exact
reconciliation invariants this produces and why a fact is never deleted while any evidence, of
either kind, still supports it.
