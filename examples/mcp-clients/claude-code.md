# Claude Code — Candidate Setup

**Candidate setup.** Configuration syntax verified against current official documentation.
Interoperability qualification is pending I3 — this is not a "Claude Code is supported" claim.

## Verification record

| | |
|---|---|
| Official source | <https://code.claude.com/docs/en/mcp> |
| Verification date | 2026-09-12 |
| Result | PASS — syntax below matches the current official page |

## 1. Start AIP

```bash
examples/runtime-demo/mcp-demo.sh --serve
```

## 2. Add AIP with `--scope local`

```bash
claude mcp add --transport http --scope local aip http://localhost:8000/mcp
```

`local` is the default scope, private to you and this project — it is **not** committed to version
control or shared with anyone else who opens the repository. This is the preferred first-run scope:
> **The first AIP onboarding should be local/private unless the user explicitly wants a shared
> project configuration.**

If you'd rather share AIP with everyone who opens this project (writes a committed `.mcp.json` at
the repository root), use `--scope project` instead:

```bash
claude mcp add --transport http --scope project aip http://localhost:8000/mcp
```

## Scope reference

| Scope | Visible to | Shared/committed | Stored in |
|---|---|---|---|
| `local` (default) | this project only | No | `~/.claude.json`, under this project's path |
| `project` | this project only | Yes, via version control | `.mcp.json` in the repository root |
| `user` | every project on this machine | No | `~/.claude.json`, top level |

## 3. Verify it's registered

```bash
claude mcp list
claude mcp get aip
```

## 4. Ask the stable prompt

Paste the [stable onboarding prompt](README.md#3-ask-the-stable-prompt) into a Claude Code session
in this repository.

## Removing it

```bash
claude mcp remove aip
```

Add `--scope project` (or `user`) if you added it under a non-default scope, so the removal targets
the same scope it was added under.

## No secrets required

AIP's local demo endpoint needs no auth header — `--header "Authorization: Bearer ..."` (documented
for servers that do need one) is irrelevant here.
