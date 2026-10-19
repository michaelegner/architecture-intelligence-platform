# v0.7.1 I4.3 — Agent-session kit

This is for the owner's one coding-agent session ([I4 spec](i4-deterministic-real-system-and-product-value-qualification.md) §5). Record the session in [`i4-evidence/agent-session.md`](i4-evidence/agent-session.md). The session adds no code. AIP serves the qualified frozen replay ([I4.1 package](i4-evidence/kafka/README.md)).

## Setup

Start from a clean `main` (≥ `1d2bf3a`) and record `git rev-parse HEAD`. You need Docker and `uv`. Run the setup, the C2 refresh and the teardown in **one shell**, which keeps `WORK` and `K`. Everything listens on loopback only. If a wait times out, it prints the log; stop there and fix it before importing.

```sh
uv sync
export WORK=$(mktemp -d) K=docs/specifications/0.7.1/i4-evidence/kafka
mkdir "$WORK/kafka" && cp "$K/c1/kafka-consumer-state.json" "$WORK/kafka/"
sed "s|@REPO@|$PWD|g; s|@WORK@|$WORK|g" docs/specifications/0.7.1/i4-evidence/session/config.template.yaml > "$WORK/config.yaml"
docker run -d --name aip-session-neo4j -p 127.0.0.1:17687:7687 -e NEO4J_AUTH=neo4j/session-local-only \
  neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93
timeout 120 sh -c 'until docker logs aip-session-neo4j 2>&1 | grep -q "Started."; do sleep 2; done' \
  || docker logs --tail 20 aip-session-neo4j        # Neo4j is up; on timeout, shows its log
NEO4J_PASSWORD=session-local-only CONFIG_PATH="$WORK/config.yaml" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$WORK/server.log" 2>&1 &
SERVER=$!
timeout 60 sh -c 'until curl -s -o /dev/null localhost:8000/docs; do sleep 2; done' \
  || tail -20 "$WORK/server.log"                     # the server is up; on timeout, shows its log
curl -s -X POST localhost:8000/api/import
```

For the agent, check out `hungCS22hcmiu/ecommerce-system` at `cd65365838ea880185a02e6536fa347439bfa274` in its own directory. Connect the "with AIP" arms to `http://localhost:8000/mcp`. `tools/list` must show six tools, including `get_destination_consumers`. The installed `aip` plugin is older (four tools), so don't use it here.

## Context card

Give the agent this card in the AIP arms, and note anything else you give it:

- `broker_id: kafka:ecommerce-local`
- `environment: local`
- `orders.created` Topic id: `topic:owned:d50263b3b6fb95e3e67b5ad7bc404874526fee87b3a9b333cc1c7fd1d87f413f`

## Prompt (unchanged in every arm)

> I'm changing the `OrderCreated` event that order-service publishes to the Kafka topic `orders.created` (renaming a field). Which Services may be affected, and how sure can we be?

## Arms

The agent works in the ecommerce-system checkout. In every arm it may read the code and run commands, including starting the system locally.

1. **Without AIP:** a fresh agent conversation with no AIP tools.
2. **With AIP, C1:** a fresh agent conversation with the AIP tools, with C1 imported.
3. **With AIP, C2:** this deliberately **continues the arm-2 conversation**, so the record shows whether the agent notices the changed state at a new T and does not read it as "no consumer". In the setup shell, refresh the capture, then ask the prompt again in that conversation:
   ```sh
   cp "$K/c2/kafka-consumer-state.json" "$WORK/kafka/"
   curl -s -X POST localhost:8000/api/import
   ```

Teardown, in the setup shell: `kill $SERVER; docker rm -f aip-session-neo4j`.
