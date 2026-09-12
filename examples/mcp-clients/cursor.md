# Cursor — Candidate Setup

**Candidate setup.** Configuration syntax verified against current official documentation.
Interoperability qualification is pending I3 — this is not a "Cursor is supported" claim.

## Verification record

| | |
|---|---|
| Official source | <https://cursor.com/docs/mcp> |
| Verification date | 2026-09-12 |
| Result | PASS — syntax below matches the current official page |

Cursor talks to remote MCP servers over Streamable HTTP or SSE. For a remote/HTTP server, only
`url` is required — no `type` field, unlike a local stdio server (which needs `command`).

## 1. Start AIP

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

## 2. Add a project-local `.cursor/mcp.json`

The repository does **not** commit this file for you — create it yourself so AIP stays opt-in for
your own working copy rather than silently affecting anyone else who opens this project:

```json
{
  "mcpServers": {
    "aip": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Save it as `.cursor/mcp.json` in the repository root. If you'd rather make AIP available in every
Cursor project instead of just this one, put the same block in `~/.cursor/mcp.json` (your home
directory) instead. Cursor loads both files and merges the server lists, so a project-level entry
and a global entry with the same name can coexist without conflict as long as you only define `aip`
in one of them.

## 3. Reload and verify

Reopen the project (or use Cursor's MCP settings panel) so it picks up the new file, then confirm
`aip` appears as a connected server with its three tools listed.

## 4. Ask the stable prompt

Paste the [stable onboarding prompt](README.md#3-ask-the-stable-prompt) into a Cursor chat in this
repository.

## Removing it

Delete the `aip` entry from whichever `mcp.json` you added it to (or delete the whole
`.cursor/mcp.json` file, if AIP was the only server in it), then reload the project.

## No secrets required

AIP's local demo endpoint needs no auth `headers` entry — that field (documented for servers that do
need one) is irrelevant here.
