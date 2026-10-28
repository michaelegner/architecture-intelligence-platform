"""v0.8 I4a: the agent's environment (I4 spec §4.1, §4.2, §5).

The Kafka-only Compose file has no MirrorMaker 2 and the I3 Kafka image; AIP is reached over HTTP;
the session settings deny the AIP checkout, the config dirs and the web; the workspace setup refuses
a run home inside an AIP worktree, refuses a used config dir, and writes the settings into the config
dir with every worktree denied.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
I4 = REPO / "harness/v08/i4"
I3_COMPOSE = REPO / "docs/specifications/0.8.0/i3-evidence/environment/docker-compose.i3.yml"


def test_kafka_compose_is_kafka_only_with_the_i3_image():
    compose = yaml.safe_load((I4 / "environment/docker-compose.kafka.yml").read_text())
    i3 = yaml.safe_load(I3_COMPOSE.read_text())
    assert list(compose["services"]) == ["kafka"]
    kafka = compose["services"]["kafka"]
    assert kafka["image"] == i3["services"]["kafka"]["image"]
    assert kafka["container_name"] == "kafka"
    assert compose["name"] == "aip-v08-i4"
    for key in ("KAFKA_LISTENERS", "KAFKA_ADVERTISED_LISTENERS", "KAFKA_AUTO_CREATE_TOPICS_ENABLE"):
        assert kafka["environment"][key] == i3["services"]["kafka"]["environment"][key]


def test_mcp_is_http_not_a_launch_command():
    server = json.loads((I4 / "agent/mcp.json").read_text())["mcpServers"]["aip"]
    assert server["type"] == "http" and server["url"].startswith("http://127.0.0.1:8000/")
    assert "command" not in server


@pytest.mark.parametrize("session", ["planning", "execution"])
def test_session_settings_deny_the_withheld(session):
    permissions = json.loads((I4 / f"agent/settings.{session}.json").read_text())["permissions"]
    assert permissions["defaultMode"] == "dontAsk"
    deny = permissions["deny"]
    for rule in (
        "Read(/__AIP_CHECKOUT__/**)",
        "Edit(/__AIP_CHECKOUT__/**)",
        "Edit(//**/.claude/**)",
        "WebFetch",
        "WebSearch",
    ):
        assert rule in deny
    assert not any(
        rule.startswith("Write(") for rule in deny + permissions["allow"]
    )  # Edit covers it


@pytest.mark.parametrize("session", ["planning", "execution"])
def test_session_settings_deny_operator_state_and_the_package(session):
    settings = json.loads((I4 / f"agent/settings.{session}.json").read_text())
    assert settings["autoMemoryEnabled"] is False
    assert {"Read(/__OPERATOR_STATE__)", "Read(/__RUN_HOME__/package/**)"} <= set(
        settings["permissions"]["deny"]
    )


def test_planning_writes_only_the_plan():
    allow = json.loads((I4 / "agent/settings.planning.json").read_text())["permissions"]["allow"]
    assert [r for r in allow if r.startswith("Edit")] == ["Edit(./plan.json)", "Edit(./plan.md)"]
    assert "Bash" not in allow and all(not r.startswith("Bash(docker rm") for r in allow)


def test_execution_cannot_touch_the_frozen_plan_or_the_planning_session():
    deny = json.loads((I4 / "agent/settings.execution.json").read_text())["permissions"]["deny"]
    assert {
        "Edit(./plan.json)",
        "Edit(./plan.md)",
        "Read(/__RUN_HOME__/claude-planning/**)",
    } <= set(deny)


def setup(run_home: Path, session: str, home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(home)}
    return subprocess.run(
        ["bash", str(I4 / "setup_workspace.sh"), str(run_home), session],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_setup_refuses_a_run_home_inside_a_worktree(tmp_path):
    result = setup(I4, "planning", tmp_path)
    assert result.returncode == 2 and "inside the AIP worktree" in result.stderr


def test_setup_planning_then_execution(tmp_path):
    run_home = tmp_path / "run"
    (run_home / "src/ecommerce-workspace").mkdir(parents=True)
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude/.credentials.json").write_text("{}")
    (home / ".claude/CLAUDE.md").write_text("operator memory")

    result = setup(run_home, "planning", home)
    assert result.returncode == 0, result.stderr
    workspace = run_home / "workspace"
    assert (workspace / "TASK.md").read_bytes() == (
        REPO / "docs/specifications/0.8.0/i4-evidence/task-card.md"
    ).read_bytes()
    assert json.loads((workspace / "plan.schema.json").read_text())["required"] == [
        "items",
        "allow_lists",
    ]
    config = run_home / "claude-planning"
    assert sorted(p.name for p in config.iterdir()) == [".credentials.json", "settings.json"]
    deny = json.loads((config / "settings.json").read_text())["permissions"]["deny"]
    assert f"Read(/{REPO})" in {rule.removesuffix("/**)") + ")" for rule in deny}
    assert not any("__" in rule for rule in deny)
    assert f"Read(/{home}/.claude/**)" in deny and f"Read(/{home}/.claude.json)" in deny
    slug = str(REPO).replace("/", "-")
    assert any(rule.startswith("Read(//tmp/claude-") and slug in rule for rule in deny)
    assert f"Read(/{run_home.resolve()}/package/**)" in deny
    assert "CLAUDE_CODE_DISABLE_AUTO_MEMORY=1" in result.stdout

    again = setup(run_home, "planning", home)
    assert again.returncode == 2 and "already exists" in again.stderr

    early = setup(run_home, "execution", home)
    assert early.returncode == 2 and "frozen plan is missing" in early.stderr
    (workspace / "plan.json").write_text("{}")
    (workspace / "plan.md").write_text("x")
    (run_home / "plan-freeze.txt").write_text("digests")
    assert setup(run_home, "execution", home).returncode == 0
    execution = json.loads((run_home / "claude-execution/settings.json").read_text())
    assert f"Read(/{run_home.resolve()}/claude-planning/**)" in execution["permissions"]["deny"]
