# MCP `2025-11-25` results of v0.8.0

v0.8.1 I1 (spec D8) proves that the `2025-11-25` path is unchanged from v0.8.0. These files hold
the `initialize`, `resources/list`, `resources/templates/list` and `tools/list` results of the
`v0.8.0` tag, flag off and flag on (`experimental.binding-picture`).

They were captured once from a detached `v0.8.0` worktree. The capture sent the same requests that
`tests/unit/test_mcp_skills.py` sends, through `build_mcp_app(server=build_mcp_server(...))` and the
real ASGI transport. Do not regenerate them from a later version: they are the v0.8.0 baseline.
The test replaces only `serverInfo.version` with the current package version.
