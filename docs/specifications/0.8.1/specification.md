# AIP v0.8.1 — Server-Provided Agent Skills

**Status:** Draft 0.1 (proposed)  
**Target:** `v0.8.1`  
**Baseline:** Published and post-release-verified [`v0.8.0`](../../release-validation/v0.8.0-release-record.md)  
**Scope authority:** [ROADMAP.md — v0.8.1](../../../ROADMAP.md#v081--server-provided-agent-skills-proposed)

## 1. Promise

v0.8.1 is an **interoperability patch release**. It adds no architecture question, canonical
entity or relation, public answer schema or MCP tool. It changes no tool answer.

The [MCP Skills extension](https://modelcontextprotocol.io/extensions/skills/overview)
([SEP-2640](https://modelcontextprotocol.io/seps/2640)) lets a server serve `SKILL.md` files. A client
finds them with `skills/list` and `skills/get` and reads them with `resources/read`. Claude Code
supports the extension from version 2.1.331.

AIP's rules for reading its answers are server-contract knowledge. Today they exist only in the
Pitstop Claude Code plugin
([`architecture-aware-development`](../../../examples/pitstop-demo/claude/plugin/skills/architecture-aware-development/SKILL.md)),
so only users of that plugin get them, and the text can drift from the server it describes.

The release promise is:

> **The AIP MCP server serves agent skills that state how to read its answers correctly. A
> skills-capable client gets the same reading rules as the tool contract it calls, from the same
> server version.**

## 2. Constraints

- Patch-release semantics only. The v0.8 architecture-question space and all Architecture
  Knowledge semantics stay unchanged.
- Every tool answer, `tools/list` and every frozen schema under `schemas/architecture_intelligence/`
  stay byte-for-byte unchanged.
- A skill is static text in the package. AIP does not generate skill content from the graph.
- A skill contains no deployment-specific content. The Pitstop service-id table stays in the plugin.
- The binding-picture skill exists only when `architecture_intelligence.experimental.binding-picture`
  is on. It follows the `get_binding_picture` tool.
- A skill states nothing that [`docs/mcp.md`](../../mcp.md) and the frozen contract do not state.
- A skill does not rely on host permission fields such as `allowed-tools`. SEP-2640 lets a host
  ignore frontmatter fields that widen permissions. The read-only rules are in the skill text.
- AIP does not offer `directoryRead`. Each skill is one `SKILL.md` file.
- Implement against this lightweight specification. No increment-specific specification files are
  required. I0 writes one short record.

## 3. I0 — Protocol spike

### 3.1 Problem

The Skills extension is defined for MCP protocol `2026-07-28` and later. AIP serves standard
negotiated MCP (`initialize` and `2025-11-25`) only:
[`app/mcp/guard.py`](../../../app/mcp/guard.py) rejects a follow-up request whose
`MCP-Protocol-Version` header names the `2026-07-28` era
([ADR 0016](../../adr/0016-public-architecture-knowledge-adapters.md)). It is not known whether
Claude Code requests skills on a `2025-11-25` session.

The pinned SDK (`mcp==2.3.0`) has no Skills helper. It has a generic extension hook,
`mcp.server.extension.Extension`, consumed by `MCPServer(extensions=[...])`. The hook can
advertise settings under `capabilities.extensions`, add resources, and bind new request methods
through `MethodBinding`, optionally restricted to given protocol versions.

### 3.2 Required outcome

1. Run AIP locally with one minimal test skill behind the SDK extension hook. Do not merge this code.
2. Connect Claude Code 2.1.332 or later to it and record:
   1. the protocol version that Claude Code uses with AIP today;
   2. whether Claude Code calls `skills/list` on a `2025-11-25` session;
   3. what Claude Code does when AIP also admits `2026-07-28`.
3. Write the result to `docs/specifications/0.8.1/i0-protocol-spike-record.md` (one page) and set D3.

### 3.3 Outcomes

| Outcome | Condition | Consequence |
|---|---|---|
| **A** | Claude Code requests and loads skills on a `2025-11-25` session. | Serve the skills methods on the existing negotiated session. The guard does not change. |
| **B** | Claude Code requests skills only on `2026-07-28`. | `/mcp` also admits `2026-07-28`. Write ADR 0018, which amends ADR 0016. Qualify every tool on both eras. The owner confirms that B still fits a patch release before I1 starts. |
| **C** | Neither A nor B works. | Stop v0.8.1 and record the finding (D7). |

## 4. I1 — Skills extension

### 4.1 Required outcome

- `AipSkillsExtension`, a subclass of `mcp.server.extension.Extension`:
  - identifier `io.modelcontextprotocol/skills`, settings `{}`;
  - declares the `resources` capability, as SEP-2640 requires;
  - binds `skills/list` and `skills/get` through `MethodBinding`, with `protocol_versions` as set by D3;
  - serves each `SKILL.md` through `resources/read`.
- Each skill URI is `skill://aip/<name>/SKILL.md`. The last path segment equals the frontmatter `name`.
- `skills/list` and `skills/get` return the frontmatter exactly as it is in the file.
- `skills/get` with an unknown URI returns JSON-RPC error `-32602`.
- `ttlMs` and `cacheScope` are deterministic and equal the `tools/list` cache hint in
  [`app/mcp/server.py`](../../../app/mcp/server.py) (`public`, `0`).
- `build_mcp_server(binding_picture=...)` passes the flag to the extension, so the skill set follows
  the tool set.
- The skill files are package data in `app/mcp/skills/<name>/SKILL.md`.

### 4.2 Skills

| Skill | Listed | Content |
|---|---|---|
| `aip-reading-answers` | Always | The observation-context rules (whole UTC days in the past, inclusive window end). The qualification on a claim is the publisher's. `evidence_refs` and `resolution_evidence_refs` mean different things. The snapshot retry: on `SNAPSHOT_NOT_AVAILABLE`, ask the question again and retry `get_evidence`, at most three attempts. A route without observed evidence is not an unused route. AIP has no payload or field-level knowledge. Report limitations and `NOT_ANSWERED` statements as unknowns. Use AIP read-only. The text is the deployment-neutral part of the current plugin skill. |
| `aip-binding-picture` | Flag on | The query and evidence modes. The crossing values (`INBOUND`, `INSIDE`, `OUTBOUND`, `NONE`, `UNRESOLVED`) and the status values (`PROMISED_AND_OBSERVED`, `PROMISED_NOT_OBSERVED`, `UNRESOLVED` with a reason such as `PROMISE_COVERAGE_MISSING`). The limits: an attachment is not event handling, producers are declared only, and delivery between brokers is never established (`CROSS_BROKER_DELIVERY_NOT_ESTABLISHED`). The semantics are experimental. |

The Pitstop plugin skill stays unchanged in v0.8.1 (D6).

### 4.3 Acceptance

All tests use the real mounted ASGI transport, as
[`tests/unit/test_mcp_discovery.py`](../../../tests/unit/test_mcp_discovery.py) does.

- The server advertises `io.modelcontextprotocol/skills` and the `resources` capability.
- `skills/list`, `skills/get` and `resources/read` round-trip for each listed skill. The returned
  frontmatter equals the file.
- Flag off: `skills/list` lists only `aip-reading-answers`, and `skills/get` for
  `aip-binding-picture` returns `-32602`. Flag on: both skills are listed.
- `tools/list` is unchanged, flag off and flag on, compared with a stored v0.8.0 fixture.
- Drift guard: each tool name that a skill names is in `TOOL_NAMES`. Each status, crossing and
  limitation code that a skill names exists in the contract enums.
- Outcome B only: a guard test for the admitted `2026-07-28` era, proven by disabling the guard
  change and showing that the test fails.

## 5. I2 — Qualification and release

Before candidate freeze:

- I1 acceptance tests pass;
- full unit and integration suites pass;
- existing v0.8 golden-path and demo semantics stay unchanged;
- one recorded Claude Code session against the candidate shows that it found and loaded the AIP
  skills. This is a demonstration: one run, no scoring;
- [`docs/mcp.md`](../../mcp.md) gets a "Skills" section;
- CodeQL, dependency and repository security checks satisfy the current release policy;
- version consistency, CHANGELOG, release notes, `server.json` and release metadata are updated
  through the normal release workflow (`release-publication` skill).

No product-value pilot is required. A hosted redeploy is the owner's decision.

## 6. Exit criteria

v0.8.1 is complete when:

> **A skills-capable MCP client that connects to AIP finds and reads the AIP skills that match the
> tools it is offered, and every tool answer and schema is unchanged from v0.8.0.**

## 7. Decision register

| ID | Decision | Status |
|---|---|---|
| D1 | v0.8.1 is an interoperability patch release: no new question, tool, schema or answer change. | Accepted (owner) |
| D2 | Build the extension on the SDK `Extension` hook. Do not wait for an SDK Skills helper. | Proposed |
| D3 | The protocol era on which AIP serves the skills methods. | Open: set by I0 |
| D4 | Two skills. The binding-picture skill follows the experimental flag. | Proposed |
| D5 | No `directoryRead`. Each skill is one file. | Proposed |
| D6 | The Pitstop plugin skill stays unchanged. Removing its duplicate text is deferred. | Proposed |
| D7 | If I0 ends in outcome C, stop v0.8.1 and record the finding. | Proposed |

## 8. Baseline carry-forward

Once v0.8.1 ships, a later release that changes how a tool's answer is read updates the matching
skill in the same release. The I1 drift-guard tests enforce the names and codes; the text stays a
review responsibility.
