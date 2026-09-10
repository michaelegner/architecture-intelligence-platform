# Snapshot/read-cost benchmark

v0.4.1 I3.1's committed, reproducible answer to one bounded question (spec
[`docs/specifications/0.4.1/i3-hardening-qualification-and-release.md`](../docs/specifications/0.4.1/i3-hardening-qualification-and-release.md)
§7):

> With the requested answer held constant, how does the current cost of snapshot-state reading,
> snapshot fingerprinting, and one representative dependency answer change as unrelated total
> graph size and observed Evidence volume increase?

This is measurement evidence for [ADR 0011](../docs/adr/0011-snapshot-identity-read-cost.md), not
an SLO, not a cache, and not a retention policy. Running this benchmark changes nothing in the
production graph or code path — it only reads.

## Running it

```bash
uv run python -m benchmarks --profile smoke
uv run python -m benchmarks --profile review-comparable \
    --candidate-sha <40-hex-git-sha> \
    --out docs/release-validation/v0.4.1-read-cost-benchmark.json
```

Requires Docker (a disposable Neo4j 5 container via Testcontainers, the same foundation
`tests/integration/` and `evaluation/` already use) and must be run from the repository root.

- `smoke` — small, fast, deterministic; proves wiring, cleanup, result validation and determinism.
  It does not prove scaling shape. Safe to run repeatedly in CI/dev.
- `review-comparable` — the expensive profile whose scale points land near the same orders of
  magnitude as the post-`v0.4.0` architecture review (`docs/architecture-review-0.4.0.md`). It is
  never run in default CI; it is invoked explicitly during release-candidate qualification (spec
  §22/§24), bound to the exact frozen candidate SHA.

## What it does and does not touch

- Boots its **own** standalone, disposable Testcontainers Neo4j instance and its own in-process
  copy of the real production app (`app.main.create_app()`), served over real network HTTP — never
  the developer's normal AIP database, and never a shared/external database by default.
- Seeds a fixed **target subgraph** (`order-service` calling `product-service`'s
  `GET /products/{id}`, from the real `examples/` fixture landscape) through the real production
  import pipeline (`app.graph.importer.import_all_sources`) plus one real observed fact through the
  real telemetry aggregation path (`app.telemetry.aggregator.persist_observation_batch`). This
  target's dependency answer has constant semantic cardinality at every scale point.
- Grows total graph/evidence size with **unrelated** synthetic Service/Operation/CALLS facts,
  seeded through the same real `persist_observation_batch` write path — never through hand-rolled
  Cypher, and never touching the target answer.
- Times `canonical_snapshot_state()`/`snapshot_fingerprint()` (`app.architecture_intelligence.
  repository`) directly, and times one end-to-end `get_service_dependencies` call through the real
  MCP boundary using `tests/integration/independent_mcp_client.py` — the same independent-client
  harness `tests/integration/test_mcp_independent_client_golden_path.py` already proves correct.
- Validates its own JSON result against the committed closed schema
  (`snapshot_read_cost.schema.json`) before writing it, and refuses (non-zero exit) if any scale
  point's structural or semantic validation fails.
- Ships **no** cache, no snapshot-identity change, no retention/compaction, and no new adapter or
  MCP endpoint. A slow result is evidence for later work (ADR 0011), not permission to add an
  optimization inside this increment.

## Result artifact

One UTF-8 JSON document per run, matching `snapshot_read_cost.schema.json` — see that schema for
the exact field contract (candidate identity, dirty-worktree flag, per-scale-point structural
counts, raw/min/median timing samples, structural/semantic validation, revision-fence and
snapshot-identity consistency). The release-bound `review-comparable` result additionally lands at
`docs/release-validation/v0.4.1-read-cost-benchmark.json` with a human-readable companion,
`v0.4.1-read-cost-benchmark.md`, per spec §23.
