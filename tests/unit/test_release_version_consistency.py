"""v0.4.1 I3.2 - spec §20: package/producer version metadata SHALL report `0.4.1` consistently.

Every active call site - `pyproject.toml`, `uv.lock`'s root project version, the MCP server's
advertised version, the production-wired `Producer`, and the architecture-answers evaluator's own
synthetic `Producer` - now imports `app.version.package_version()` rather than maintaining its own
literal (PR #120 review finding: the evaluator and its 23 frozen `expected_answer.json` fixtures
had each independently drifted to a stale `0.4.0` while production wiring had already moved to
`0.4.1`, and nothing caught it because both sides of that one comparison agreed on the same wrong
value). This file pins the release version once and asserts every other path traces back to it."""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import Mock

from app.mcp.server import mcp_server
from app.mcp.wiring import build_production_service
from app.version import package_version
from evaluation.architecture_answers.runner import _build_producer

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RELEASE_VERSION = "0.4.1"


def _uv_lock_root_project_version() -> str:
    with (_REPO_ROOT / "uv.lock").open("rb") as f:
        data = tomllib.load(f)
    [package] = [p for p in data["package"] if p["name"] == "architecture-intelligence-platform"]
    return package["version"]


def test_package_version_reports_the_current_release_version():
    assert package_version() == _RELEASE_VERSION


def test_uv_lock_root_project_version_agrees_with_package_version():
    assert _uv_lock_root_project_version() == package_version()


def test_mcp_server_advertised_version_agrees_with_package_version():
    assert mcp_server.version == package_version()


def test_production_wired_producer_version_agrees_with_package_version(monkeypatch):
    # AIP_BUILD_REVISION is set explicitly so this test never shells out to `git rev-parse HEAD`
    # (Copilot review finding on PR #120: the git fallback is environment-dependent and can be
    # slow/noisy where git or .git isn't available) - build_revision's own value isn't what this
    # test is about. A Mock driver is safe: ArchitectureIntelligenceService.__init__ only stores it,
    # never touches it, before this test's one assertion.
    monkeypatch.setenv("AIP_BUILD_REVISION", "f" * 40)
    service = build_production_service(Mock(), database="neo4j")
    assert service._producer.version == package_version()


def test_architecture_answers_evaluator_producer_version_agrees_with_package_version():
    producer = _build_producer("f" * 40)
    assert producer.version == package_version()
