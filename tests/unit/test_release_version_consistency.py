"""v0.4.2 I1 - spec §23, carried forward by v0.5.0 I6 §6 and the v0.5.1 release: package/producer
version metadata SHALL report the current release version (`0.8.0`) consistently.

Every active call site - `pyproject.toml`, `uv.lock`'s root project version, the MCP server's
advertised version, the production-wired `Producer`, and the architecture-answers evaluator's own
synthetic `Producer` - now imports `app.version.package_version()` rather than maintaining its own
literal (PR #120 review finding: the evaluator and its 23 frozen `expected_answer.json` fixtures
had each independently drifted to a stale `0.4.0` while production wiring had already moved to
`0.4.1`, and nothing caught it because both sides of that one comparison agreed on the same wrong
value). This file pins the release version once and asserts every other path traces back to it."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import get_args
from unittest.mock import Mock

from app.architecture_intelligence.bootstrap import build_production_service
from app.architecture_intelligence.contracts import PRODUCER_NAME, Producer
from app.mcp.server import mcp_server
from app.version import package_version
from evaluation.architecture_answers.runner import _build_producer

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RELEASE_VERSION = "0.8.0"


def _uv_lock_root_project_version() -> str:
    with (_REPO_ROOT / "uv.lock").open("rb") as f:
        data = tomllib.load(f)
    [package] = [p for p in data["package"] if p["name"] == "architecture-intelligence-platform"]
    return package["version"]


def test_producer_name_constant_matches_contract_literal():
    assert get_args(Producer.model_fields["name"].annotation) == (PRODUCER_NAME,)


def test_mcp_server_name_agrees_with_producer_name():
    assert mcp_server.name == PRODUCER_NAME


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
    assert service._producer.name == PRODUCER_NAME
    assert service._producer.version == package_version()


def test_architecture_answers_evaluator_producer_version_agrees_with_package_version():
    producer = _build_producer("f" * 40)
    assert producer.name == PRODUCER_NAME
    assert producer.version == package_version()


def test_mcp_registry_server_json_agrees_with_package_version():
    # `server.json` is the MCP Registry entry (metadata only: no packages, no remotes). A registry
    # version is per publish, so it moves with each release (release-publication skill).
    server = json.loads((_REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    assert server["version"] == package_version()
    assert server["name"] == "io.github.michaelegner/architecture-intelligence-platform"
    assert "packages" not in server
    assert "remotes" not in server
    assert server["websiteUrl"].endswith("#connect-aip-to-your-coding-agent")


def test_server_json_website_anchor_points_at_hosted_mcp_demo():
    server = json.loads((_REPO_ROOT / "server.json").read_text(encoding="utf-8"))
    fragment = server["websiteUrl"].rsplit("#", 1)[-1]
    readme = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    anchor = f'<a id="{fragment}"></a>'
    assert f"\n{anchor}\n" in readme
    assert (
        readme.index("\n## Try AIP\n")
        < readme.index(anchor)
        < readme.index("\n### Hosted MCP demo\n")
    )
