# Hero Demo — Architecture Drift via MCP

This is the `v0.4.0` I3.4 "hero demo" (spec §41-43): a new, independent client — using nothing but
plain HTTP — asks AIP **which direct dependencies of `order-service` were observed at runtime but
never declared**, gets `LegacyPricingService` back qualified `OBSERVED_ONLY`, then drills into the
evidence that supports that answer, entirely through the same immutable snapshot. No LLM, no graph
query language, no AIP internal module.

Since `v0.5.0` I3 (ADR 0016), `ArchitectureIntelligenceService` is the single semantic owner behind
two public adapters — standard negotiated MCP and REST. This walkthrough discovers the tools over
MCP, then drives the deterministic drift → evidence path over REST (the published-image golden path
per ADR 0016); either adapter returns the same `ArchitectureAnswer` semantics.

Unlike [`README.md`](README.md)'s live traffic-generator walkthrough, this demo's evidence is a
**one-shot, timestamp-frozen** batch (`seed_frozen_evidence.py`), not a continuous live-clock loop
— spec §43 forbids a hero demo whose result depends on wall clock, so this one uses a fixed
observation window instead of `now - 24h`. It reuses the same `examples/runtime-demo` bundle
(topology, `docker-compose.demo.yml`) as the live demo, just without starting the `traffic-generator`
service.

Expect the whole thing, start to finish, to take about five minutes.

## 1. Prerequisites

Same as the live demo: copy `.env.example` to `.env` at the repo root (see root `README.md`) — its
`NEO4J_PASSWORD` default is fine here.

## 2. Bring up AIP (without the live traffic generator)

From the repo root:

```bash
docker compose -f docker-compose.demo.yml up --build architecture-intelligence otel-collector
```

Naming only these two services starts them plus their dependency, `neo4j` — the live
`traffic-generator` service is deliberately not started, so the only evidence in the graph is what
this demo seeds explicitly in step 4. Leave this running in this terminal; run everything else
below from a second one.

## 3. Import the declared architecture

```bash
curl -s -X POST http://localhost:8000/api/import | jq .
```

Loads `examples/` — `order-service` declares `CALLS product-service.getProduct`,
`SENDS payment-q`, and `SENDS unused-q` (see `examples/order-service/architecture.yaml`/
`asyncapi.yaml`). `LegacyPricingService` is declared nowhere.

## 4. Seed frozen evidence

```bash
docker compose -f docker-compose.demo.yml run --rm --build traffic-generator python seed_frozen_evidence.py
```

Sends one fixed-timestamp OTLP batch (anchored at `2026-08-26T12:00:00Z`, well inside the window
used below) through the real collector → AIP ingestion path: `OrderService -> ProductService`
(declared + observed) and `OrderService -> SENDS payment-q` (declared + observed) — both will
qualify `CONFIRMED` — plus the undeclared `OrderService -> LegacyPricingService` call. Since this
sends once and exits, re-running step 4 again is harmless and produces the same result.

## 5. Discover the tools over standard negotiated MCP

Since `v0.5.0` I3 (ADR 0016), `/mcp` serves standard negotiated MCP only — no `mcp-method`/`mcp-name`
headers or `_meta` markers are needed; a standalone `tools/list` is answered statelessly:

```bash
curl -s http://localhost:8000/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -H 'mcp-protocol-version: 2025-11-25' \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}' \
  | jq '.result.tools[].name'
```

Expect exactly three tools, in this order: `get_architecture_drift`, `get_evidence`,
`get_service_dependencies` (I3 spec §24's frozen lexicographic order).

## 6. Ask `GET /api/services/{id}/drift` (REST)

Per ADR 0016, the deterministic drift → evidence walkthrough below uses the REST adapter — the same
`ArchitectureIntelligenceService.get_architecture_drift` semantics, over plain HTTP:

```bash
curl -sf -G http://localhost:8000/api/services/service:order-service/drift \
  --data-urlencode 'environment=demo' \
  --data-urlencode 'from=2026-08-26T00:00:00.000000Z' \
  --data-urlencode 'to=2026-08-27T00:00:00.000000Z' \
  > /tmp/drift.json
jq '.claims[] | {object: .object.name, qualification}' /tmp/drift.json
```

Expect two claims: `LegacyPricingService` qualified `OBSERVED_ONLY` (the hero finding — a real
dependency `examples/` never declares) and `unused-q` qualified `NOT_OBSERVED_IN_WINDOW` (declared
in `asyncapi.yaml`, never sent to by the seed). `ProductService` and `payment-q` are `CONFIRMED`
(both declared and observed) and correctly do **not** appear — `get_architecture_drift` only
returns a discrepancy, never a match.

## 7. Inspect the snapshot and observation context

```bash
jq '{snapshot, observation_context}' /tmp/drift.json
```

Both are stable identifiers bound to this exact answer — the evidence lookup in the next step must
reuse the same `snapshot_id` to see the same underlying facts.

## 8. Collect the evidence references

```bash
jq -c '.evidence_refs' /tmp/drift.json
SNAPSHOT_ID=$(jq -r '.snapshot.snapshot_id' /tmp/drift.json)
```

`evidence_refs` is the exact sorted union of every returned claim's evidence (I3 spec §21) — opaque
IDs only, no raw span/trace payload.

## 9. Resolve the evidence on the same snapshot (REST)

```bash
EVIDENCE_REFS=$(jq -c '.evidence_refs' /tmp/drift.json)
BODY=$(jq -n --argjson refs "$EVIDENCE_REFS" --arg snapshot "$SNAPSHOT_ID" \
  '{evidence_refs: $refs, snapshot_id: $snapshot}')
curl -sf -X POST http://localhost:8000/api/evidence/resolve \
  -H 'content-type: application/json' \
  -d "$BODY" | jq '.data.records'
```

Returns sanitized provenance for each reference — `evidence_type` (`DECLARED`/`OBSERVED`),
`source_type` (`OPENAPI`/`ASYNCAPI`/`MANIFEST`/`OPENTELEMETRY`), `source_locator`/`source_revision`
or an observation window (`bucket_start`/`bucket_end`/`first_seen`/`last_seen`), and nothing that
spec §47 forbids (no raw span/trace payload, no headers, no secrets).

## 10. Clean up

```bash
docker compose -f docker-compose.demo.yml down -v
```

## Why this is deterministic

Every span `seed_frozen_evidence.py` sends is timestamped at the fixed
`SEED_TIMESTAMP = 2026-08-26T12:00:00Z` constant, not `datetime.now()` — see its module docstring.
`window_start`/`window_end` above are the matching fixed constants, not computed relative to
whenever you run this. Re-running steps 3-9 from a clean state (`docker compose down -v` then
repeat from step 2) reproduces the same qualifications every time, regardless of wall-clock time,
host timezone, or how many times you've run it before.
