# v0.7.0 I4.3 — Product-value pilot runbook

**Status:** I4.3b kit. Governing: [I4 specification](i4-deterministic-real-system-and-product-value-qualification.md) §9; [decision record](i4-decision-record.md) D7 (method, frozen). This runbook makes the owner's **one recorded coding-agent session** reproducible and measurable. It adds no Architecture Intelligence semantics and no code. The agent is a consumer of AIP, never semantic authority; the disposition (`CONTINUE | NARROW | DEFER | STOP`) is the owner's and rests on this single session, which the record states.

The pilot runs against the **pinned APISIX replay world** of I4.2 (`i4-replay/`, revisions R1 then R2), through the **public surface only** (negotiated MCP at `/mcp`, or the REST routes). The frozen package is never written to: the kit works on a copy. In this world the gateway Routes match no OpenAPI Operation and no mapping is supplied, so the session first meets the unresolved answer (I4.2: Route→Operation 5/5 and Route→Service 5/5 unresolved), then **the operator authors the mapping during the session**; that effort is a recorded measure.

## 1. Set up (clock from the first command)

Start from a clean checkout of `main` at or after the I4.2 candidate (`c662f3c`; every later commit is documentation or this kit, no `app/` change). Record `git rev-parse HEAD`. Docker and `uv` are required.

```sh
uv sync
export PILOT=$(mktemp -d)                         # the working copy; i4-replay/ is never written to
R=docs/specifications/0.7.0/i4-replay
mkdir -p "$PILOT/gateway" "$PILOT/metrics"
cp "$R"/r1/gateway/*  "$PILOT/gateway/"            # revision R1: configuration capture
cp "$R"/r1/metrics/*  "$PILOT/metrics/"            # revision R1: measurement window W1
sed "s|@REPO@|$PWD|; s|@PILOT@|$PILOT|" docs/specifications/0.7.0/i4-pilot/config.template.yaml > "$PILOT/config.yaml"

docker run -d --name aip-pilot-neo4j -p 17687:7687 -e NEO4J_AUTH=neo4j/pilot-local-only \
  neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93
NEO4J_PASSWORD=pilot-local-only CONFIG_PATH="$PILOT/config.yaml" \
  uv run uvicorn app.main:app --port 8000          # keep this running; use port 8000 (see below)
curl -s -X POST localhost:8000/api/import          # import R1 through the production source path
```

Use port **8000**: the MCP endpoint's default host allow-list accepts `localhost:8000`, and any other port answers `Invalid Host header` unless `mcp.allowed-hosts` is configured. Connect the agent to `http://localhost:8000/mcp` (negotiated MCP; client configuration examples are in `examples/mcp-clients/`). `tools/list` must show five tools including `get_api_consumer_usage`. An installed AIP plugin that lists only four tools is an older build; point the client at this server.

The **context card** the operator gives the agent is part of the measure. The tool needs exact identifiers and a measurement window, and no public tool discovers the gateway instance, environment or window: `gateway_instance_id = gw-i4-replay`, `environment = replay`, and `window_start` / `window_end` read from `"$PILOT"/metrics/apisix-measurement-manifest.json`. Record exactly what you gave the agent.

## 2. The task

Give the agent this task, unchanged:

> An agent is about to change an API Operation and asks which configured consumers are related to that exposure, which have independently observed usage in the selected completed window, and what remains unresolved.

The Operation is `POST /orders` of the order service (id `operation:service:order-service:POST:/orders`). Run the agent with the AIP tools only: no Neo4j access, no source files of the replay, no Cypher. Enforce it by starting the client with its built-in tools disabled (`claude --tools ""`), and check with `/mcp` that the five AIP tools are still available. Paste only the operator's own shell commands into your own terminal, never into the agent. After the Phase 3 refresh, ask with the **R2** window from the new manifest.

## 3. Phases

**Phase 1 — no mapping (first synchronization cycle: import R1).** Ask the question. Expected from the frozen behavior, not scripted: the answer cannot select a Route for the Operation (`NO_ROUTE_SELECTED`, with the Route→Operation summary showing the Routes unresolved). Record what the agent concludes and does next, and whether it separates "no evidence" from "no consumers".

**Phase 2 — the operator mapping.** The operator authors `"$PILOT"/metrics/apisix-mapping.json` (`aip-apisix-mapping/1`, format in [`i2-measurement-contract.md`](i2-measurement-contract.md) §5: `route_operation` and `target_service` entries, the APISIX Route id and the canonical Operation and Service ids), then re-imports (`curl -s -X POST localhost:8000/api/import`) and re-asks. The task is an Operation question, so author **only the minimal `route_operation` entry** that associates the Route exposing the Operation with the Operation; leave `target_service` empty (`[]`). The Route→Operation and Route→Service chains are independent, so the Operation answer does not need a Service association. If the agent independently needs an application-Service association for a follow-up question, record that as additional work, not as baseline setup. Time the authoring, note every lookup needed and every input the operator had to supply. The kit does not provide the file; its content is the pilot's identity-mapping effort.

**Phase 3 — second synchronization cycle (import R2).** Keep the mapping file and replace the capture and measurement with the controlled revision (a consumer removed from an allow-list, a Route removed, a Route added, a new window), then re-import and re-ask with the new window:

```sh
cp "$R"/r2/gateway/*  "$PILOT/gateway/"
cp "$R"/r2/metrics/*  "$PILOT/metrics/"
curl -s -X POST localhost:8000/api/import
```

Read the new window from the manifest again. Also resubmit, after the import, a continuation cursor and an evidence request minted in Phase 2 (use `limit: 1` in Phase 2 to obtain the cursor and an `evidence_refs` entry from a Phase 2 row). Resubmit them **unchanged**: the evidence request with the **same Phase 2 context** (target, gateway instance, environment, window) and the **same Phase 2 `snapshot_id`** together with the old refs, and the cursor with its original snapshot id. Changing the context or the snapshot would turn the check into a cross-context test instead of the intended stale-snapshot test. Both must be refused as `SNAPSHOT_NOT_AVAILABLE`. Record the time and effort of this refresh, the difference in the answer, and whether the agent noticed the changed state.

Stop the server and `docker rm -f aip-pilot-neo4j` afterwards. Nothing in the pilot is committed.

## 4. What to record

Fill [`i4-pilot-record-template.md`](i4-pilot-record-template.md): the agent or client and the model and version; per phase the setup, synchronization, consumer-attribution and identity-mapping effort in minutes, the manual inputs, the unresolved and ambiguous rate, the useful answer coverage, the time and cost to keep the evidence current over the two cycles, whether the answer materially improved the agent's decision, and whether the agent kept architecture evidence apart from unsupported dependency, ownership or authorization inference. Semantic correctness (what the evidence establishes) and product usefulness (whether obtaining and maintaining it is worthwhile) are judged separately. A semantically correct result may still be `NARROW`, `DEFER` or `STOP`.

If the agent cannot separate evidence from unsupported inference, stop and report; that is an I4 stop condition (specification §13), not a result to soften.

## 5. Dry run of this kit (not pilot evidence)

On 2026-10-15 the author ran the three phases end to end against a real server on the then-current `main`, through REST (and `/mcp` for the tool list and one call), to prove the kit works. A first run mapped both chains; after review the Phase 2 and Phase 3 steps were re-run with only the `route_operation` entry, and the table reports what that re-run showed (the five rows were read in the first run, where the Operation chain was the same). It involved no agent and measured no effort; none of it is a pilot result. Observed:

| Step | Observed |
|---|---|
| `tools/list` on `:8000/mcp` | five tools, `get_api_consumer_usage` first |
| Phase 1 (R1, no mapping) | `NOT_ANSWERED`, `NO_ROUTE_SELECTED`; Route→Operation summary: 5 unresolved |
| Phase 2 (`route_operation` entry for `orders-route` only, `target_service` empty, re-import) | answered (`limit: 1` gives `PARTIAL` with a cursor; unpaged `ANSWERED`); 5 rows: alice `OBSERVED_USAGE` (3 upstream requests), carol `NO_MATCHING_CONFIGURED_ACCESS_FACT` with `USAGE_UNESTABLISHED` (2 rejected attempts), bob, dave and erin configured with `MEASURED_ZERO`; Route→Operation summary: 1 resolved to target, 4 unresolved. The evidence refs of a row resolved (`RESOLVED`) at the Phase 2 snapshot |
| Phase 3 (R2 over R1, same mapping file) | `ANSWERED` in the new window; rows alice and erin only, both `MEASURED_ZERO`; the Phase 2 cursor, and the Phase 2 evidence request resubmitted with the same context and snapshot id, both answered `SNAPSHOT_NOT_AVAILABLE` |
| `get_api_consumer_usage` through `/mcp` | `isError` false, `ANSWERED` |

Two frictions the pilot should expect and record: no public tool discovers the gateway instance, environment, window or the canonical Route and Operation ids (the operator must supply them), and the mapping needs the exact canonical Operation id and the raw APISIX Route id.
