"""v0.8 value qualification (spec §4.2, §6.1-§6.2): the Claude Code settings of the four session
types, derived from the v0.8 planning settings.

- F: the v0.8 planning allow list. T: the same list without every `docker`, `kubectl`, `helm`, `rpk`
  and Kafka command, and those command groups denied as a whole.
- `+` allows the `mcp__aip` tools and enables the workspace MCP server; `-` denies them.
- The writable files are the session outputs, by absolute path.
- Read is denied on the AIP worktrees, the operator state, the run package, all clones
  (`RUN_HOME/src`), AIP's inputs (`RUN_HOME/aip`), the request catalogue and every other session.

`template()` builds the frozen template with placeholders; `render()` fills them for one session.
"""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
V08_SETTINGS = HERE.parent / "i4/agent/settings.planning.json"
TYPES = ("F+", "F-", "T+", "T-")
OUTPUTS = ("plan.json", "plan.md", "answers.json")
TEAM_DENIED_PROGRAMS = ("docker", "kubectl", "helm", "rpk", "kafka-", "/opt/kafka/")
TEAM_DENIED_RULES = [
    "Bash(docker:*)",
    "Bash(kubectl:*)",
    "Bash(helm:*)",
    "Bash(rpk:*)",
    "Bash(k3d:*)",
    "Bash(kafka-topics.sh:*)",
    "Bash(kafka-consumer-groups.sh:*)",
]
RUN_HOME_DENIED = ("package", "src", "aip", "catalogue")


def outputs(card_type: str) -> tuple[str, ...]:
    return (*OUTPUTS, "requests.json") if card_type.startswith("T") else OUTPUTS


def template(card_type: str) -> dict:
    if card_type not in TYPES:
        raise ValueError(f"unknown type {card_type}")
    team, with_aip = card_type[0] == "T", card_type[1] == "+"
    settings = json.loads(V08_SETTINGS.read_text())
    allow = []
    for rule in settings["permissions"]["allow"]:
        if rule.startswith("Edit("):
            continue
        if rule == "mcp__aip" and not with_aip:
            continue
        if team and rule.startswith("Bash(") and rule[5:].startswith(TEAM_DENIED_PROGRAMS):
            continue
        allow.append(rule)
    allow += [f"Edit(/__WORKSPACE__/{name})" for name in outputs(card_type)]
    deny = []
    for rule in settings["permissions"]["deny"]:
        if rule == "Read(/__RUN_HOME__/package/**)":
            deny += [f"Read(/__RUN_HOME__/{name}/**)" for name in RUN_HOME_DENIED]
            deny.append("Read(/__OTHER_SESSIONS__/**)")
        elif rule == "Edit(/__RUN_HOME__/claude-*/**)":
            deny.append("Edit(/__CONFIG__/**)")
        else:
            deny.append(rule)
    if not with_aip:
        deny.append("mcp__aip")
    if team:
        deny += TEAM_DENIED_RULES
    settings["permissions"]["allow"] = allow
    settings["permissions"]["deny"] = deny
    settings["enableAllProjectMcpServers"] = with_aip
    return settings


def _expand(rule: str, placeholder: str, values: list[str]) -> list[str]:
    return [rule.replace("/" + placeholder, "/" + value) for value in values]


def render(
    settings: dict,
    *,
    run_home: str,
    workspace: str,
    config: str,
    withheld: list[str],
    operator_state: list[str],
    other_sessions: list[str],
) -> dict:
    """The template for one session. A directory of the operator state is denied with everything
    under it; the paths are absolute (`//path`), as in v0.8."""
    state = [p if p.endswith(".json") else p + "/**" for p in operator_state]
    rendered = json.loads(json.dumps(settings))
    for kind in ("allow", "deny"):
        rules = []
        for rule in settings["permissions"][kind]:
            if "__AIP_CHECKOUT__" in rule:
                rules += _expand(rule, "__AIP_CHECKOUT__", withheld)
            elif "__OPERATOR_STATE__" in rule:
                rules += _expand(rule, "__OPERATOR_STATE__", state)
            elif "__OTHER_SESSIONS__" in rule:
                rules += _expand(rule, "__OTHER_SESSIONS__", other_sessions)
            else:
                rules.append(
                    rule.replace("/__RUN_HOME__", "/" + run_home)
                    .replace("/__WORKSPACE__", "/" + workspace)
                    .replace("/__CONFIG__", "/" + config)
                )
        rendered["permissions"][kind] = rules
    rules = rendered["permissions"]["allow"] + rendered["permissions"]["deny"]
    leftover = [r for r in rules if "/__" in r]
    if leftover:
        raise ValueError(f"unfilled placeholders: {leftover}")
    return rendered
