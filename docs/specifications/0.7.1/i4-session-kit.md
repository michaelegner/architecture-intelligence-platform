# v0.7.1 I4.3 — Agent-session kit

This is for the owner's one coding-agent session ([I4 spec](i4-deterministic-real-system-and-product-value-qualification.md) §5). Record the session in [`i4-evidence/agent-session.md`](i4-evidence/agent-session.md); each step below says which fields to fill and when. The session adds no code. AIP serves the qualified frozen replay ([I4.1 package](i4-evidence/kafka/README.md)).

**Isolation.** Each arm starts Claude Code with the `aip`, `aip-mod` and `memtrace-skills` plugins disabled and only the MCP servers given on the command line. Every other MCP server is dropped, including the Claude Docs connector. Checked with Claude Code 2.1.304: with an empty MCP config the session has no MCP tools and no plugin skills. The `/mcp` gate in each arm confirms it.

## 0. Before you start

Fill in the Setup table:
- *Date, operator*;
- *Agent client, model and version*: `Claude Code <version>, claude-opus-5-5, effort high`. Use the same model and effort in every arm.

Check the agent's checkout, which must be clean at `cd65365…`. Recreate it if needed:

```sh
git clone https://github.com/hungCS22hcmiu/ecommerce-system.git ~/code/ecom-session
git -C ~/code/ecom-session checkout --detach cd65365838ea880185a02e6536fa347439bfa274
```

Then check it. Both lines must print `OK`; on `STOP`, fix the checkout first:

```sh
[ "$(git -C ~/code/ecom-session rev-parse HEAD)" = cd65365838ea880185a02e6536fa347439bfa274 ] && echo OK || echo "STOP: wrong commit"
[ -z "$(git -C ~/code/ecom-session status --porcelain)" ] && echo OK || echo "STOP: checkout not clean"
```

Note the clock time. It starts *Setup effort*.

## 1. AIP setup (shell 1, kept open)

Start from a clean AIP `main` (≥ `1d2bf3a`). You need Docker and `uv`. Shell 1 runs the setup, the C2 refresh and the teardown, and it keeps `WORK`, `K`, `NEO4J` and `SERVER`. Everything listens on loopback only.

First, the checks. Both lines must print `OK`; on `STOP`, fix it before you go on:

```sh
git merge-base --is-ancestor 1d2bf3a HEAD && [ -z "$(git status --porcelain)" ] && echo OK || echo "STOP: AIP checkout not clean or older than 1d2bf3a"
docker ps -a --format '{{.Names}}' | grep -qx aip-session-neo4j && echo "STOP: aip-session-neo4j exists (remove it only if it is yours)" || echo OK
```

Then the setup. If a wait times out, it prints the log; stop there.

```sh
uv sync
export WORK=$(mktemp -d) K=docs/specifications/0.7.1/i4-evidence/kafka
mkdir "$WORK/kafka" && cp "$K/c1/kafka-consumer-state.json" "$WORK/kafka/"
sed "s|@REPO@|$PWD|g; s|@WORK@|$WORK|g" docs/specifications/0.7.1/i4-evidence/session/config.template.yaml > "$WORK/config.yaml"
NEO4J=$(docker run -d --name aip-session-neo4j -p 127.0.0.1:17687:7687 -e NEO4J_AUTH=neo4j/session-local-only \
  neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93)
timeout 120 sh -c "until docker logs $NEO4J 2>&1 | grep -q Started.; do sleep 2; done" \
  || docker logs --tail 20 "$NEO4J"                  # Neo4j is up; on timeout, shows its log
NEO4J_PASSWORD=session-local-only CONFIG_PATH="$WORK/config.yaml" \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 > "$WORK/server.log" 2>&1 &
SERVER=$!
timeout 60 sh -c 'until curl -fs -o /dev/null localhost:8000/health/neo4j; do sleep 2; done' \
  || tail -20 "$WORK/server.log"                     # server and graph are up; on timeout, shows its log
curl -fsS -X POST localhost:8000/api/import | grep -q '"committed":true' && echo "import OK" || echo "STOP: import failed"
cat > "$WORK/aip-session.mcp.json" <<'EOF'
{"mcpServers": {"aip-session": {"type": "http", "url": "http://localhost:8000/mcp"}}}
EOF
echo "$WORK/aip-session.mcp.json"                    # the MCP config path for arm 2
git rev-parse HEAD
```

Continue only after `import OK`. Fill in *AIP checkout* with the last line.

## Context card and prompt

The context card goes to the AIP arms only:

- `broker_id: kafka:ecommerce-local`
- `environment: local`
- `orders.created` Topic id: `topic:owned:d50263b3b6fb95e3e67b5ad7bc404874526fee87b3a9b333cc1c7fd1d87f413f`

The prompt is the same in every arm:

> I'm changing the `OrderCreated` event that order-service publishes to the Kafka topic `orders.created` (renaming a field). Which Services may be affected, and how sure can we be?

In every arm the agent may read the code and run commands, including starting the system locally. Approve its commands as asked, and note what it ran. Don't put a prompt on the `claude` command line: `--mcp-config` takes several values and would read it as a file. Don't use `--disable-slash-commands`, because it removes `/mcp` and `/export`.

## 2. Arm 1: without AIP (shell 2)

```sh
cd ~/code/ecom-session
PLUGINS_OFF='{"enabledPlugins":{"aip@aip-plugins":false,"aip-mod@aip-plugins":false,"memtrace-skills@memtrace":false}}'
claude --model claude-opus-5-5 --effort high --settings "$PLUGINS_OFF" --strict-mcp-config --mcp-config '{"mcpServers":{}}'
```

1. Gate: `/mcp` lists **no** servers.
2. Paste the prompt only, with no card.
3. When it has answered, run `/export`.
4. Fill in **section 1** (the five bullets).
5. Exit.

## 3. Arm 2: with AIP, C1 (shell 2, fresh session)

```sh
claude --model claude-opus-5-5 --effort high --settings "$PLUGINS_OFF" --strict-mcp-config --mcp-config <path printed in step 1>
```

1. Gate: `/mcp` lists only `aip-session`, connected, with **six tools**, including `get_destination_consumers`. If anything else is listed (`aip`, `memtrace`, Claude Docs), stop.
2. Fill in *Setup effort*: minutes from the step-0 time to now.
3. Paste the card, then the prompt.
4. Fill in *Context card given*: the card verbatim, plus anything else you had to tell the agent.
5. When it has answered, run `/export`.
6. Fill in **section 2**.
7. Don't exit: arm 3 continues this conversation.

## 4. Arm 3: with AIP, C2 (the same session)

This deliberately continues the arm-2 conversation, so the record shows whether the agent notices the changed state at a new T and does not read it as "no consumer".

1. Note the time, then refresh in shell 1:
   ```sh
   cp "$K/c2/kafka-consumer-state.json" "$WORK/kafka/"
   curl -fsS -X POST localhost:8000/api/import | grep -q '"committed":true' && echo "import OK" || echo "STOP: import failed"
   ```
2. Only after `import OK`, paste the prompt again in the arm-2 session.
3. Fill in *Effort: refresh (C1 → C2)*: minutes from the `cp` to the agent's answer.
4. Run `/export`.
5. Fill in **section 3**.

## 5. Teardown (shell 1)

```sh
kill $SERVER; docker rm -f "$NEO4J"                 # only the container this run created
```

## 6. Assessment, after all arms

Fill in the Assessment table from the three sections:

| Field | From |
|---|---|
| Broker evidence changed the investigation or next action? | arm 1 vs. arms 2 and 3 |
| payment-service kept as "no attachment at T", not "does not consume"? | arm 3 |
| `ops-tail` found or handled? | arm 2 |
| At-T observation presented as a complete change-impact assessment? | arms 2 and 3 |
| Value outweighs the upkeep? | your judgement, with the effort minutes |

*Service mapping* and *Unresolved / ambiguous rows* are pre-filled; check that they match what you saw.

## 7. Decision, last

Fill in `CONTINUE | NARROW | DEFER | STOP` and a one- or two-sentence reason. The I4 result record and the I4 → I5 handoff (I4.3b) are drafted from the finished record.
