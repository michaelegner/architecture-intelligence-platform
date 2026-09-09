# Architecture Review — after `v0.4.0`

**Reviewed:** `main` @ `78c62e5dae2a6e8e9a1a0d2aa8f1433e00824580` (2026-09-07, immediately after
`v0.4.0` shipped)
**Question:** does the structure that carried `v0.1`–`v0.4` support
[`ROADMAP.md`](../ROADMAP.md)'s `v0.5` (Broader Architecture Discovery), or does something need
restructuring first?
**Method:** read of `app/` (~8.5k lines, 15 packages) against the roadmap's next scope, plus one
measured scaling experiment ([below](#measured-read-cost)). Not a code-quality review — this looks
only at seams, contracts, and costs that are hard to change later.

## Verdict

**No large-scale refactoring is warranted.** The load-bearing decisions all held up: the Canonical
Model as the single mapping target, deterministic path-independent ids, the fact/evidence invariant,
per-service atomic reimport, the revision-fenced stable read, the frozen answer contract, and the
read-only LLM/MCP boundary. Nothing in `v0.5`'s scope requires undoing any of them.

Four structural items do need decisions, recorded as [ADR 0009](adr/0009-source-adapter-seam.md)
– [ADR 0013](adr/0013-no-topic-family-without-guards.md):

| # | Finding | Why now |
|---|---|---|
| [F1](#f1--the-adapter-extension-point-is-a-convention-not-a-seam) | The adapter extension point is a wiring convention, not a seam | `v0.5`'s first adapter doesn't fit the current source shape |
| [F2](#f2--the-declared-vs-observed-rule-is-stated-twice-and-never-cross-checked) | The declared-vs-observed rule is implemented twice, with nothing asserting the two agree | Each new adapter widens the blast radius of a silent divergence |
| [F3](#f3--read-cost-grows-with-the-whole-graph-and-evidence-never-stops-growing) | Every tool call reads and hashes the entire graph; observed evidence accumulates without bound | Measured: **29s** for one MCP call at ~98k nodes. Also `snapshot_id` semantics are public contract surface `v0.9` is meant to *freeze*, not redesign |
| [F4](#f4--a-standing-model-constraint-is-recorded-only-in-a-validation-dossier) | The queue-only messaging constraint lives in a validation dossier, not the ADR index | `v0.5` discovery work will meet it immediately |

F1 and F4 are prerequisites for the first `v0.5` adapter. F2 should land alongside it. F3 needs to be
*decided* now and implemented when a real landscape demands it.

## What is sound, and should not be touched

Recorded explicitly, so a later reader doesn't mistake the findings below for a verdict on the whole
system:

- **Canonical Model as the only mapping target.** Adapters never write to Neo4j; the model
  ([`app/canonical/model.py`](../app/canonical/model.py)) stayed stable across the OpenTelemetry
  addition and both real-world validations, which is exactly the decoupling
  [ADR 0002](adr/0002-canonical-model.md) predicted.
- **Deterministic, path-independent ids** ([`app/canonical/ids.py`](../app/canonical/ids.py)),
  including `observed_evidence_id`'s (fact, day, environment) bucketing that makes repeated
  observation idempotent.
- **The fact/evidence invariant and per-service atomic reimport**
  ([`app/graph/importer.py:168`](../app/graph/importer.py)) — one transaction, stale facts expired by
  reconciliation, never a partial import.
- **The revision-fenced stable read** ([`app/graph/revision_fence.py`](../app/graph/revision_fence.py),
  [`repository.py:140`](../app/architecture_intelligence/repository.py)) — a genuinely correct answer
  to non-repeatable reads, and the reason a claim and its evidence can be trusted to come from one
  committed state.
- **The frozen public contract with a drift test**
  ([`schema_export.py`](../app/architecture_intelligence/schema_export.py) plus
  `tests/unit/test_architecture_intelligence_schema_frozen.py`) — the contract cannot silently move.
- **The read-only boundary** for both the LLM ([ADR 0005](adr/0005-llm-is-not-source-of-truth.md)) and
  MCP: no tool holds a write path, and no tool needs an LLM key.
- **Spec-referenced comments.** Non-obvious rules cite the spec section that justifies them, which is
  what made this review possible at all without re-deriving intent.

## F1 — The adapter extension point is a convention, not a seam

[`docs/adapter-development.md`](adapter-development.md) describes `ArchitectureSourceAdapter`
(`supports()` / `load()`) as the *target* extension point and says plainly that there is no registry
today. That honesty is correct, and the gap is now load-bearing:

- [`app/ingestion/pipeline.py:58`](../app/ingestion/pipeline.py) — `parse_sources` hardcodes one
  block per source type; a fourth adapter means editing this function.
- [`app/ingestion/scanner.py:20`](../app/ingestion/scanner.py) — `FILE_KIND_BY_NAME` hardcodes
  filenames, `SpecificationSource` is file-bound (`path: Path`), and `service_id` *is* the directory
  name.
- [`app/graph/importer.py:168`](../app/graph/importer.py) — the atomic reimport unit is that same
  directory slug, tagged onto every node and relation as `.sources`.

`v0.5`'s first named adapter is Kubernetes discovery. A cluster has no per-service directory and no
spec file, and one source yields *many* services — so it fits neither `SpecificationSource` nor the
"reimport scope = directory" assumption. gRPC/protobuf and Kafka Connect sit closer to the file
model, but they too are files-per-*interface*, not files-per-service-directory.

The decision this needs is not "make the pipeline extensible in general" — it is specifically:
what is a *source instance*, and what is the reimport scope when one source declares many services?
See [ADR 0009](adr/0009-source-adapter-seam.md).

## F2 — The declared-vs-observed rule is stated twice, and never cross-checked

The same semantics exist in two implementations:

| | Cypher | Python |
|---|---|---|
| Evidence-window match | [`app/analysis/runtime.py:28`](../app/analysis/runtime.py) — `_OBSERVED_EXISTS`, `_NOT_OBSERVED_EXISTS`, `_DECLARED_EXISTS` | [`dependency_projection.py:52`](../app/architecture_intelligence/dependency_projection.py) — `_matches_declared`, `_matches_observed` |
| Coverage classification | `app/analysis/runtime.py:364` `_classify_coverage` | `dependency_projection.py:82` `_classify_coverage` |
| Consumers | O1–O5, REST (`app/api/runtime.py`), the UI | `get_service_dependencies` and `get_architecture_drift` |

Part of this is deliberate and defensible: `contracts.py`'s enums "mirror `app.analysis.runtime`'s
literal values by value, not by import, so this public contract doesn't couple to internal analysis
module churn", and the coverage rule itself is genuinely *shared* rather than reimplemented —
[`repository.py:296`](../app/architecture_intelligence/repository.py) calls `telemetry_coverage` and
says so ("*is* that rule, not a reimplementation of it").

`get_evidence` is not affected: it resolves provenance for already-identified references and
produces no qualified claims of its own, so the divergence risk covers `get_service_dependencies`
and `get_architecture_drift` only.

The gap is that **nothing executable asserts the two paths agree**. Both are covered by frozen
evaluation — [`evaluation/projector.py`](../evaluation/projector.py) exercises the Cypher path,
`evaluation/architecture_answers/` the Python path — but against independently authored scenario
sets, so a divergence between them would fail neither suite.

Two related asymmetries belong in the same decision, because they are visible to users comparing the
two surfaces:

- REST answers against an implicit, clock-relative window (`default_since`, and `$until IS NULL` is
  allowed); MCP requires an explicit `observation_context`. The same fact can legitimately read
  differently on the two surfaces, and nothing says so in either contract.
- The REST/UI layer reaches Neo4j directly (`app/api/services.py`, `queues.py`, `messages.py`,
  `evidence.py`, `ui.py` all embed Cypher), while the MCP layer goes through a repository. Only one
  of the two has a seam to change.

The fix is *not* to merge the layers — the contract/internals decoupling is worth keeping. It is one
differential test over shared fixtures plus a named owner for the window predicate. See
[ADR 0010](adr/0010-single-qualification-rule.md).

## F3 — Read cost grows with the whole graph, and evidence never stops growing

Three separate mechanisms, which compound:

1. **Snapshot fingerprinting reads everything.**
   [`repository.py:99`](../app/architecture_intelligence/repository.py)'s
   `canonical_snapshot_state` selects every `Service`, `Operation`, `Queue`, `Message`, `Schema` and
   `Evidence` node plus every relation, and hashes them canonically in Python. Every MCP call pays
   it — including `get_evidence` for a single reference — and the stable read may repeat it up to
   three times.
2. **Ingestion rescans the graph per export.**
   [`app/api/telemetry.py:46`](../app/api/telemetry.py) loads all services, operations and queues
   into memory on *every* OTLP request. (`telemetry_coverage` likewise runs `_ALL_SERVICES_QUERY`
   even when scoped to one service.)
3. **Observed evidence accumulates without bound.** One `Evidence` node per (fact, day,
   environment) ([`ids.py:39`](../app/canonical/ids.py)), and each relation's `evidence_ids` array is
   append-only ([`aggregator.py:48`](../app/telemetry/aggregator.py)). There is no retention,
   compaction, or archival anywhere, and no setting for one in
   [`app/settings.py`](../app/settings.py).

### Measured read cost

Synthetic `Service`/`Operation`/`Evidence` nodes seeded into the demo Neo4j, evidence shaped exactly
as `observed_evidence_id` produces it (per-fact, per-day buckets referenced from relation
`evidence_ids`). `canonical_snapshot_state` + `snapshot_fingerprint` timed in-process over Bolt, best
of three:

| Evidence nodes | Total nodes | Fingerprint |
|---:|---:|---:|
| 6 | 124 | 0.05 s |
| 4,604 | 4,722 | 0.75 s |
| 23,004 | 23,122 | 3.60 s |
| 97,548 | 98,566 | 16.06 s |

End-to-end `get_service_dependencies` over MCP against the same database, three samples each,
best of three (the fixture graph's first post-start call was 0.62 s, the rest 0.11 s):

| Graph | Latency |
|---|---:|
| bundled `examples/` fixture (30 nodes) | 0.11 s |
| 501 services, 97,548 evidence nodes (98,566 nodes) | **29.1 s** |

Cost is linear in total graph size, not in the size of the answer. 98k nodes is not a large
landscape: it is roughly 300 observed facts kept for a year, or 3,000 facts kept for a month, in a
single environment.

Caveats: a developer machine (WSL2, single-node Neo4j 5 container), so the absolute numbers are
indicative, not a production benchmark. The *shape* — linear in the whole graph, independent of the
question asked — is a property of the design, not of the hardware.

The mechanism for fixing the first item already exists: every writer bumps the revision fence
(`importer.py`, `aggregator.py`), so a fingerprint can be cached against a revision instead of
recomputed. That changes what `snapshot_id` guarantees, which is why it belongs in an ADR rather
than in a quiet optimization — see [ADR 0011](adr/0011-snapshot-identity-read-cost.md). Evidence
retention is a separate semantic decision, because deleting observed evidence deletes the basis of
past claims: [ADR 0012](adr/0012-observed-evidence-retention.md).

## F4 — A standing model constraint is recorded only in a validation dossier

The `v0.3` cross-system decisions
[`queue-topic-boundary.md`](real-world-validation/cross-system/decisions/queue-topic-boundary.md) and
[`messaging-operation-compatibility.md`](real-world-validation/cross-system/decisions/messaging-operation-compatibility.md)
establish that the Canonical Model has no topic/pub-sub family, that its `Queue` is
competing-consumer semantics only, and that widening `messaging.operation` recognition requires
**both** a topic-vs-queue guard and a service-identity guard first — `resolve_queue`
([`queue_resolver.py:24`](../app/telemetry/queue_resolver.py)) and `resolve_service` both mint an
entity unconditionally when no declared candidate matches.

That is a live constraint on `v0.5`'s discovery work, but it is reachable only by knowing which
validation dossier to open. Promote it into the ADR index — without re-deciding it — so the next
adapter proposal meets it in the obvious place: [ADR 0013](adr/0013-no-topic-family-without-guards.md).

## Sequencing

| When | Item |
|---|---|
| Before the first `v0.5` adapter | F1 (the seam), F4 (promote the constraint) |
| Alongside the first `v0.5` adapter | F2 (differential test) — a new adapter is exactly what makes divergence expensive |
| Decide now, implement when a real landscape needs it | F3 (snapshot cost, evidence retention) |

F3's *decision* cannot wait for `v0.9`: that release is meant to freeze the REST/MCP contract, the
Graph Schema and the Adapter SPI. `snapshot_id` semantics and evidence-reference bounds are part of
that surface, so arriving at `v0.9` with them undecided means redesigning a contract at the moment
it is supposed to stabilize.

## Reproducing the measurement

The measurement script was deliberately not committed — it seeds throwaway data into a disposable
demo graph. To repeat it:

1. `examples/runtime-demo/mcp-demo.sh` (or `docker compose -f docker-compose.demo.yml up -d
   architecture-intelligence`) and `POST /api/import`.
2. Seed synthetic `Service`/`Operation` pairs, then `Evidence` nodes whose ids follow
   `evidence:otel:<env>:<date>:<hash>`, appending each id to a relation's `evidence_ids`.
3. Time `canonical_snapshot_state()` + `snapshot_fingerprint()` from
   `app.architecture_intelligence.repository`, and one `get_service_dependencies` call over `/mcp`,
   at each graph size.
4. Delete the synthetic nodes, or `examples/runtime-demo/mcp-demo.sh --down`.

Any implementation of [ADR 0011](adr/0011-snapshot-identity-read-cost.md) should turn step 3 into a
committed, repeatable benchmark rather than an ad-hoc script.
