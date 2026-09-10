"""v0.4.1 I3.2 - spec §20: "package/producer version metadata SHALL report `0.4.1` consistently,"
naming `pyproject.toml`, the MCP server's advertised version, and `ArchitectureAnswer.producer.
version` as the active call sites that must agree. Nothing previously asserted this - each was an
independently hand-maintained literal, and I1/I2 already let one test drift to `"0.4.1"` ahead of
the real release bump before this file existed."""

from __future__ import annotations

import tomllib
from pathlib import Path

from app.mcp.server import mcp_server
from app.mcp.wiring import build_production_service

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _pyproject_version() -> str:
    with (_REPO_ROOT / "pyproject.toml").open("rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def test_pyproject_toml_reports_the_current_release_version():
    assert _pyproject_version() == "0.4.1"


def test_mcp_server_advertised_version_agrees_with_pyproject_toml():
    assert mcp_server.version == _pyproject_version()


def test_production_wired_producer_version_agrees_with_pyproject_toml():
    # driver=None is safe here: ArchitectureIntelligenceService.__init__ only stores the driver
    # reference, and this test never dispatches a call that would use it.
    service = build_production_service(None, database="neo4j")
    assert service._producer.version == _pyproject_version()
