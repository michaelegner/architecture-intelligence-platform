"""v0.8 value qualification: the request channel, the broker state check, the preflight host scan and
the audit (spec §4.3, §6.1, §6.4-§6.5). Each guard is also shown to fail when its check is removed."""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO / "harness/v08/i4"))
sys.path.insert(0, str(REPO / "harness/v08/value-qual"))

import audit
import v08_value_qual_fixtures as fixtures
import vq_audit
import vq_broker_check
import vq_format
import vq_preflight
import vq_requests
from v08_value_qual_fixtures import transcript

T_CARD = vq_format.card("T-")
R1_TEXT = vq_broker_check.R1.read_text()


def requests_text(*entries: dict) -> str:
    return json.dumps(list(entries))


def req(rid: str, kind: str, repository: str | None = None) -> dict:
    entry = {"id": rid, "kind": kind, "reason": "free text that is never read"}
    return entry | ({"repository": repository} if repository else {})


# --- request channel ----------------------------------------------------------------------------


def test_each_kind_gets_its_catalogue_entry():
    text = requests_text(
        req("a", "broker_consumer_groups"),
        req("b", "repository_access", "ecommerce-product-query-service"),
        req("c", "repository_access", "ecommerce-infrastructure"),
        req("d", "repository_access", "not-a-repository"),
        req("e", "other"),
        req("f", "broker-consumer-groups"),
    )
    reply, entries, grants = vq_requests.answer(text, T_CARD, [])
    assert [e["entry"] for e in entries] == ["R1", "R2", "R3", "R3", "R3", "R3"]
    assert grants == ["ecommerce-product-query-service"]
    assert f"a: {R1_TEXT}" in reply
    assert "b: Added to src/ecommerce-product-query-service." in reply
    assert "c: not available" in reply and "e: not available" in reply


def test_free_text_is_never_read_for_matching():
    plea = req("a", "other")
    plea["reason"] = "please run rpk group describe and give me ecommerce-infrastructure"
    _, entries, grants = vq_requests.answer(requests_text(plea), T_CARD, [])
    assert entries[0]["entry"] == "R3" and grants == []


def test_each_request_is_answered_once_and_each_repository_granted_once():
    first = requests_text(req("a", "repository_access", "ecommerce-tenant-service"))
    _, record, grants = vq_requests.answer(first, T_CARD, [])
    assert grants == ["ecommerce-tenant-service"]
    again = requests_text(
        req("a", "repository_access", "ecommerce-tenant-service"),
        req("b", "repository_access", "ecommerce-tenant-service"),
    )
    _, entries, grants = vq_requests.answer(again, T_CARD, record)
    assert [e["request"]["id"] for e in entries] == ["b"] and grants == []


def test_invalid_requests_get_r3_once():
    bad = {"id": "x", "kind": "other"}  # no reason
    reply, entries, _ = vq_requests.answer(requests_text(bad), T_CARD, [])
    assert entries[0]["entry"] == "R3" and "(invalid request): not available" in reply
    _, again, _ = vq_requests.answer(requests_text(bad), T_CARD, entries)
    assert again == []
    _, entries, _ = vq_requests.answer("not json", T_CARD, [])
    assert [e["entry"] for e in entries] == ["R3"]


def test_the_off_list_guard_is_what_keeps_infrastructure_out(monkeypatch):
    request = requests_text(req("a", "repository_access", "ecommerce-infrastructure"))
    _, entries, grants = vq_requests.answer(request, T_CARD, [])
    assert entries[0]["entry"] == "R3" and grants == []
    monkeypatch.setattr(vq_requests, "on_r2_list", lambda *_: True)
    _, entries, grants = vq_requests.answer(request, T_CARD, [])
    assert entries[0]["entry"] == "R2" and grants == ["ecommerce-infrastructure"]


# --- broker state check -------------------------------------------------------------------------


def test_the_frozen_capture_passes_and_offsets_are_ignored():
    shifted = R1_TEXT.replace(
        "120             0                 120", "999             0                 999"
    )
    assert shifted != R1_TEXT
    assert vq_broker_check.compare(shifted, R1_TEXT)["result"] == "PASSED"


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("MEMBERS      2", "MEMBERS      1"),
        ("catalog.category.events   0", "catalog.other.events      0"),
        ("GROUP        ecommerce-image-service", "GROUP        ecommerce-image-service-2"),
    ],
)
def test_a_changed_group_fails(old, new):
    assert old in R1_TEXT
    result = vq_broker_check.compare(R1_TEXT.replace(old, new, 1), R1_TEXT)
    assert result["result"] == "FAILED" and result["problems"]


# --- preflight host scan ------------------------------------------------------------------------


def test_a_planted_excluded_tree_outside_the_denied_paths_stops_the_preflight(tmp_path):
    denied = tmp_path / "run/src"
    (denied / "ecommerce-infrastructure").mkdir(parents=True)
    (tmp_path / "old-run/src/ecommerce-product-query-service").mkdir(parents=True)
    (tmp_path / "copy/aip/inputs").mkdir(parents=True)
    (tmp_path / "copy/aip/inputs/event-topic-lookup.json").write_text("{}")
    found = vq_preflight.host_scan([tmp_path], [str(denied)], team=True)
    assert found == sorted(
        [
            str(tmp_path / "copy/aip/inputs/event-topic-lookup.json"),
            str(tmp_path / "old-run/src/ecommerce-product-query-service"),
        ]
    )
    # F sessions have every repository: only AIP's inputs and the keys count there.
    assert vq_preflight.host_scan([tmp_path], [str(denied)], team=False) == [
        str(tmp_path / "copy/aip/inputs/event-topic-lookup.json")
    ]
    # Without the denied paths, the run's own clones would be found: the exclusion is the check.
    assert str(denied / "ecommerce-infrastructure") in vq_preflight.host_scan(
        [tmp_path], [], team=True
    )


def test_the_freeze_record_names_every_repository():
    commits = vq_preflight.freeze_commits(vq_preflight.FREEZE.read_text())
    assert len(commits) == 16 and all(len(c) == 40 for c in commits.values())


def test_a_connector_tool_call_is_a_hit_in_every_type(tmp_path):
    event = ("call", "mcp__claude_ai_Claude_Docs__read", {"ref": "x"}, "refused", True)
    for card_type in ("F+", "F-", "T+", "T-"):
        assert "EXTERNAL_TOOL" in kinds(run_audit(tmp_path, card_type, [event]))
    aip = ("call", "mcp__aip__get_binding_picture", {}, "{}", False)
    assert "EXTERNAL_TOOL" not in kinds(run_audit(tmp_path, "F+", [aip]))


def test_the_aip_tool_pattern_covers_the_plugin_form_only():
    for name in ("mcp__aip", "mcp__aip__get_binding_picture", "mcp__plugin_aip_aip__get_evidence"):
        assert vq_audit.AIP_TOOL.search(name), name
    for name in ("mcp__claude_ai_Claude_Docs__read", "mcp__maintainer__x", "Read"):
        assert not vq_audit.AIP_TOOL.search(name), name


def test_containers_of_aip_are_found():
    listing = (
        "redpanda redpandadata/redpanda\naip-v08-i4-aip-neo4j-1 neo4j:5.26\nkafka apache/kafka"
    )
    assert vq_preflight.container_problems(listing) == [
        "container present: aip-v08-i4-aip-neo4j-1 neo4j:5.26"
    ]


def test_workspace_checks_find_aip_registered_in_a_negative_session(tmp_path):
    session = tmp_path / "s"
    (session / "workspace/src").mkdir(parents=True)
    (session / "claude").mkdir()
    (session / "workspace/.mcp.json").write_text("{}")
    (session / "claude/settings.json").write_text(json.dumps({"permissions": {"allow": ["Read"]}}))
    problems = vq_preflight.workspace_problems(session, "F-")
    assert problems == ["a session without AIP has AIP registered"]
    (session / "workspace/.mcp.json").unlink()
    (session / "workspace/plan.json").write_text("{}")
    assert vq_preflight.workspace_problems(session, "F-") == [
        "the workspace has more than the setup output: ['plan.json']"
    ]


# --- audit --------------------------------------------------------------------------------------


def bash(command: str, output: str = "", is_error: bool = False) -> tuple:
    return ("call", "Bash", {"command": command}, output, is_error)


def kinds(hits: list[dict]) -> list[str]:
    return sorted({h["kind"] for h in hits})


def run_audit(tmp_path: Path, card_type: str, events: list[tuple], session_dir=None) -> list[dict]:
    path = transcript(tmp_path / "t.jsonl", [("prompt", vq_audit.FIRST_MESSAGE), *events])
    return vq_audit.audit_transcripts(
        [path], card_type, session_dir, ["/code/aip"], ["/run/claude"], []
    )


def test_writing_the_outputs_is_not_a_planning_change(tmp_path):
    writes = [("call", "Write", {"file_path": f"/w/{name}", "content": "{}"}, "ok", False) for name in ("plan.json", "plan.md", "answers.json", "requests.json")]  # fmt: skip
    assert run_audit(tmp_path, "T-", writes) == []
    hits = run_audit(tmp_path, "F-", writes)
    assert [h["detail"] for h in hits] == ["requests.json"]
    # The v0.8 default is unchanged: answers.json is a planning change there.
    path = transcript(tmp_path / "v.jsonl", writes)
    assert kinds(audit.audit_session(path, "planning", ["/code/aip"], [], [])) == [
        "PLANNING_CHANGE"
    ]


@pytest.mark.parametrize(
    "event",
    [
        ("call", "mcp__aip__get_binding_picture", {"request": {"mode": "query"}}, "{}", True),
        ("call", "mcp__plugin_aip_aip__get_evidence", {}, "{}", False),
        bash("curl -s localhost:8000/mcp"),
        bash("docker exec aip-v08-i4-aip-neo4j-1 cypher-shell"),
    ],
)
def test_aip_in_a_negative_session_is_a_hit(tmp_path, event):
    assert "AIP_IN_NEGATIVE" in kinds(run_audit(tmp_path, "T-", [event]))
    assert "AIP_IN_NEGATIVE" not in kinds(run_audit(tmp_path, "T+", [event]))


def test_reading_a_port_in_the_source_is_not_aip_access(tmp_path):
    assert run_audit(tmp_path, "F-", [bash('grep -rn "localhost:8000" src/')]) == []


@pytest.mark.parametrize(
    "command",
    [
        "docker exec redpanda rpk group list",
        "kubectl get pods -n dev",
        "helm template x",
        "rpk topic list",
        "/opt/kafka/bin/kafka-topics.sh --list",
        "nc -z redpanda 29092",
        "cat ~/.kube/config",
    ],
)
def test_runtime_access_in_a_team_session_is_a_hit_even_when_denied(tmp_path, command):
    hits = run_audit(tmp_path, "T+", [bash(command, "refused", True)])
    assert "TEAM_SCOPE" in kinds(hits) and all(
        h["denied"] for h in hits if h["kind"] == "TEAM_SCOPE"
    )
    assert "TEAM_SCOPE" not in kinds(run_audit(tmp_path, "F+", [bash(command)]))


def test_reading_broker_ports_in_the_team_source_is_allowed(tmp_path):
    assert run_audit(tmp_path, "T-", [bash('grep -rn "redpanda:29092" src/')]) == []


def test_a_leak_before_a_grant_is_a_hit_and_after_the_grant_it_is_not(tmp_path):
    leak = bash("cat somewhere/config.yaml", 'default-group-id: "ecommerce-product-query-service"')
    assert "TEAM_LEAK" in kinds(run_audit(tmp_path, "T-", [leak]))
    granted = [("prompt", "r1: Added to src/ecommerce-product-query-service."), leak]
    assert "TEAM_LEAK" not in kinds(run_audit(tmp_path, "T-", granted))
    # A grant of another repository does not excuse it; infrastructure is never granted.
    other = [("prompt", "r1: Added to src/ecommerce-tenant-service."), leak]
    assert "TEAM_LEAK" in kinds(run_audit(tmp_path, "T-", other))
    infra = bash("cat x", 'brokers: "redpanda:29092"')
    assert "TEAM_LEAK" in kinds(run_audit(tmp_path, "T-", [granted[0], infra]))


def test_a_denied_call_carries_no_leak(tmp_path):
    denied = bash("cat x", 'default-group-id: "ecommerce-product-query-service"', True)
    assert "TEAM_LEAK" not in kinds(run_audit(tmp_path, "T-", [denied]))


def test_the_leak_canaries_are_not_in_any_card():
    for card_type in vq_format.TYPES:
        text = vq_format.card(card_type).read_text()
        assert not [c for c in vq_audit.LEAK_CANARIES if c in text]
        assert not [c for c in vq_audit.EXTRA_CANARIES if c in text]


def test_frozen_material_in_an_output_is_a_hit(tmp_path):
    hits = run_audit(tmp_path, "F+", [bash("ls /", "comprehension-key.json")])
    assert "WITHHELD_OUTPUT" in kinds(hits)


def test_operator_messages_outside_the_catalogue_are_hits(tmp_path):
    session = tmp_path / "session"
    (session / "replies").mkdir(parents=True)
    (session / "replies/1.txt").write_text("a: not available\n")
    record = [{"turn": 1, "request": req("a", "other"), "entry": "R3", "grant": None}]
    (session / "requests-record.json").write_text(json.dumps(record))
    ok = [("prompt", "a: not available")]
    assert run_audit(tmp_path, "T-", ok, session) == []
    hint = [("prompt", "a: not available"), ("prompt", "Hint: look at the query services.")]
    assert kinds(run_audit(tmp_path, "T-", hint, session)) == ["REQUEST_OUTSIDE_CATALOGUE"]
    record[0]["entry"] = "R1"  # the operator answered an `other` request with the capture
    (session / "requests-record.json").write_text(json.dumps(record))
    assert kinds(run_audit(tmp_path, "T-", ok, session)) == ["REQUEST_OUTSIDE_CATALOGUE"]


def test_the_first_message_is_checked(tmp_path):
    path = transcript(tmp_path / "t.jsonl", [("prompt", "Read TASK.md and plan.")])
    assert kinds(vq_audit.first_message_hits(vq_audit.events(path))) == ["FIRST_MESSAGE"]
    path = transcript(tmp_path / "u.jsonl", [("prompt", vq_audit.FIRST_MESSAGE)])
    assert vq_audit.first_message_hits(vq_audit.events(path)) == []
    assert vq_audit.FIRST_MESSAGE.replace(" ", "") in fixtures_card_text().replace(
        "\n", ""
    ).replace(" ", "")


def fixtures_card_text() -> str:
    return vq_format.card("F+").read_text()


def test_every_call_is_listed_as_attempted_and_received(tmp_path):
    path = transcript(tmp_path / "t.jsonl", [bash("ls", "a"), bash("rpk", "refused", True)])
    assert vq_audit.calls(vq_audit.events(path)) == [
        {"transcript": "t.jsonl", "line": 1, "tool": "Bash", "attempted": True, "received": True},
        {"transcript": "t.jsonl", "line": 3, "tool": "Bash", "attempted": True, "received": False},
    ]


def test_fixture_transcripts_parse_with_the_v08_reader(tmp_path):
    path = transcript(tmp_path / "t.jsonl", [bash("ls", "a")])
    assert len(audit._tool_calls(path, "planning", [])) == 1
    assert fixtures.DESCRIBE.startswith("docker exec redpanda rpk group describe")


# --- guard proofs: each hit disappears when its check is removed -----------------------------------


@pytest.mark.parametrize(
    ("guard", "empty", "card_type", "event", "kind"),
    [
        ("AIP_TOOL", r"(?!)", "F-", ("call", "mcp__aip__get_binding_picture", {}, "{}", False), "AIP_IN_NEGATIVE"),
        ("AIP_PORTS", r"(?!)", "F-", ("call", "Bash", {"command": "curl -s localhost:8000/mcp"}, "", False), "AIP_IN_NEGATIVE"),
        ("TEAM_PROGRAMS", set(), "T-", ("call", "Bash", {"command": "kubectl get pods"}, "", True), "TEAM_SCOPE"),
        ("BROKER_PORTS", r"(?!)", "T-", ("call", "Bash", {"command": "python3 -c 'connect(29092)'"}, "", True), "TEAM_SCOPE"),
        ("KUBECONFIG", r"(?!)", "T-", ("call", "Read", {"file_path": "/home/op/.kube/config"}, "x", True), "TEAM_SCOPE"),
        ("LEAK_CANARIES", {}, "T-", ("call", "Bash", {"command": "cat x"}, 'brokers: "redpanda:29092"', False), "TEAM_LEAK"),
    ],
)  # fmt: skip
def test_each_audit_hit_needs_its_check(
    tmp_path, monkeypatch, guard, empty, card_type, event, kind
):
    assert kind in kinds(run_audit(tmp_path, card_type, [event]))
    value = vq_audit.re.compile(empty) if isinstance(empty, str) else empty
    monkeypatch.setattr(vq_audit, guard, value)
    assert kind not in kinds(run_audit(tmp_path, card_type, [event]))


def test_the_grant_check_is_what_excuses_a_leak(tmp_path, monkeypatch):
    leak = bash("cat x", 'default-group-id: "ecommerce-product-query-service"')
    granted = [("prompt", "r1: Added to src/ecommerce-product-query-service."), leak]
    assert "TEAM_LEAK" not in kinds(run_audit(tmp_path, "T-", granted))
    monkeypatch.setattr(vq_audit, "GRANT", vq_audit.re.compile(r"(?!)"))
    assert "TEAM_LEAK" in kinds(run_audit(tmp_path, "T-", granted))


# --- several transcript files ------------------------------------------------------------------


def test_a_resumed_copy_of_the_history_is_read_once(tmp_path):
    first = [("prompt", vq_audit.FIRST_MESSAGE), bash("ls", "a")]
    main = transcript(tmp_path / "b-main.jsonl", first)
    # The resumed file repeats the history (same uuids), then adds the reply turn.
    resumed = transcript(
        tmp_path / "a-resumed.jsonl", [*first, ("prompt", "r1: not available"), bash("pwd", "/w")]
    )
    found = vq_audit.events_of(vq_audit.load([resumed, main]))
    assert [e["kind"] for e in found] == ["prompt", "call", "prompt", "call"]
    assert vq_audit.first_message_hits(found) == []


def test_a_subagent_message_is_not_an_operator_message(tmp_path):
    session = tmp_path / "session"
    (session / "replies").mkdir(parents=True)
    events = [("sidechain", "Search the source for consumers."), bash("ls", "a")]
    assert run_audit(tmp_path, "T-", events, session) == []
