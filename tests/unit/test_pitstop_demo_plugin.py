"""v0.6.2 I1b-1: the Pitstop demo's Claude Code plugin (spec §6.1, §2).

The plugin is example client material: it adds no AIP behaviour and its removal changes no answer. These
tests guard its static contract without a network or a `claude` binary:
- the manifest and `.mcp.json` name the plugin `aip` and the MCP URL `run.sh` prints;
- both skills grant exactly the three read-only AIP tools, under the names Claude Code gives a plugin's MCP
  tools (`mcp__plugin_aip_aip__<tool>`), each of which AIP really registers;
- the service-id table is the overlay's, row for row;
- the skill text carries the §6.1 workflow and boundaries, and never asserts field usage, per-queue
  qualification or completeness.
`claude plugin validate --strict` (a real check, run by hand) is the authoritative structural check.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
PLUGIN = DEMO_DIR / "claude" / "plugin"
DEVELOPMENT = PLUGIN / "skills" / "architecture-aware-development" / "SKILL.md"
INSPECT = PLUGIN / "skills" / "inspect" / "SKILL.md"
TOOL_PREFIX = "mcp__plugin_aip_aip__"
READ_ONLY = {"get_service_dependencies", "get_evidence", "get_architecture_drift"}
FORBIDDEN_TOOLS = (
    "Bash",
    "Write",
    "Edit",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
    "Agent",
)


def _skill(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.DOTALL)
    assert match, f"{path} has no frontmatter"
    return yaml.safe_load(match.group(1)), match.group(2)


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _registered_tools() -> set[str]:
    source = (REPO / "app" / "mcp" / "tools.py").read_text()
    return set(re.findall(r'@server\.tool\(\s*name="(\w+)"', source))


def _overlay_services() -> dict[str, tuple[str, str]]:
    """title -> (service id, role)."""
    services = {}
    for path in sorted((DEMO_DIR / "overlay").glob("*/asyncapi.yaml")):
        document = yaml.safe_load(path.read_text())
        channel = document["channels"]["Pitstop"]
        role = (
            "publishes"
            if "publish" in channel
            else f"receives via queue `{channel['subscribe']['x-aip-subscription-name']}`"
        )
        services[document["info"]["title"]] = (document["x-aip-service-id"], role)
    return services


def _table_rows(body: str) -> dict[str, tuple[str, str]]:
    rows = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[1].startswith("`service:"):
            rows[cells[0]] = (cells[1].strip("`"), cells[2])
    return rows


def test_manifest_names_the_plugin_aip_and_the_url_run_sh_prints():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == "aip"
    assert re.fullmatch(r"[a-z][a-z0-9-]*", manifest["name"])
    assert set(manifest) <= {"name", "version", "description", "author", "license", "userConfig"}
    [(key, option)] = manifest["userConfig"].items()
    assert key == "aip_mcp_url"
    assert set(option) == {"type", "title", "description", "default"}
    run_sh = (DEMO_DIR / "run.sh").read_text()
    [aip_url] = re.findall(r'^AIP_URL="([^"]+)"', run_sh, re.MULTILINE)
    assert option["default"] == f"{aip_url}/mcp"

    # Spike 2026-10-08: `claude plugin configure` cannot target a `--plugin-dir` plugin, so no plugin setting (and no
    # sensitive `userConfig` token) can be set for it. The only userConfig option stays the URL (asserted by the
    # single-entry unpack above, with its localhost default); the hosted instance is reached through two environment
    # variables: AIP_MCP_URL overrides the URL, AIP_MCP_TOKEN is the bearer token. Unset, the localhost demo is unchanged.
    servers = json.loads((PLUGIN / ".mcp.json").read_text())["mcpServers"]
    assert servers == {
        "aip": {
            "type": "http",
            "url": "${AIP_MCP_URL:-${user_config.aip_mcp_url}}",
            "headers": {"Authorization": "Bearer ${AIP_MCP_TOKEN:-}"},
        }
    }


def test_no_plugin_file_holds_a_token_value():
    """The bearer token is a variable reference only: nothing secret-looking is committed in the plugin."""
    for path in PLUGIN.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        for match in re.finditer(r"Bearer\s+(\S+)", text):
            assert match.group(1).rstrip('",') == "${AIP_MCP_TOKEN:-}", (path.name, match.group(0))
        assert not re.search(r"[0-9a-f]{32,}", text), path.name


def test_both_skills_grant_exactly_the_three_read_only_aip_tools_and_nothing_else():
    registered = _registered_tools()
    assert READ_ONLY <= registered
    for path in (DEVELOPMENT, INSPECT):
        frontmatter, _body = _skill(path)
        granted = frontmatter["allowed-tools"].split()
        assert set(granted) == {TOOL_PREFIX + name for name in READ_ONLY}, path
        assert not [t for t in granted if t.startswith(FORBIDDEN_TOOLS)], path
        # `allowed-tools` only pre-approves; the read-only guarantee is `disallowed-tools`, which removes
        # the action-capable tools from the pool while the skill runs, and leaves repository read/search
        # tools (Read, Grep, Glob) available for finding the publisher and comparing documents
        removed = set(frontmatter["disallowed-tools"].split())
        assert removed >= {"Bash", "Write", "Edit", "NotebookEdit"}, path
        assert not removed & set(granted), path
        assert not removed & {"Read", "Grep", "Glob"}, path
        assert all(t.removeprefix(TOOL_PREFIX) in registered for t in granted), path


def test_the_skills_have_the_names_and_invocation_the_spec_requires():
    development, _ = _skill(DEVELOPMENT)
    assert development["name"] == "architecture-aware-development"
    assert development["description"].startswith("Use when")
    assert "disable-model-invocation" not in development  # Claude may choose it for matching tasks
    inspect, body = _skill(INSPECT)
    assert inspect["name"] == "inspect"  # /aip:inspect under the plugin name `aip`
    assert inspect["disable-model-invocation"] is True
    assert inspect["argument-hint"]
    assert "$ARGUMENTS" in body


def test_service_id_table_is_the_overlays_row_for_row_in_both_skills():
    expected = _overlay_services()
    assert len(expected) == 9
    for path in (DEVELOPMENT, INSPECT):
        assert _table_rows(_skill(path)[1]) == expected, path


def test_development_skill_carries_the_spec_workflow_and_boundaries():
    _frontmatter, body = _skill(DEVELOPMENT)
    text = _normalized(body)
    for required in (
        "through the publishing service",
        "no receiver-side question",
        "`RESOLVED_SERVICE`",
        "**per messaging destination**",
        "**never per event type**",
        "publisher's** qualification",
        "no per-queue qualification",
        "no payload or field-level knowledge",
        "Never invent an environment or a window",
        "whole UTC days wholly in the past",
        "own `snapshot_id`",
        "`SNAPSHOT_NOT_AVAILABLE`",
        "**same** context",
        "at most three attempts",
        "report the drill-down as failed",
        "Read the route evidence from the claim's `resolution_evidence_refs`",
        "are the **publisher's** and say nothing about the receiver",
        "## Evidence (AIP)",
        "Route has observed evidence",
        "`NOT_ANSWERED`",
        "as **unknowns**, never as risks resolved",
        '"inspect the consumer"',
        "your reading of the documents",
        "not as an AIP drift claim",
        '"unobserved" never means "unused"',
        "Do not claim that the change is safe, or that AIP identified the breaking consumers",
        "It never edits files, runs commands or changes AIP",
    ):
        assert required in text, required


def test_inspect_skill_prints_the_table_and_the_boundary_and_never_acts():
    _frontmatter, body = _skill(INSPECT)
    text = _normalized(body)
    for required in (
        "Read-only: never edit files or run commands",
        "one row per dependency claim",
        "carries observed evidence (read it from `resolution_evidence_refs`",
        "say nothing about the receiver",
        "evidence reference ids",
        "every limitation verbatim",
        "never per event type",
        "no payload or field-level knowledge",
        "Drill-down on request only",
        "at most three attempts",
        "never invent them",
    ):
        assert required in text, required


def test_no_skill_asserts_field_usage_per_queue_qualification_or_completeness():
    for path in (DEVELOPMENT, INSPECT):
        text = _normalized(_skill(path)[1]).lower()
        for forbidden in (
            "starttime",
            "endtime",
            "duration",
            "maintenancejobfinished",
            "all consumers are known",
            "complete list",
            "per-queue qualification is",
            "reads the field",
        ):
            assert forbidden not in text, (path.name, forbidden)


def test_readme_documents_how_to_load_the_plugin():
    readme = (DEMO_DIR / "README.md").read_text()
    assert "claude --plugin-dir examples/pitstop-demo/claude/plugin" in readme
    assert "/aip:inspect" in readme
    assert "plugin:aip:aip" in readme
    assert "export AIP_MCP_URL=" in readme
    assert "export AIP_MCP_TOKEN=" in readme
    # a standalone server with the same URL makes Claude Code suppress the plugin's server (spike 2026-10-08)
    assert "standalone `aip` MCP server" in readme
    assert "suppresses" in readme
