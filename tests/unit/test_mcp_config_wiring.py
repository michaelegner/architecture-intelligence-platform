"""v0.4.0 I2.1 review fix - proves `create_app()` actually reads `MCPConfig` from the loaded
config.yaml (`app.settings.load_config(CONFIG_PATH).mcp`) rather than silently mounting with
`MCPConfig()`'s bare defaults, which would make a deployment's `mcp.allowed-origins`/`allowed-hosts`
override ineffective despite `docs/security-model.md` documenting it as the way to configure this.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.main

_CUSTOM_ORIGIN = "http://mcp-test.example"
_CUSTOM_HOST = "mcp-test.example"
_DEFAULT_ORIGIN = "http://127.0.0.1:8000"


@pytest.fixture
def app_with_custom_mcp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEO4J_PASSWORD", "unused")
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        textwrap.dedent(f"""\
            architecture_intelligence:
              mcp:
                allowed-origins: ["{_CUSTOM_ORIGIN}"]
                allowed-hosts: ["{_CUSTOM_HOST}"]
            """)
    )
    monkeypatch.setattr(app.main, "CONFIG_PATH", config_path)
    return app.main.create_app()


def _tools_list_request(origin: str) -> dict:
    return {
        "headers": {
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": "2026-07-28",
            "mcp-method": "tools/list",
            "origin": origin,
        },
        "json": {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {
                "_meta": {
                    "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                    "io.modelcontextprotocol/clientCapabilities": {},
                }
            },
        },
    }


def test_configured_origin_is_honored_and_the_default_is_no_longer_allowed(
    app_with_custom_mcp_config,
):
    with TestClient(app_with_custom_mcp_config, base_url=_CUSTOM_ORIGIN) as client:
        allowed = client.post("/mcp", **_tools_list_request(_CUSTOM_ORIGIN))
        assert allowed.status_code == 200

        default_now_rejected = client.post("/mcp", **_tools_list_request(_DEFAULT_ORIGIN))
        assert default_now_rejected.status_code == 403
