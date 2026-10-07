# Pitstop demo

A ready-to-run local replay of an authored OpenTelemetry window over
[Pitstop](https://github.com/EdwinVW/pitstop), a .NET garage-management sample on RabbitMQ
([v0.6.2 spec](../../docs/specifications/0.6.2/specification.md) §4). It answers *"I am about to change
`MaintenanceJobFinished`: which services receive from the messaging destination this service publishes
to, how far can the evidence resolve that topology, and what must I still inspect?"* with real AIP
answers over MCP and REST. It does not start Pitstop.

This is the **local, reproducible** mode: it replays a frozen fixture so the demo works immediately and
offline. The hosted, continuously running instance and `run.sh --live` come in a later increment.

## Run

Needs Docker with Compose v2 and `curl`. No LLM key, .NET, RabbitMQ or SQL Server is needed. The first
run builds the AIP image. Ports 8000 and 4318 must be free, so stop the
[Quarkus demo](../quarkus-super-heroes-demo/README.md) and the [minimal demo](../runtime-demo/README.md)
first.

```bash
examples/pitstop-demo/run.sh
```

The script starts AIP, Neo4j and an OpenTelemetry Collector, then:

1. imports the nine operator-authored AsyncAPI overlays (see [PROVENANCE.md](PROVENANCE.md)). The import is
   all or nothing: one invalid document rejects the whole set and the script stops;
2. replays an authored, timestamp-frozen OpenTelemetry window (`pitstop-demo`, the whole UTC day
   `2026-10-06`) once, then stops the Collector, so nothing can ingest afterwards;
3. checks the real `WorkshopManagementAPI` answer against the expected topology and stops if it differs;
4. prints the MCP URL and a ready-to-copy agent prompt, also saved in `.aip-pitstop-demo/prompt.txt` at the
   repository root.

## Connect your agent

```bash
claude mcp add --transport http --scope local aip http://localhost:8000/mcp
```

For Codex CLI, Cursor or VS Code, see [`../mcp-clients/`](../mcp-clients/README.md). Then paste the prompt
from `.aip-pitstop-demo/prompt.txt`. It already contains the environment and the observation window, which
AIP needs to answer.

## Agent setup: the Claude Code plugin

An optional plugin turns the question ladder into agent behaviour. It is example client material: it adds no
AIP behaviour, and removing it changes no answer.

```bash
claude --plugin-dir examples/pitstop-demo/claude/plugin
```

- `/mcp` shows the server as `plugin:aip:aip` with the four tools. It reads the MCP URL from the plugin's
  `aip_mcp_url` setting, default `http://localhost:8000/mcp`, the URL `run.sh` prints; change it to point at
  another AIP instance.
- The **`architecture-aware-development`** skill triggers on a task that changes an event, a message contract,
  shared data, a deployment or a service boundary. It asks the publishing service, resolves the evidence with
  the bounded drill-down, and puts an **Evidence** section into the plan: the receivers, the publisher's
  qualification, which routes carry observed evidence, the limitations as unknowns, and what AIP cannot know
  (which receiver reads a field, per-event-type receipt).
- **`/aip:inspect [service]`** prints one table of claims with qualification, route evidence, evidence
  references, the snapshot id and the limitations. It only reads.
- Both skills may use only the three read-only AIP tools; they never edit files or run commands. Give the agent
  the observation context from `.aip-pitstop-demo/prompt.txt`.

## Ask the questions

[`walkthrough.md`](walkthrough.md): the question ladder Q1–Q5, each with the MCP and REST call and the real
answer, keeping AIP results apart from what AIP cannot know. AIP has no receiver-side question: you ask
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

## Troubleshooting

- **"port 8000 is in use"**: stop whatever uses it (often another demo: `run.sh --down` of that demo, or
  `examples/runtime-demo/mcp-demo.sh --down`).
- **"the demo is already running"**: run `run.sh --down`, then `run.sh` again for a fresh replay.
- **"The demo is NOT ready"**: the real answer differs from the expected topology. The listed lines name
  each difference. Nothing is wrong with your agent; report it with those lines.
- **`--live`** exits with "not available yet".

## Stop

```bash
examples/pitstop-demo/run.sh --down
```

This removes the containers, the Neo4j volume and `.aip-pitstop-demo/`. If you change the graph yourself
(for example by importing again), evidence references from earlier answers become stale: ask the
dependency question again and retry `get_evidence` with the new snapshot (at most three attempts), or run
`--down` and replay.
