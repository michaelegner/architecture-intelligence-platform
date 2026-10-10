"""The repository's Claude Code marketplace (`.claude-plugin/marketplace.json`): example client material.

CI has no Claude Code CLI, so `claude plugin validate .` and an install are run by hand (the README says so). What is
checked here is what can be: the file's shape, that each entry resolves to the plugin or mod it names, that sources
stay inside the repository, and that nothing secret-looking is committed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
CLAUDE = REPO / "examples" / "pitstop-demo" / "claude"
DATA = json.loads(MARKETPLACE.read_text())

# Names Claude Code refuses or reserves for official marketplaces (marketplace reference, "Reserved names").
RESERVED = {
    "claude-code-marketplace",
    "claude-code-plugins",
    "claude-plugins-official",
    "anthropic-marketplace",
    "anthropic-plugins",
    "agent-skills",
    "anthropic-agent-skills",
    "life-sciences",
    "knowledge-work-plugins",
    "claude-for-legal",
    "claude-for-financial-services",
    "financial-services-plugins",
    "first-party-plugins",
    "claude-tag-plugins",
    "claude-community",
    "claude-plugins-community",
    "healthcare",
    "anthropic-plugin-directory",
    "claude-plugin-directory",
    "inline",
    "builtin",
    "skills-dir",
    "synced",
    "claude-plugin-test",
    "npm",
    "pip",
    "uv",
    "cargo",
    "github",
    "gh",
}
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def test_marketplace_has_the_required_fields_and_a_valid_unreserved_name():
    assert set(DATA) <= {"name", "description", "owner", "plugins"}
    assert NAME.fullmatch(DATA["name"]) and ".." not in DATA["name"]
    assert (
        DATA["name"] == "aip-plugins"
    )  # install ids are aip@aip-plugins: permanent once users install
    assert DATA["name"].lower() not in RESERVED
    assert not DATA["name"].lower().startswith("claudeai-")
    assert not re.search(r"official|anthropic", DATA["name"], re.IGNORECASE)
    assert DATA["owner"]["name"]
    assert DATA["description"]


def test_each_entry_resolves_to_the_plugin_it_names_and_stays_inside_the_repository():
    expected = {
        "aip": CLAUDE / "plugin",
        "aip-mod": CLAUDE / "mod",
    }
    entries = {entry["name"]: entry for entry in DATA["plugins"]}
    assert set(entries) == set(expected)
    assert len(entries) == len(DATA["plugins"])  # no duplicate names
    for name, entry in entries.items():
        assert NAME.fullmatch(name)
        source = entry["source"]
        assert isinstance(source, str) and source.startswith("./")
        assert ".." not in source and "\\" not in source
        resolved = (REPO / source).resolve()
        assert resolved == expected[name].resolve(), name
        manifest = json.loads((resolved / ".claude-plugin" / "plugin.json").read_text())
        # The entry name is the install id; Claude Code looks the plugin up by it, so it must equal the manifest name.
        assert manifest["name"] == name
        # The version belongs to plugin.json (an entry version that disagrees only warns, so keep one source).
        assert "version" not in entry
        assert entry["description"]


def test_the_marketplace_file_holds_no_token_or_hostname():
    text = MARKETPLACE.read_text()
    assert "Bearer" not in text
    assert not re.search(r"[0-9a-f]{32,}", text)
    assert not re.search(r"sslip\.io|https?://\d", text)
