# VS Code — Candidate Setup

**Candidate setup.** Configuration syntax verified against current official documentation.
Interoperability qualification is pending I3 — this is not a "VS Code is supported" claim.

## Verification record

| | |
|---|---|
| Official source | <https://code.visualstudio.com/docs/agent-customization/mcp-servers> and <https://code.visualstudio.com/docs/agents/reference/mcp-configuration> |
| Verification date | 2026-09-12 |
| Result | PASS — JSON shape below matches the current official reference |

MCP tool support in VS Code's agent mode has been generally available since VS Code **1.102** (July
2025) and requires the **GitHub Copilot Chat** extension. Check `Help > About` for your VS Code
version and the Extensions view for Copilot Chat if `aip`'s tools don't show up after setup.

## 1. Start AIP

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

## 2. Add a workspace `.vscode/mcp.json`

The repository does **not** commit this file for you — create it yourself so AIP stays opt-in for
your own working copy:

```json
{
  "servers": {
    "aip": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Save it as `.vscode/mcp.json` in the repository root. Note the top-level key is `servers`, **not**
`mcpServers` — that's Claude Code/Cursor's key, and using it here silently does nothing in VS Code.

To make AIP available across every workspace instead of just this one, run the **MCP: Open User
Configuration** command from the Command Palette and add the same `aip` block there instead of (or
in addition to) the workspace file.

## 3. Start the server and verify

VS Code shows a `Start` affordance (via CodeLens or the MCP: List Servers command) the first time it
sees a new `mcp.json` entry — use it, then confirm `aip` is connected with its three tools listed
before asking anything.

## 4. Ask the stable prompt

Open Copilot Chat in **agent mode** and paste the
[stable onboarding prompt](README.md#3-ask-the-stable-prompt).

## Removing it

Delete the `aip` entry from `.vscode/mcp.json` (or the user configuration, if you added it there
instead), then stop the server from the MCP: List Servers view if it's still running.

## No secrets required

AIP's local demo endpoint needs no auth `headers` entry — that field (documented for servers that do
need one) is irrelevant here.
