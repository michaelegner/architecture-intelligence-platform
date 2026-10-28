"""v0.8 I4a: the independence audit (I4 spec §4.4). It fails closed.

Synthetic transcripts in the Claude Code JSONL shape (checked against 2.1.312): an `assistant` line
carries `tool_use` blocks, a `user` line the matching `tool_result`. Every withheld read (also one the
settings denied), web tool, network command to outside the environment, settings write, planning-time
change and unparseable line is a hit; network commands inside the environment are not.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import audit

CHECKOUT = "/home/op/code/ArchitectureIntelligencePlatform"
CONFIG = "/home/op/run/claude-planning"


def transcript(
    tmp_path: Path, calls: list[tuple[str, dict]], denied: bool = False, extra=()
) -> Path:
    lines = []
    for n, (tool, data) in enumerate(calls):
        lines.append(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "id": f"t{n}", "name": tool, "input": data}]
                },
            }
        )
        lines.append(
            {
                "type": "user",
                "message": {
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": f"t{n}",
                            "is_error": denied,
                            "content": "x",
                        }
                    ]
                },
            }
        )
    path = tmp_path / "session.jsonl"
    path.write_text("\n".join([json.dumps(line) for line in lines] + list(extra)) + "\n")
    return path


def kinds(tmp_path, calls, session="execution", **kw) -> list[str]:
    path = transcript(tmp_path, calls, **kw)
    return sorted({h["kind"] for h in audit.audit_session(path, session, [CHECKOUT], [CONFIG], [])})


def bash(command: str) -> tuple[str, dict]:
    return ("Bash", {"command": command})


def test_clean_transcript(tmp_path):
    calls = [
        ("Read", {"file_path": "/home/op/run/workspace/src/x/topics.go"}),
        bash("docker exec redpanda rpk group describe ecommerce-image-service"),
        bash("curl -s -H 'Host: catalog.127.0.0.1.nip.io' http://127.0.0.1/healthz"),
        bash(
            "docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --list"
        ),
        bash("nc -z kafka 29092"),
        (
            "mcp__aip__get_binding_picture",
            {"mode": "query", "bounded_context_id": "catalog-management"},
        ),
    ]
    assert kinds(tmp_path, calls) == []


@pytest.mark.parametrize(
    ("call", "kind"),
    [
        (
            ("Read", {"file_path": f"{CHECKOUT}/docs/specifications/0.8.0/specification.md"}),
            "WITHHELD_PATH",
        ),
        (bash(f"cat {CHECKOUT}/README.md"), "WITHHELD_PATH"),
        (bash("grep -r mirror ~/code/aip-v08-i4a/harness/v08"), "WITHHELD_PATH"),
        (bash("find / -name 'plan-key*'"), "WITHHELD_PATH"),
        (("WebFetch", {"url": "https://example.com"}), "WEB_TOOL"),
        (bash("curl -s https://raw.githubusercontent.com/x/y"), "NETWORK_OUTSIDE"),
        (bash("wget example.com/file"), "NETWORK_OUTSIDE"),
        (bash("curl $URL"), "NETWORK_OUTSIDE"),
        (bash("git clone https://github.com/x/y"), "NETWORK_OUTSIDE"),
        (bash("cd src && gh repo view"), "NETWORK_OUTSIDE"),
        (bash("docker pull apache/kafka:latest"), "NETWORK_OUTSIDE"),
        (bash("helm dependency update charts/x"), "NETWORK_OUTSIDE"),
        (bash("docker exec kafka curl https://example.com"), "NETWORK_OUTSIDE"),
        (("Edit", {"file_path": "/home/op/run/workspace/.claude/settings.json"}), "SETTINGS_WRITE"),
        (bash(f"cat {CONFIG}/projects/x.jsonl"), "SETTINGS_WRITE"),
    ],
)
def test_each_hit(tmp_path, call, kind):
    assert kind in kinds(tmp_path, [call])


def test_denied_attempt_still_counts(tmp_path):
    hits = audit.audit_session(
        transcript(tmp_path, [("Read", {"file_path": f"{CHECKOUT}/x"})], denied=True),
        "execution",
        [CHECKOUT],
        [],
        [],
    )
    assert hits[0]["kind"] == "WITHHELD_PATH" and hits[0]["denied"] is True


@pytest.mark.parametrize(
    "call",
    [
        bash("docker rm -f kafka"),
        bash("kubectl -n dev scale deployment/x --replicas=0"),
        bash("kubectl apply -f x.yaml"),
        bash("docker exec redpanda rpk topic create x"),
        bash(
            "docker exec kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:29092 --create --topic x"
        ),
        bash("sed -i s/a/b/ values.yaml"),
        bash("ls && touch x"),
        ("Write", {"file_path": "/home/op/run/workspace/notes.txt", "content": "x"}),
    ],
)
def test_planning_changes(tmp_path, call):
    assert "PLANNING_CHANGE" in kinds(tmp_path, [call], session="planning")
    assert "PLANNING_CHANGE" not in kinds(tmp_path, [call], session="execution")


def test_planning_reads_and_plan_files_are_allowed(tmp_path):
    calls = [
        bash("kubectl -n dev get configmap x -o yaml | head -50"),
        bash("docker exec redpanda rpk topic describe x"),
        bash("helm template ./chart -f values.yaml"),
        ("Write", {"file_path": "/home/op/run/workspace/plan.json", "content": "{}"}),
        ("Edit", {"file_path": "/home/op/run/workspace/plan.md"}),
    ]
    assert kinds(tmp_path, calls, session="planning") == []


def test_unparseable_line(tmp_path):
    assert "UNPARSEABLE" in kinds(tmp_path, [], extra=["{not json"])


def test_requests_are_extracted_with_the_answer_the_agent_saw(tmp_path):
    answer = {"outcome": "ANSWERED", "snapshot": {"snapshot_id": "s"}}
    request = {"mode": "query", "bounded_context_id": "catalog-management", "environment": "local"}
    lines = [
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "a", "name": audit.BINDING_TOOL, "input": {"request": request}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "a", "content": [{"type": "text", "text": json.dumps(answer)}]}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": "b", "name": audit.BINDING_TOOL, "input": {"request": {**request, "mode": "evidence"}}}]}},
    ]  # fmt: skip
    path = tmp_path / "s.jsonl"
    path.write_text("\n".join(json.dumps(line) for line in lines))
    found: list[dict] = []
    audit.audit_session(path, "planning", [CHECKOUT], [], found)
    assert [(r["request"]["mode"], r["transcript_answer"]) for r in found] == [("query", answer)]


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods -n dev 2>&1 | head",
        "grep -E 'a|b' src/x/topics.go",
        "kubectl get cm x -o json | jq '.data | keys'",
        "echo $(date -u)",
        "ls src &>/dev/null; cat src/a.yaml",
        "docker exec redpanda rpk group list 2>/dev/null || true",
    ],
)
def test_read_only_shell_forms_are_not_planning_changes(tmp_path, command):
    assert kinds(tmp_path, [bash(command)], session="planning") == []


@pytest.mark.parametrize(
    "command",
    ["kubectl get cm x -o yaml > values.yaml", "cat a >> b", "echo x | tee out.txt"],
)
def test_writes_in_planning(tmp_path, command):
    assert "PLANNING_CHANGE" in kinds(tmp_path, [bash(command)], session="planning")


@pytest.mark.parametrize(
    ("command", "outside"),
    [
        ("cat > probe.sh <<'EOF'\ncurl https://example.com\nEOF\nbash probe.sh", False),
        ("bash -c 'curl -s https://example.com'", True),
        ("docker exec -e A=1 kafka curl https://example.com", True),
        ("curl http://catalog.127.0.0.1.nip.io/x", False),
        ("curl http://catalog.8.8.8.8.nip.io/x", True),
        ("curl --connect-to ::127.0.0.1: http://catalog.127.0.0.1.nip.io/x", False),
    ],
)
def test_network_targets(tmp_path, command, outside):
    assert ("NETWORK_OUTSIDE" in kinds(tmp_path, [bash(command)])) is outside


def test_withheld_paths_match_at_a_path_boundary(tmp_path):
    run_home = f"{CHECKOUT}-run/workspace/src/x.yaml"
    assert kinds(tmp_path, [("Read", {"file_path": run_home})]) == []
    assert kinds(tmp_path, [("Read", {"file_path": CHECKOUT})]) == ["WITHHELD_PATH"]


def test_file_content_is_not_a_locator(tmp_path):
    """A plan may quote AIP's producer name; only paths, patterns, URLs and commands count."""
    content = {
        "file_path": "/home/op/run/workspace/plan.md",
        "content": "producer architecture-intelligence-platform",
    }
    assert kinds(tmp_path, [("Write", content)], session="planning") == []
