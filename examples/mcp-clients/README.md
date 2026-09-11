# Connecting a Coding-Agent Client to AIP

This directory has one candidate setup guide per targeted client family:

- [Codex CLI](codex.md)
- [Claude Code](claude-code.md)
- [Cursor](cursor.md)
- [VS Code](vscode.md)

**Candidate setup.** Every command and configuration fragment in these guides was checked against
that client's current official documentation immediately before writing this guide (source URL and
verification date recorded in each guide, and consolidated in
`docs/specifications/0.4.2/i2-completion-record.md` once I2 completes). That is **syntax
verification**, not **interoperability qualification** —
whether the actual named client can complete the deterministic AIP workflow end to end against a
real release candidate is I3's job, not I2's. Until I3 publishes its qualified client/platform
matrix, nothing here is a "supported" claim.

## 1. Prepare the deterministic demo

```bash
cp .env.example .env
examples/runtime-demo/mcp-demo.sh --serve
```

This starts AIP, Neo4j and an OTel Collector, imports the bundled declared architecture, seeds one
timestamp-frozen batch of runtime telemetry, and then **stops before issuing any MCP call itself** —
the next MCP caller must be your coding-agent client, not this script. It prints:

```text
MCP endpoint:
http://localhost:8000/mcp
```

## 2. Configure your client

Pick a guide above and point it at `http://localhost:8000/mcp`.

## 3. Ask the stable prompt

```text
Use AIP to find architecture drift for service:order-service in the demo
environment between 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z.

For every finding:
1. explain its qualification;
2. resolve its evidence using the same snapshot;
3. identify what AIP actually established;
4. do not infer facts AIP does not establish.
```

If the demo's observation window ever changes, this prompt, the `--serve` output, and every guide
in this directory change together — a stale timestamp here is a defect, not a rounding error.

## 4. Expect two deterministic findings

| Dependency | Qualification | Evidence | Meaning |
|---|---|---|---|
| `LegacyPricingService` | `OBSERVED_ONLY` | OpenTelemetry observation of `GET /pricing/{sku}` | A runtime dependency AIP has no declaration for. |
| `unused-q` | `NOT_OBSERVED_IN_WINDOW` | AsyncAPI declaration | Declared, but not seen in this window. |

**`NOT_OBSERVED_IN_WINDOW` is never "unused", "dead", "obsolete", or "safe to remove."** It means
exactly what it says: not observed *in this window*, nothing more.

Resolving either finding's evidence is not a second independent guess — `get_evidence` resolves
provenance for the same claim at the **same `snapshot_id`** the drift answer returned. No guide
here should ever recommend resolving evidence without preserving that snapshot identity.

## 5. What's deterministic and what isn't

AIP's tool semantics and this demo's data are deterministic — the two findings above, their
qualifications, and their evidence never change between clean runs. **How a coding agent chooses to
call those tools and phrase its explanation is not** — a different client, model, or session may
call the tools in a different order, ask a follow-up, or word its summary differently. I2 completion
does not depend on any model producing one exact sentence; it depends on AIP's own result being
reproducible underneath whatever the agent says about it.

## 6. Local/trusted-network only

- `/mcp` has no public-internet authentication in `v0.4.2` — never expose it directly to an
  untrusted network.
- A client running on your own machine can normally reach `http://localhost:8000/mcp`. A
  hosted/cloud agent usually **cannot** reach your `localhost` without an explicit networking
  mechanism, which is outside `v0.4.2`'s scope — none of these guides introduce tunneling or a
  public endpoint as a workaround.
- AIP itself needs no LLM API key for its deterministic MCP correctness path. Your coding-agent
  client may still need its own normal account/model access.

## 7. Tear down

```bash
examples/runtime-demo/mcp-demo.sh --down
```
