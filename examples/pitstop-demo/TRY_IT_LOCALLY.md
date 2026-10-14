# Try the Pitstop demo locally

This is the shortest path to try AIP with a coding agent on a realistic distributed-system change.

You will ask the agent to change the `MaintenanceJobFinished` event. AIP supplies evidence-qualified
architecture context; the agent then inspects the code for what AIP does not know.

## 1. Start the local demo

Prerequisites: Docker with Compose v2, Git and `curl`. No AIP credentials or LLM API key are needed.

```bash
git clone https://github.com/michaelegner/architecture-intelligence-platform.git
cd architecture-intelligence-platform
examples/pitstop-demo/run.sh
```

The script starts AIP locally, loads the demo evidence, replays the frozen observation window and writes
the ready-to-copy task to:

```text
.aip-pitstop-demo/prompt.txt
```

## 2. Install the Claude Code integration

The `aip` plugin includes the `architecture-aware-development` skill. The optional `aip-mod` shows
AIP's evidence beside the agent's plan.

```bash
claude plugin marketplace add michaelegner/architecture-intelligence-platform
claude plugin install aip@aip-plugins
claude plugin install aip-mod@aip-plugins   # optional
```

The local plugin endpoint defaults to `http://localhost:8000/mcp`; no token is required.

## 3. Give the agent the Pitstop source

In another directory:

```bash
git clone https://github.com/EdwinVW/pitstop.git
cd pitstop
git checkout 306b5fbd0febceb6b0d0706f152a0520ca1a993a
claude
```

Run `/mcp` and check that `plugin:aip:aip` is connected. Then paste the prompt generated in
`.aip-pitstop-demo/prompt.txt`.

The main task asks the agent to replace `StartTime` and `EndTime` in `MaintenanceJobFinished`
with `Duration` and plan the change.

## 4. Continue the conversation

Useful follow-up questions:

- Why is `ReportingService` relevant?
- Does AIP establish that `ReportingService` consumes `MaintenanceJobFinished` specifically?
- Which receivers use `StartTime` or `EndTime`?
- What evidence supports the distributed relationships in the plan?
- What is established by AIP, what comes from code inspection, and what remains unresolved?

The important behavior is that AIP helps establish **where to inspect** without pretending to know
what only source inspection can establish.

## Stop the demo

From the AIP repository:

```bash
examples/pitstop-demo/run.sh --down
```

For the hosted path, see [Try the Pitstop demo hosted](TRY_IT_HOSTED.md). For expected answers,
provenance and live-mode details, see the [Pitstop demo README](README.md) and the
[walkthrough](walkthrough.md).
