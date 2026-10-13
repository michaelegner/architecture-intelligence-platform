# Pitstop demo

A demo over
[Pitstop](https://github.com/EdwinVW/pitstop), a .NET garage-management sample on RabbitMQ
([v0.6.2 spec](../../docs/specifications/0.6.2/specification.md) §4). It answers *"I am about to change
`MaintenanceJobFinished`: which services receive from the messaging destination this service publishes
to, how far can the evidence resolve that topology, and what must I still inspect?"* with real AIP
answers over MCP and REST. It can be tried as a reproducible local replay or against the hosted live demo.

## Try it

- **[Try locally](TRY_IT_LOCALLY.md)** — reproducible replay, no credentials required.
- **[Try hosted](TRY_IT_HOSTED.md)** — live demo through the public read-only MCP endpoint `https://217-154-245-195.sslip.io/mcp`; no credentials required.

## Ask the questions

[`walkthrough.md`](walkthrough.md): the question ladder Q1–Q5, each with the MCP and REST call and the real
answer, keeping AIP results apart from what AIP cannot know; Q6 links to
[`conversation-claude-code.md`](conversation-claude-code.md), a recorded Claude Code conversation over this demo
(an example, not qualification evidence). AIP has no receiver-side question: you ask
the **publisher** and read its receivers from the answer.

## What the `WorkshopManagementAPI` answer shows

- `PUBLISHES_TO` the exchange `Pitstop` (a Topic) through the Broker `rabbitmq:pitstop-rabbitmq`
  (`USES_BROKER`).
- Five receivers, each a `RESOLVED_SERVICE` claim through its own named queue: `InvoiceService`
  (`Invoicing`), `NotificationService` (`Notifications`), `WorkshopManagementEventHandler`
  (`WorkshopManagement`), `ReportingService` (`Reporting`) and `AuditlogService` (`Auditlog`). Receipt is
  per messaging destination (the exchange), **never per event type**: the answer says nothing about which
  receiver handles which event.
- Every claim carries the **publisher's** qualification (`CONFIRMED`: one `send` span lies in the window).
  There is no per-queue qualification. Four receiver routes also carry observed evidence; `AuditlogService`
  has none in this fixture, which does not mean the queue is unused.
- `ReportingService` is a fork addition that no Pitstop README, ADR or arc42 table lists. It is present in
  AIP's operator-declared evidence (its own overlay), not discovered at runtime.
- **AIP holds no payload or field-level knowledge.** Which receiver reads `StartTime` or `EndTime` is not
  in any answer: it is what you must still inspect in each receiver.

## Live mode

`run.sh --live` runs the real thing instead of a replay: the instrumented Pitstop fork (nine .NET services, RabbitMQ,
SQL Server), an OpenTelemetry Collector, a traffic generator and AIP, all in one Compose project
(`aip-pitstop-live`). Every service exports `send`/`process` spans for its RabbitMQ messages
(`Pitstop.Infrastructure.Messaging` `5.5.0-aip.3`, fork commit `15b21c6`); the Collector forwards them to AIP's
`/v1/traces`.

```bash
PITSTOP_FORK_DIR=/path/to/pitstop-fork examples/pitstop-demo/run.sh --live
```

- **Needs the private fork** (`PITSTOP_FORK_DIR`, the instrumented commit). It is not part of this repository, so
  CI does not run this mode. About 4 GB of RAM are needed (SQL Server alone takes 2 GB); the first run builds the
  fork's images (several minutes).
- **Order matters**: AIP, Neo4j and the Collector start first, the nine overlays are imported (all or nothing), and
  only then do Pitstop and the generator start. Spans that arrived before the import would create observed-only
  Services that never merge with the declared ones.
- **Traffic**: one cycle every `TRAFFIC_INTERVAL_SECONDS` (default 600, i.e. 144 a day): register a customer and a
  vehicle, plan a workshop job and finish it, through Pitstop's own APIs. Each cycle uses fresh identifiers and a
  fresh synthetic planning date. A failed call is logged and counted, never retried. `TimeService` is not driven by
  a cycle (it publishes at most once per 24 hours of uptime), so its first span appears about a day after start.
- **Answers refer to a completed UTC day.** Only whole-UTC-day windows are stable under later evidence, so
  `run.sh --live --check` checks yesterday (or `--date YYYY-MM-DD`) and exits 3 with "No completed window yet"
  until a day wholly in the past holds traffic. The first such day is the start date, available after UTC midnight.
- **What you see differs from the replay in one way**: every consumer really receives, so all five routes carry
  observed evidence (two resolution refs each, `AuditlogService` included). The replay's "unobserved is not unused"
  boundary is a property of its authored fixture only.
- `run.sh --live --down` removes the containers, volumes and `.aip-pitstop-live/`.

## Public read-only profile (hosted instance)

The hosted demo is reachable anonymously (no token) at its public MCP URL. AIP itself still provides no
public-internet authentication or tenancy: the deployment edge owns the safety, and
[`hosted/verify_public_edge.py`](hosted/verify_public_edge.py) is the external evidence that it does. The edge
must:

- publish **only `POST /mcp`** over HTTPS; `/api/*` (including `/api/import` and `/api/query`), `/v1/traces`, Neo4j
  and every operational endpoint stay unrouted, and Pitstop, the Collector and administration stay on the internal
  network;
- ignore, and not forward, the `Authorization` header (the plugin sends an empty `Bearer` header when `aip_token`
  is empty);
- bound abuse: a per-client rate limit with a bounded burst, a request-body cap, an upstream timeout, bounded
  concurrent requests and a global ceiling, with limits set from a real Claude Code Pitstop run so that
  initialization, tool discovery and evidence drill-down are not blocked;
- leave AIP's `mcp.allowed-hosts` / `mcp.allowed-origins` set to the public hostname (see `config.yaml`).

Because the edge cannot tell a safe `tools/call` from a future mutating tool, the checker fails unless `tools/list`
returns exactly the frozen public tool allowlist, and a unit test ties that list to the registered tools.

With Caddy, that is a `handle` that matches only `/mcp` (everything else answers 404), `header_up -Authorization`,
`request_body { max_size }`, `reverse_proxy` transport timeouts and `max_conns_per_host`; rate limiting needs a
Caddy build with a rate-limit module such as `github.com/mholt/caddy-ratelimit`.

```bash
python examples/pitstop-demo/hosted/verify_public_edge.py --url https://<host>/mcp \
  --date <completed UTC day> --expect-429-within <deployed per-client limit + 1>
```

Run it from outside the hosting network. `--expect-429-within` is optional: without it the rate-limit check is
reported `SKIPPED`. The exit code is non-zero if any check fails. Run it, and compare the Pitstop answer for the
latest completed UTC day with the recorded one, before publishing the anonymous URL.

## Troubleshooting

- **"port 8000 is in use"**: stop whatever uses it (often another demo: `run.sh --down` of that demo, or
  `examples/runtime-demo/mcp-demo.sh --down`).
- **"the demo is already running"**: run `run.sh --down`, then `run.sh` again for a fresh replay.
- **"The demo is NOT ready"**: the real answer differs from the expected topology. The listed lines name
  each difference. Nothing is wrong with your agent; report it with those lines.
- **`--live` says "PITSTOP_FORK_DIR must point at the instrumented Pitstop fork"**: live mode needs the private, instrumented fork (see [Live mode](#live-mode)).

## Stop

```bash
examples/pitstop-demo/run.sh --down
```

This removes the containers, the Neo4j volume and `.aip-pitstop-demo/`. If you change the graph yourself
(for example by importing again), evidence references from earlier answers become stale: ask the
dependency question again and retry `get_evidence` with the new snapshot (at most three attempts), or run
`--down` and replay.
