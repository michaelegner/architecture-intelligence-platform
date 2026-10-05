# Quarkus Super Heroes demo

A ready-to-run replay of the already-qualified [Quarkus Super Heroes](https://github.com/quarkusio/quarkus-super-heroes)
evidence from AIP v0.5.0 ([v0.5.1 spec](../../docs/specifications/0.5.1/specification.md) §4). It
answers the question *"what do I need to know before changing `rest-fights`?"* with real AIP
answers over MCP and REST. It does not start the Quarkus services.

## Run

Needs Docker with Compose v2 and `curl`. No LLM key, Maven, Kafka or cluster is needed. The first
run builds the AIP image. Ports 8000 and 4318 must be free, so stop the
[minimal demo](../runtime-demo/README.md) first.

```bash
examples/quarkus-super-heroes-demo/run.sh
```

The script starts AIP, Neo4j and an OpenTelemetry Collector, then:

1. imports the frozen dossier inputs: four OpenAPI documents, the `rest-fights` manifest, identity
   bindings, the offline Kubernetes manifest and the configured Service-to-Workload mapping;
2. imports an operator-authored AsyncAPI overlay for Kafka `fights` (see [PROVENANCE.md](PROVENANCE.md));
3. replays a timestamp-frozen OpenTelemetry window (`quarkus-i5`, `2026-09-25T13:06:47Z` to
   `13:06:54Z`) once, then stops the Collector, so nothing can ingest afterwards;
4. checks the real `rest-fights` answer against the frozen evidence and stops if it differs;
5. prints the MCP URL and a ready-to-copy agent prompt, also saved in `.aip-qsh-demo/prompt.txt` at the repository root.

## Connect your agent

```bash
claude mcp add --transport http --scope local aip http://localhost:8000/mcp
```

For Codex CLI, Cursor or VS Code, see [`../mcp-clients/`](../mcp-clients/README.md). Then paste the
prompt from `.aip-qsh-demo/prompt.txt`. It already contains the environment and the observation
window, which AIP needs to answer.

## Ask the questions

- [`walkthrough.md`](walkthrough.md): the eight task questions, each with the MCP and REST call and the
  real answer, keeping AIP results, dossier context and agent suggestions apart.
- [`conversation-claude-code.md`](conversation-claude-code.md): a recorded Claude Code conversation over
  this demo, checked question by question.

## What the `rest-fights` answer shows

- Seven `CALLS` to heroes, villains and narration: three `CONFIRMED` in the window and four
  `NOT_OBSERVED_IN_WINDOW` (not exercised, which does not mean unused).
- `DEPLOYED_AS` the `rest-fights` Deployment, `RESOLVED_CONFIGURED` through the configured mapping.
- `PUBLISHES_TO` Topic `fights`, declared only by the overlay and `NOT_OBSERVED_IN_WINDOW`. AIP names
  no consumer: the answer is `PARTIAL` with one `UNRESOLVED_IDENTITY` limitation, because the
  topic has no evidenced Subscription.

The gRPC call to `grpc-locations` is outside what v0.5 can answer. The dossier records it; AIP's
answer does not.

## Troubleshooting

- **"port 8000 is in use"**: stop whatever uses it (often the minimal demo:
  `examples/runtime-demo/mcp-demo.sh --down`).
- **"the demo is already running"**: run `run.sh --down`, then `run.sh` again for a fresh replay.
- **"The demo is NOT ready"**: the real answer differs from the frozen evidence. The listed lines
  name each difference. Nothing is wrong with your agent; report it with those lines.

## Stop

```bash
examples/quarkus-super-heroes-demo/run.sh --down
```

This removes the containers, the Neo4j volume and `.aip-qsh-demo/`. If you change the graph yourself (for
example by importing again), evidence references from earlier answers become stale: query again,
or run `--down` and replay.
