# v0.8.1 I0 — Protocol spike record

**Date:** 2026-11-26  
**Specification:** [v0.8.1 §3](specification.md#3-i0--protocol-spike)  
**Result:** outcome **B**. Claude Code 2.1.332 uses MCP skills only on protocol `2026-07-28`. D3 is set to B.

## Client and harness

- **Client:** Claude Code 2.1.332 (CLI), `/login` with a Claude Pro subscription, auto mode.
  Each run started with `MCP_SDK_GENERATION=v2`, `--strict-mcp-config` and one HTTP server entry,
  in a new empty folder. All runs used `MCP_PROTOCOL_NEGOTIATION=auto`, except the control run.
- **Server:** a throwaway harness, not committed. It builds the AIP MCP server from
  `origin/main` `055b668`, the same way that `build_mcp_server` does, with the six default tools.
  The tools are not connected to Neo4j, and no tool was called. The harness adds
  one test skill, `skill://aip-spike/aip-spike-probe/SKILL.md`, through the SDK `Extension` hook
  (`mcp==2.3.0`). The skill body holds the token `AIP-SPIKE-7F3A`.
- **Evidence:** a wire log of each HTTP exchange (method, path, `MCP-Protocol-Version`, request
  and response body), the Claude Code debug log, and screen captures of `/skills` and the prompt
  "Use the aip-spike:aip-spike-probe skill and quote its token."
- **Self-check:** before the runs, raw JSON-RPC requests checked the modes. The modern mode passed
  every check. The legacy mode passed every check except the advertisement (see the SDK finding),
  and the owner chose to add run R1b for it. `skills/list` and `skills/get` return the SEP-2640 shape. `resources/read` returns 319 bytes, and their sha256
  equals the manifest digest
  (`sha256:2d2a2bd034c32260132dacef27df9f2c7c4ad6f08c815dd230a916d544d33c3b`).

## SDK finding

`mcp==2.3.0` treats `capabilities.extensions` as a `2026-07-28` field. On a `2025-11-25`
`initialize` result, the SDK removes it, so AIP cannot advertise the Skills extension on the
existing session through the SDK. Run R1b added the field with a harness rewrite to test the
client anyway.

## Runs

| Run | Server mode | Negotiated | `skills/list` called | Skill in `/skills` | Token quoted |
|---|---|---|---|---|---|
| R0 | Production-equivalent: no extension, guard on | `2025-11-25` (legacy) | — | No | — |
| R1 | Extension, guard on (SDK as is: not advertised) | `2025-11-25` (legacy) | No | No | No ("Unknown skill") |
| R1b | R1, plus `extensions` added to the `initialize` result | `2025-11-25` (legacy) | No | No | No ("Unknown skill") |
| R1b control | R1b, with `MCP_PROTOCOL_NEGOTIATION=legacy` | `2025-11-25` (legacy) | No | No | — |
| R2 | Extension, `ModernProtocolGuard` bypassed | `2026-07-28` (modern) | Yes | Yes: `aip-spike:aip-spike-probe`, source `mcp` | Yes: `AIP-SPIKE-7F3A` |

**R0 to R1b.** Claude Code first sends `server/discover` with `MCP-Protocol-Version: 2026-07-28`.
The AIP guard rejects it: HTTP 400, `-32600`, "The direct protocol era cannot be used for a
negotiated follow-up request". Claude Code then falls back to `initialize` and uses `2025-11-25`.
It calls `tools/list`, `prompts/list` and `resources/list`, but never `skills/list`. This is also
true in R1b, where the `initialize` result it receives contains
`"extensions":{"io.modelcontextprotocol/skills":{}}`. The control run sends no
`server/discover` probe, and the result is the same. Therefore, the legacy result does not come
from a failed modern probe.

**R2.** At connection (18:46:01Z), Claude Code sends `server/discover`, then `prompts/list`,
`skills/list`, `resources/list` and `tools/list`, and it opens `subscriptions/listen`. When the
skill is used (18:46:25Z), it sends `resources/read` for the `SKILL.md`.

The wire log writes each line when the response ends, so the listen stream is logged last, at
`/exit` (18:46:52Z). The evidence indicates that the stream was open for the whole session: the
debug log shows "connected with subscribe=true" at 18:46:01Z, and the stream carries three pings.
So `resources/read` was served while the listen stream was open.

Claude Code did not call `skills/get`. No approval prompt was shown: the skill use was
"Allowed by auto mode". Abridged excerpts, with `_meta` left out and the frontmatter and digest
shortened:

```text
server/discover   result.capabilities = {"extensions":{"io.modelcontextprotocol/skills":{}},
                  "prompts":{"listChanged":true},"resources":{"listChanged":true,"subscribe":true},
                  "tools":{"listChanged":true}}; supportedVersions = ["2026-07-28"]
                  client capabilities = {"roots":{"listChanged":true},"elicitation":{"form":{},"url":{}},
                  "extensions":{"io.modelcontextprotocol/tasks":{}}}
skills/list       params {} → {"resultType":"complete","skills":[{"uri":"skill://aip-spike/aip-spike-probe/SKILL.md",
                  "frontmatter":{...},"resources":[{"uri":"skill://aip-spike/aip-spike-probe/SKILL.md",
                  "digest":"sha256:2d2a…3c3b","size":319}]}],"ttlMs":0,"cacheScope":"public"}
resources/read    params {"uri":"skill://aip-spike/aip-spike-probe/SKILL.md"}
```

All seven R2 requests carry `_meta` with `protocolVersion`, `clientInfo` and `clientCapabilities`.
The client declares no Skills extension of its own.

## Outcome and conformance

- **Outcome A is not viable.** On `2025-11-25`, Claude Code does not request skills, even when
  the server advertises the extension. Also, SDK 2.3.0 cannot advertise it there.
- **Outcome B is a viable direction.** On `2026-07-28`, the SDK and Claude Code complete the
  SEP-2640 flow, and the skill loads. R2 bypassed `ModernProtocolGuard`. It therefore does **not**
  show that AIP's production ingress supports `2026-07-28` safely. Outcome B is the conformant
  route: the extension runs on the era it is defined for.
- **Outcome C does not apply:** the self-check passed, and R2 succeeded with the same client configuration.

## Consequences for I1 (outcome B)

1. The owner confirmed on 2026-11-26 that outcome B still fits a patch release (spec D3).
2. ADR 0018 amends ADR 0016: `/mcp` also serves `2026-07-28`. The guard change needs its own test,
   proven by disabling the change.
3. Every tool needs a regression test on both eras. The `2025-11-25` path must stay unchanged:
   R0 shows that clients fall back to it when the modern probe fails.
4. **`subscriptions/listen`.** In the modern era, Claude Code opens `subscriptions/listen`, a
   long-lived SSE stream, at connection. In R2 the stream sent an acknowledgement and pings, a
   concurrent `resources/read` was served while it was open, and it closed when the client exited.
   This one short session does not qualify the method. The [guard](../../../app/mcp/guard.py)
   docstring records a past SDK hang with this method under AIP's stateless single-worker
   deployment. The owner decided (spec D9) that AIP declines the method. I1 verifies that this is
   possible with SDK 2.3.0 and that Claude Code still loads the skills.
5. Claude Code did not call `skills/get`. The I1 tests still cover it, because SEP-2640 requires it.
