# Codex CLI — Candidate Setup

**Candidate setup.** Configuration syntax verified against current official documentation.
Interoperability qualification is pending I3 — this is not a "Codex CLI is supported" claim.

## Verification record

| | |
|---|---|
| Official source | <https://learn.chatgpt.com/docs/extend/mcp?surface=cli> |
| Verification date | 2026-09-12 |
| Result | PASS — syntax below matches the current official page and `codex-cli 0.154.0 --help` |

The official docs and the stable `codex mcp add` CLI both document a `--url` flag for registering a
remote **Streamable HTTP** MCP server (AIP's transport) directly from the command line — no manual
`config.toml` edit required. `--env ... -- <command>` remains the flag combination for local **stdio**
servers instead.

## 1. Start AIP

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

## 2. Add AIP with the Codex CLI

```bash
codex mcp add aip --url http://localhost:8000/mcp
```

This registers `aip` in your global `~/.codex/config.toml`. `codex mcp add` always writes to that
global file — if you'd rather scope it to this project instead, add the same block to a project-scoped
`.codex/config.toml` in the repository root by hand:

```toml
[mcp_servers.aip]
url = "http://localhost:8000/mcp"
```

## 3. Verify it's registered

```bash
codex mcp list
```

`aip` should appear in the list, pointed at `http://localhost:8000/mcp`.

## 4. Ask the stable prompt

Start a Codex session in this repository (or any directory — the MCP server is a URL, not tied to a
project) and paste the [stable onboarding prompt](README.md#3-ask-the-stable-prompt). Inside the
session, `/mcp` shows connected servers and their tools if you want to confirm `aip` is live before
asking.

## Removing it

```bash
codex mcp remove aip
```

(Or delete the `[mcp_servers.aip]` block by hand, if you added it by editing `config.toml`.)

## No secrets required

AIP's local demo endpoint needs no API key, bearer token, or header — `bearer_token_env_var` and
`http_headers` (documented for servers that do need them) are irrelevant here.
