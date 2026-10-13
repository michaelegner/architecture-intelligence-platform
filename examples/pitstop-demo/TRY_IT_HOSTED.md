# Try the Pitstop demo hosted

This is the shortest path to try the live Pitstop demo with Claude Code. Nothing from AIP needs to run
on your machine, and the public demo requires no credentials.

You need:

- Git
- Claude Code 2.1.292 or later
- the published public Pitstop demo MCP URL

## 1. Clone Pitstop

The agent reads the upstream source while it plans the change:

```bash
git clone https://github.com/EdwinVW/pitstop.git
cd pitstop
git checkout 306b5fbd0febceb6b0d0706f152a0520ca1a993a
```

`ReportingService` is not in this upstream repository. AIP still resolves it as a receiver from
architecture and runtime evidence; that contrast is part of the demo.

## 2. Install the Claude Code integration

The `aip` plugin includes the `architecture-aware-development` skill. The optional `aip-mod` shows
AIP's evidence beside the agent's plan.

```bash
claude plugin marketplace add michaelegner/architecture-intelligence-platform
claude plugin install aip@aip-plugins
claude plugin install aip-mod@aip-plugins   # optional
```

## 3. Configure the public endpoint

Start Claude Code and run:

```text
/plugin configure aip@aip-plugins
```

Set `aip_mcp_url` to the published public demo MCP URL and leave `aip_token` empty, then restart
Claude Code.

If a standalone `aip` MCP server points at the same URL, remove it first:

```bash
claude mcp remove aip
```

Otherwise Claude Code can hide the plugin's MCP server as a duplicate.

The public demo exposes only the read-only MCP surface; ingestion, imports and other AIP application
routes are intentionally not public.

## 4. Check the connection

Start Claude Code in the Pitstop folder:

```bash
claude
```

Run `/mcp`. `plugin:aip:aip` should be connected with four tools.

## 5. Ask the main question

Use a **completed UTC day**: yesterday, from `T00:00:00Z` through `T23:59:59Z`.

```text
In the Pitstop service WorkshopManagementAPI, replace the StartTime and EndTime fields of the MaintenanceJobFinished event with a single Duration field: the workshop only needs to report how long a job took. Plan the change. Use environment pitstop-demo and the window <YYYY-MM-DD>T00:00:00Z to <YYYY-MM-DD>T23:59:59Z
```

Replace `<YYYY-MM-DD>` with yesterday's UTC date.

The agent should use the AIP skill, include an **Evidence** section in its plan, identify the five receivers
AIP resolves, and keep AIP evidence separate from what it learns by reading source code.

## Continue the conversation

Useful follow-up questions:

- Why is `ReportingService` relevant?
- Does AIP establish that `ReportingService` consumes `MaintenanceJobFinished` specifically?
- Which receivers use `StartTime` or `EndTime`?
- What evidence supports the distributed relationships in the plan?
- What is established by AIP, what comes from code inspection, and what remains unresolved?

With `aip-mod` installed, the status line shows the current AIP result and the **Evidence** button
(or `/aip-evidence`) opens the evidence pane.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `/mcp` cannot connect | check that `aip_mcp_url` is the published public MCP URL, then restart Claude Code |
| `421 Invalid Host header` | use the exact published public MCP URL |
| no `plugin:aip:aip` in `/mcp` | restart after configuration, and remove any standalone `aip` server for the same URL |
| `429 Too Many Requests` | the public demo rate limit was reached; wait briefly and retry |
| the agent says the window is not over | use yesterday in UTC, not today |

For expected answers and provenance, see the [Pitstop demo README](README.md) and
[walkthrough](walkthrough.md).
