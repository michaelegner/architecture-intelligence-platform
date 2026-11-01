# Blind bindingPicture ToolSeed run — Sokol111

**Status:** protocol frozen 2026-11-01 before the first session. Result: see §5 (filled after the run).

## 1. Question

Can a coding agent that has only `prompt.md`, a supplied question and a fresh Sokol111 workspace produce a
binding picture that matches the frozen references? The agent does not see this repository, the
earlier implementation (`build.mjs`, `source-only/`) or the comparison results.

## 2. Arms

| Arm | Workspace | Provider | Reference |
|---|---|---|---|
| P− | 16 Sokol111 clones at the `S1-02-clone.txt` freeze SHAs | none | `source-only/COMPARISON.md` table (pairs and crossing) |
| P+ | same | hosted AIP `https://mcp.daip.io/mcp` (v0.8.0) | `docs/specifications/0.8.0/i2-vectors/c1-expected.json` |

Pre-check (2026-11-01): the hosted `get_binding_picture` answer has the same row signature
(broker, topic, consumer, crossing, status, reason, cross_broker_producers) and the same four
limitation codes as C1. Its snapshot is `aip:snapshot:v1:7f171aea…c413`, capture `2026-10-21T17:53:57Z`.

One session per arm. Same model (`claude-opus-5-5`), Claude Code 2.1.316, default effort,
`claude -p` under `env -i`, a new empty `CLAUDE_CONFIG_DIR` (credentials only), auto memory off.

## 3. Isolation

- Run home `~/toolseed-blind`, outside `~/code`. Each arm has its own workspace and config dir.
- Read denied: `~/code/**` (all AIP worktrees and captures), `~/.claude/**`, `~/.claude.json`,
  `/tmp/claude-<uid>/**`, the other arm's session.
- Denied tools: WebFetch, WebSearch, Artifact, `curl`, `wget`, `gh`, all claude.ai connectors. P−
  has no MCP server. P+ has only the hosted AIP server.
- Check after each run: the `system/init` event lists no web tool, no Artifact, no `mcp__plugin_*`
  or `mcp__claude_ai_*` tool (P+: only `mcp__aip__*`). The transcript has no path outside the
  workspace and no `michaelegner`, `daip.io` (P−), `ArchitectureIntelligencePlatform` or
  `.claude/projects`.

## 4. Input and scoring (frozen)

Input: `prompt.md` verbatim, then this block (the question and boundary from `source-only/inputs.json`):

```text
SUPPLIED QUESTION AND BOUNDARY
- Question: When moving Catalog Management (Catalog and Image) to Apache Kafka, which bindings are
  configured across the boundary and what is not established?
- Boundary: Catalog Management = ecommerce-catalog-service and ecommerce-image-service. This is the
  task definition, not inferred from source.
- Environment: local.
- The Sokol111 repositories are in ./src. Write all outputs into this workspace.
```

Scoring items, both arms unless noted:

| Id | Item | Pass rule |
|---|---|---|
| S1 | Required bindings | all 7 INBOUND/OUTBOUND/INSIDE consumer×topic pairs of the reference are shown |
| S2 | Crossing | each shown reference pair has the reference crossing class |
| S3 | NONE rows | the 2 tenant NONE rows: not scored (the prompt allows "relevant only") |
| S4 | Extra bindings | every extra pair is listed; each is judged supported or unsupported by the clones |
| S5 | No manufactured claims | P−: no observation, promise, delivery or handling claim. P+: no status stronger than the provider's; `PARTIAL` kept |
| S6 | References | ≥ 3 sampled file/line refs resolve at the freeze SHAs, including one inbound tenant row |
| S7 | Unknowns | missing inputs are listed (P−: no broker capture, no owner promise) |
| S8 | Identity | consumer identity is not by name similarity alone; repo-qualified vs service ids are consistent |
| S9 | Provider fidelity (P+) | the 9 statuses and reasons, the 4 limitation codes, the snapshot id and the evidence refs are exact |
| S10 | Provider removal (P+) | the agent shows or states that provider-only findings disappear without the provider |
| S11 | Artifact | self-contained HTML with a direction or status filter and row selection |
| S12 | Honest checks | checks not performed (for example, browser opening in headless mode) are stated as not performed |

A session is invalid if it is cut off by a usage limit or if §3 shows an isolation breach.
An invalid session is kept and replaced once.

## 5. Result

Run 2026-11-01. P− 20:23–20:32Z (101 turns, 498 s). P+ 20:32–20:45Z (62 turns, 729 s). Both valid.
Outputs, input, final message and session metadata: `results/P-/`, `results/P+/`. Raw streams and
config dirs are not kept.

**Condition actually tested: a Read/Write-only agent.** The §3 Bash allow list never took effect,
so neither agent had search, `node` or git (see "Deviations").

**Outcome:** under that condition, both blind agents reproduced the reference.

- **P−** found all 7 cross-boundary pairs with the correct crossing, from source alone.
- **P+** shows the provider answer exactly: 9/9 rows, 4/4 limitations, the snapshot and 16/16 refs.
  It also resolved the refs in evidence mode, which the earlier implementation did not do.
- **One P+ defect:** its provider-off view still shows two provider statuses, and it reported that
  toggle as a performed check.

| Id | P− | P+ |
|---|---|---|
| S1 | PASS: 7/7 (B1/B2 split one pair by producer; B3, B4, B5, B6, B7) | PASS: 9/9 (R1–R9) |
| S2 | PASS: all crossings match (`internal` = INSIDE) | PASS: all match; re-derived from the boundary |
| S3 | NONE rows not shown | NONE rows shown, hidden by default |
| S4 | B8 (image consumes its own promoted events on `catalog.product.events`): supported. B9–B14: shared resources (broker, topic provisioning, DLQ, offsets, headers, standalone addresses), not consumer×topic pairs | R10 (DLQ, unresolved), R11 (shared broker): not consumer×topic pairs |
| S5 | PASS: says "declared or referenced, never observed"; no promise claims | PASS: `PARTIAL` kept; statuses verbatim, joined by exact topic + `service:` id |
| S6 | PASS: 6 refs checked at freeze SHAs (event factory, both topic registries, image values 29-30, auto-create line 35, product-query handler module) | PASS: 4 refs checked at freeze SHAs (E18 catalog values 31-42 for the inbound tenant row, E10 image event factory, E14 tenant consumer, E20 product-query values) |
| S7 | PASS | PASS |
| S8 | PASS: consumer names traced to code registration by exact name | PASS |
| S9 | — | PASS: rows, reasons, limitations, snapshot and refs equal to C1 / the hosted answer |
| S10 | — | PARTIAL: `?provider=off` removes the statuses and refs from the table and the evidence list, but the static verification log still shows two provider statuses (R1 `PROMISED_AND_OBSERVED`, R6 `PROMISE_COVERAGE_MISSING`), labelled as provider |
| S11 | PASS: direction filter + unresolved filter, row selection | PASS: direction, unresolved and provider filters, row selection |
| S12 | PASS: browser test reported as not done | PARTIAL: the browser test is reported as not done, but the final message lists the provider toggle under "Checks performed" ("removes all provider statuses"). It was not run, and the render shows it is partly false (S10) |

Operator checks:

- **Isolation clean:** `system/init` has no web tool, no Artifact and no plugin or claude.ai MCP
  tool; P+ has only `mcp__aip__*`. No tool input names a path outside the workspace. The stream has
  none of the §3 strings.
- **Headless render (operator):** all three pages render (P−, P+, P+ `?provider=off`). The P+
  in-page integrity checks pass: 37 source facts referenced, 16/16 provider refs resolve. Clicks
  were not exercised.

Deviations and limits:

- **Harness:** each agent's only Bash call was a compound command (`cd …;` / `&&` chains). It
  matched no allow rule, and `dontAsk` denied it. This CLI build has no Glob or Grep tool, so search
  depends on Bash. Both agents therefore worked with Read and Write only: no search, no `node`, no
  git. The condition is stricter than intended, the same in both arms, and arguably a lower bound.
  Discovery followed `AGENTS.md` files and imports, and both agents state that other references may
  exist.
- **Audit coverage:** the path audit checks tool inputs for `/home/michael/…`. It is sufficient here
  only because no Bash command ran. A run with a working shell needs OS-level confinement, because
  Read-deny rules do not constrain `cat`/`grep` in Bash. It also needs a wider audit (`~`, `$HOME`,
  `..`, `/tmp`).
- One session per arm and one codebase. This shows prompt feasibility on Sokol111, not
  portability, comprehension or decision value.
- The question and boundary were supplied. Boundary selection by the agent is not tested.

Observations (interpretation):

- Both agents added migration-relevant items that the reference does not score:
  - both: DLQ topics with unknown readers;
  - P−: one `kafka.brokers` setting per service, so a service cannot be split across two clusters;
  - P−: topic auto-creation (`AllowAutoTopicCreation`);
  - P−: no retry or DLQ settings on image's `catalog-events` consumer;
  - P+: all five services share one broker address;
  - P+: offset-reset replay risk into the S3 cleanup handlers.
- P+ found two places where the source shows more than the provider: `ProductDeleted` is produced and
  handled but not promised, and the provider's producer record for `catalog.attribute.events` lists
  no event types. P+ kept both as gaps and did not change the provider status.
