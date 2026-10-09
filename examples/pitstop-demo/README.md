# Pitstop demo

A ready-to-run local replay of an authored OpenTelemetry window over
[Pitstop](https://github.com/EdwinVW/pitstop), a .NET garage-management sample on RabbitMQ
([v0.6.2 spec](../../docs/specifications/0.6.2/specification.md) §4). It answers *"I am about to change
`MaintenanceJobFinished`: which services receive from the messaging destination this service publishes
to, how far can the evidence resolve that topology, and what must I still inspect?"* with real AIP
answers over MCP and REST. It does not start Pitstop.

This is the **local, reproducible** mode: it replays a frozen fixture so the demo works immediately and
offline. `run.sh --live` is the continuously running variant (see [Live mode](#live-mode)); the hosted instance is operated by the demo owner.

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

- `/mcp` shows the server as `plugin:aip:aip` with the four tools. By default it uses the plugin's
  `aip_mcp_url` setting, `http://localhost:8000/mcp`, the URL `run.sh` prints; the local demo needs no
  credentials.
- **Hosted instance (token-gated):** export two environment variables before starting Claude Code. The plugin
  reads them at start and nothing is stored in a file:

  ```bash
  export AIP_MCP_URL=https://<hosted-host>/mcp      # overrides the localhost default
  export AIP_MCP_TOKEN=<token from the operator>    # sent as "Authorization: Bearer <token>"
  claude --plugin-dir examples/pitstop-demo/claude/plugin
  ```

  The token is a secret the operator gives you: never commit it or paste it into a prompt. With
  `AIP_MCP_TOKEN` unset the plugin sends an empty `Bearer` header, which the unauthenticated local demo ignores.
  A plugin loaded with `--plugin-dir` has no way to set a plugin setting, which is why these are environment
  variables and not a `userConfig` token.

  Remove any standalone `aip` MCP server that points at the same URL (`claude mcp remove aip`): Claude Code then
  suppresses the plugin's server as a duplicate, with no error, and the skills find no AIP tools.
- The **`architecture-aware-development`** skill triggers on a task that changes an event, a message contract,
  shared data, a deployment or a service boundary. It asks the publishing service, resolves the evidence with
  the bounded drill-down, and puts an **Evidence** section into the plan: the receivers, the publisher's
  qualification, which routes carry observed evidence, the limitations as unknowns, and what AIP cannot know
  (which receiver reads a field, per-event-type receipt).
- **`/aip:inspect [service]`** prints one table of claims with qualification, route evidence, evidence
  references, the snapshot id and the limitations. It only reads.
- Both skills pre-approve only the three read-only AIP tools (`allowed-tools`) and remove `Bash`, `Write`,
  `Edit` and `NotebookEdit` from the tool pool while they run (`disallowed-tools`), so they cannot edit files or
  run commands; reading and searching the repository stays available. Claude Code applies that restriction for
  the turn in which the skill is invoked and clears it on the next user message, and `allowed-tools` alone does
  not restrict anything. Give the agent the observation context from `.aip-pitstop-demo/prompt.txt`.

### Optional mod: AIP evidence next to the plan

A second, optional plugin (`claude/mod`, spec §6.2) shows AIP's current answer beside the agent's plan. It only
reads the results of the plugin's AIP tools: it never changes a prompt, a plan or a tool result, and without it
nothing else changes. It is example client material.

```bash
claude --plugin-dir examples/pitstop-demo/claude        # loads claude/plugin and claude/mod, one flag
```

- Above the prompt a quiet line shows `AIP: consulting` while an AIP tool runs, then
  `AIP: <n> receivers, snapshot <id>, limitations <n>` with an **Evidence** button.
- The **Evidence** button, or the `/aip-evidence` command, opens a pane with one row per receiver
  (`receiver / queue: qualification, observed or declared only`) and the snapshot id and limitations. These are
  AIP's facts as returned, next to the agent's own plan, for example a route that only has declared evidence.
  Only your own action opens the pane: it does not open by itself (for example from `/aip:inspect`), and below 144
  terminal columns it still opens from the button.
- The hosted instance works the same way: set `AIP_MCP_URL` and `AIP_MCP_TOKEN` as above and remove any standalone
  `aip` MCP server first. Keep only `plugin/` and `mod/` directly under `claude/`: every plugin found there loads.
- The mod uses Claude Code's typed mod API, so it is tied to the Claude Code build: it was tested with 2.1.294 and
  2.1.295. `claude plugin validate examples/pitstop-demo/claude/mod` and
  `claude plugin test examples/pitstop-demo/claude/mod` check it by hand (CI has no Claude Code CLI; CI checks
  the files, the tool matcher and the answer fields the mod reads).
  Loading the mod makes Claude Code write editor type files (`claude/mod/.claude-plugin/types/` and
  `claude/mod/tsconfig.json`) into its folder; both are git-ignored and are not part of the demo.

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
