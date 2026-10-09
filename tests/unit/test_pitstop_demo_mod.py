"""v0.6.2 optional mod (spec §6.2): static checks of `examples/pitstop-demo/claude/mod/`.

The mod is example client material: it shows the last AIP answer beside the agent's plan and only reads the
result of the plugin's AIP tools. CI has no Claude Code CLI, so its behaviour is checked by hand
(`claude plugin validate` / `claude plugin test`, the README says so). What is checked here is what can be:

- the manifest, the hooks file and the files the spec lists;
- the mod never touches a prompt (`prompt.submit`, `prompt.compose`) or calls a model, and it hooks exactly the
  plugin's own tools (a RegExp matching the real `mcp__plugin_aip_aip__*` names, not the glob the spec used to say);
- every field name its pure reader accesses is a property of the released v0.6 answer schema;
- nothing secret-looking is committed in it, and the README documents it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO / "examples" / "pitstop-demo"
MOD = DEMO_DIR / "claude" / "mod"
REGISTER = (MOD / "hooks" / "register.tsx").read_text()
LOGIC = (MOD / "hooks" / "logic.ts").read_text()
SCHEMA = REPO / "schemas" / "architecture_intelligence" / "v0.6" / "architecture-answer.schema.json"

# The plugin's real tool prefix (the plugin test pins it against the skills and the registered tools).
TOOL_PREFIX = "mcp__plugin_aip_aip__"
# Property accesses in logic.ts that are the language's, not the answer's.
LANGUAGE = {"parse", "filter", "map", "some", "startsWith", "length"}


def _schema_property_names() -> set[str]:
    names: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            properties = node.get("properties")
            if isinstance(properties, dict):
                names.update(properties)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(SCHEMA.read_text()))
    return names


def test_the_mod_has_the_files_the_spec_lists():
    for relative in (
        ".claude-plugin/plugin.json",
        "hooks/hooks.json",
        "hooks/register.tsx",
        "hooks/logic.ts",
        "hooks/pane.test.ts",
        "types/index.d.ts",
    ):
        assert (MOD / relative).is_file(), relative


def test_manifest_and_hooks_file_name_the_mod_and_its_module():
    manifest = json.loads((MOD / ".claude-plugin" / "plugin.json").read_text())
    # `aip-mod` also owns the mod's state values: the module's atoms name it and a mismatch is refused by the engine.
    assert manifest["name"] == "aip-mod"
    assert manifest["types"] == "./types/index.d.ts"
    assert set(manifest) <= {"name", "version", "description", "author", "license", "types"}
    assert "userConfig" not in manifest
    assert json.loads((MOD / "hooks" / "hooks.json").read_text()) == {"modules": ["./register.tsx"]}
    assert "plugin: 'aip-mod'" in REGISTER
    assert "'aip-mod'" in (MOD / "types" / "index.d.ts").read_text()


def test_the_mod_never_touches_a_prompt_or_calls_a_model():
    """The relevance judge was measured and dropped (spec §6.2): the mod only reads tool results."""
    code = "\n".join(line for line in REGISTER.splitlines() if not line.lstrip().startswith("//"))
    for forbidden in (
        "prompt.submit",
        "prompt.compose",
        "model.complete",
        "$.model",
        "skill.prompt",
        "ui.status",
        "ui.toast",
    ):
        assert forbidden not in code, forbidden


def test_it_hooks_exactly_the_plugins_aip_tools_with_a_regexp_and_fails_open():
    [matcher] = re.findall(r"on\('tool\.call', \{ tool: /(.+?)/ \}", REGISTER)
    assert re.search(matcher, f"{TOOL_PREFIX}get_service_dependencies")
    assert re.search(matcher, f"{TOOL_PREFIX}get_evidence")
    assert not re.search(matcher, "mcp__aip__get_service_dependencies")
    assert not re.search(matcher, "mcp__memtrace__find_code")
    assert "mcp__aip__*" not in REGISTER
    # A hook that throws must leave the call as it would be without the mod.
    assert ".catch(($, e, next) => next(e))" in REGISTER
    # It returns the result it got, unchanged.
    assert re.search(r"return ran\b", REGISTER)


def test_the_pane_opens_only_on_the_persons_own_action():
    assert "command: 'aip-evidence'" in REGISTER
    assert "name: 'aip-evidence'" in REGISTER
    assert 'label="Evidence"' in REGISTER
    assert (
        REGISTER.count("$.ui.open(") == 2
    )  # the command and the button, nothing triggered by a hook


def test_the_reader_accesses_only_fields_of_the_released_v0_6_answer_schema():
    accessed = set(re.findall(r"\??\.([A-Za-z_]+)", LOGIC))
    accessed -= LANGUAGE
    # `.catch`-style language members and the helper's own names are not answer fields.
    unknown = accessed - _schema_property_names()
    assert not unknown, f"fields not in the v0.6 answer schema: {sorted(unknown)}"
    # And it reads the ones the pane shows.
    for field in (
        "outcome",
        "tool",
        "snapshot_id",
        "limitations",
        "qualification",
        "coverage",
        "resolution_evidence_refs",
    ):
        assert field in accessed, field


def test_no_mod_file_holds_a_token_value():
    for path in MOD.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text()
        assert "Bearer" not in text, path.name
        assert not re.search(r"[0-9a-f]{32,}", text), path.name


def test_the_readme_documents_the_mod_and_how_to_load_both_plugins():
    readme = (DEMO_DIR / "README.md").read_text()
    assert (
        "claude --plugin-dir examples/pitstop-demo/claude " in readme
        or "claude --plugin-dir examples/pitstop-demo/claude\n" in readme
    )
    for needed in (
        "/aip-evidence",
        "Evidence",
        "144",
        "claude plugin validate",
        "claude plugin test",
        "2.1.29",
    ):
        assert needed in readme, needed
