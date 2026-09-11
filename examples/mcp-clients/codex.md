# Codex CLI — Candidate Setup

**Candidate setup.** Configuration syntax verified against current official documentation.
Interoperability qualification is pending I3 — this is not a "Codex CLI is supported" claim.

## Verification record

| | |
|---|---|
| Official source | <https://learn.chatgpt.com/docs/extend/mcp?surface=cli> |
| Verification date | 2026-09-12 |
| Result | PASS — syntax below matches the current official page |

The official docs' own guidance for a remote **Streamable HTTP** MCP server (AIP's transport) is to
edit `~/.codex/config.toml` directly rather than a CLI flag, and reserve `codex mcp add ... --env ...
-- <command>` for local **stdio** servers. We follow that guidance here rather than inventing an
unverified `--url` flag some third-party guides describe but the official page does not.

## 1. Start AIP

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

## 2. Add AIP to `~/.codex/config.toml`

```toml
[mcp_servers.aip]
url = "http://localhost:8000/mcp"
```

A trusted project may instead use a project-scoped `.codex/config.toml` in the repository root with
the same `[mcp_servers.aip]` block, if you'd rather not add it to your global config.

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

Delete the `[mcp_servers.aip]` block from `~/.codex/config.toml` (or the project-scoped
`.codex/config.toml`, if that's where you added it).

## No secrets required

AIP's local demo endpoint needs no API key, bearer token, or header — `bearer_token_env_var` and
`http_headers` (documented for servers that do need them) are irrelevant here.
