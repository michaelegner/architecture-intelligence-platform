"""v0.6.2 I1a smoke test for `examples/pitstop-demo/` (spec §7.2).

Runs the real `run.sh` against the real Compose stack, the same way a user would, then re-checks the
result independently over standard negotiated MCP:

- `run.sh` exits 0, which means its own `check_ready.py` accepted the §4.4 answer shape;
- `tools/list` advertises exactly the four read-only tools;
- Q1/Q2: the publisher's `get_service_dependencies` answer validates against the published v0.6 schema,
  passes the same pinned shape (`check_ready.check_answer`, imported rather than duplicated) and lists
  the five receivers through their queues, plus one Broker claim;
- Q3: ReportingService's claim cites its declared overlay evidence and its route's observed evidence,
  and both resolve through `get_evidence` at the answer's own snapshot;
- §4.4 drift: `get_architecture_drift` for the same service and context is `ANSWERED` with no claims and
  no limitations (pinned by `check_ready.check_drift`, also enforced by `run.sh`);
- Q4: every claim carries the publisher's qualification, while only four of the five receiver routes
  carry observed evidence (the authored fixture has no AuditlogService receive span);
- Q5: no answer or evidence field holds any payload, field name or event type: AIP has no field-level
  knowledge, so the boundary is stated by the demo text, never by an answer;
- the bounded drill-down protocol of spec §4.4: a stale snapshot is refused (`SNAPSHOT_NOT_AVAILABLE`),
  a re-asked dependency question for the same window yields the same claims and a snapshot that resolves;
- the replay is finished: the Collector is stopped, so nothing can ingest any more;
- `run.sh --live` without the fork is rejected in preflight, and `run.sh --down` removes the stack and the run-local state.

Isolation: `run.sh` uses a fixed Compose project (`aip-pitstop-demo`) and fixed host ports (8000,
4318). The test skips, rather than touching anything, when that project is already running or a port
is taken, so a developer's own running demo is never torn down. It tears down only a stack it started
itself.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import urllib.request
from pathlib import Path

import pytest

from tests.support.answer_schemas import validate_dependencies, validate_evidence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "pitstop-demo"
RUN_SH = DEMO_DIR / "run.sh"
RUN_DIR = REPO_ROOT / ".aip-pitstop-demo"
BASH = shutil.which("bash")
DOCKER = shutil.which("docker")
PROJECT = "aip-pitstop-demo"
MCP_URL = "http://localhost:8000/mcp"
MCP_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-11-25",
}
MAX_DRILL_DOWN_ATTEMPTS = 3

pytestmark = [
    pytest.mark.demo_e2e,
    pytest.mark.skipif(DOCKER is None, reason="requires Docker + Compose to run the real demo"),
]


def _check_ready():
    """The demo's own readiness checker, so the pinned answer shape lives in one place."""
    spec = importlib.util.spec_from_file_location(
        "pitstop_check_ready", DEMO_DIR / "check_ready.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _project_containers() -> str:
    """The demo project's containers, read through the exact Compose contract run.sh uses: the demo's
    own compose file, the repository as project directory and no .env file."""
    result = subprocess.run(
        [
            DOCKER,
            "compose",
            "-p",
            PROJECT,
            "--project-directory",
            str(REPO_ROOT),
            "-f",
            str(DEMO_DIR / "docker-compose.yml"),
            "--env-file",
            "/dev/null",
            "ps",
            "-a",
            "-q",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
        # Only for interpolation of the demo's `:?` variable; `ps` connects to nothing.
        env={**os.environ, "PITSTOP_DEMO_NEO4J_PASSWORD": "unused"},
    )
    return result.stdout.strip()


def _run(*args: str, timeout: int) -> subprocess.CompletedProcess[str]:
    """Runs run.sh in its own process group. On timeout the whole group is killed, not just bash,
    so no orphaned `docker compose` child can keep creating containers after the teardown."""
    process = subprocess.Popen(
        [BASH, str(RUN_SH), *args],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, stdout, stderr)


def _mcp(method: str, params: dict, request_id: int) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
    request = urllib.request.Request(MCP_URL, body.encode(), MCP_HEADERS)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)["result"]


def _call(name: str, arguments: dict, request_id: int) -> dict:
    result = _mcp("tools/call", {"name": name, "arguments": {"request": arguments}}, request_id)
    assert result.get("isError") is False, result
    return result["structuredContent"]


def _publisher_answer(check_ready, request_id: int) -> dict:
    return _call(
        "get_service_dependencies",
        {"service_id": check_ready.SERVICE_ID, "observation_context": check_ready.CONTEXT},
        request_id,
    )


def _drill_down(check_ready, answer: dict, request_id: int) -> tuple[dict, dict]:
    """Spec §4.4's bounded client protocol: call get_evidence at the answer's own snapshot; on a
    stale-snapshot refusal re-ask the dependency question for the same context and retry, at most
    three attempts, then fail explicitly. Returns the (answer, evidence) pair that resolved."""
    for attempt in range(MAX_DRILL_DOWN_ATTEMPTS):
        evidence = _call(
            "get_evidence",
            {
                "evidence_refs": answer["evidence_refs"],
                "snapshot_id": answer["snapshot"]["snapshot_id"],
            },
            request_id + attempt,
        )
        if evidence["outcome"] == "ANSWERED":
            return answer, evidence
        assert [lim["code"] for lim in evidence["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
        answer = _publisher_answer(check_ready, request_id + 10 + attempt)
    pytest.fail("the drill-down failed after the bounded number of attempts")


def _receiver_claims(answer: dict) -> dict[str, dict]:
    return {
        c["object"]["name"]: c
        for c in answer["claims"]
        if (c.get("delivery") or {}).get("relation_type") == "PUBLISHES_TO"
    }


def test_one_command_demo_answers_the_question_ladder_at_one_snapshot():
    if _project_containers():
        pytest.skip(f"Compose project {PROJECT} already exists; leaving a developer's demo alone")
    if _port_open(8000) or _port_open(4318):
        pytest.skip("port 8000 or 4318 is in use; the demo needs both")

    check_ready = _check_ready()
    # The guard above proved the project did not exist, so anything run.sh creates from here on is
    # this test's own: tear it down on every exit path, including a run.sh timeout.
    try:
        run = _run(timeout=900)
        assert run.returncode == 0, f"run.sh failed:\n{run.stdout}\n{run.stderr}"
        assert "demo is ready" in run.stdout

        # The replay is finished: the Collector is stopped, and the printed prompt carries the
        # observation context and states the AIP boundary the question ladder relies on.
        assert not _port_open(4318)
        prompt = (RUN_DIR / "prompt.txt").read_text()
        for value in check_ready.CONTEXT.values():
            assert value in prompt
        assert "no payload or field-level knowledge" in " ".join(prompt.split())

        tools = [tool["name"] for tool in _mcp("tools/list", {}, 1)["tools"]]
        assert tools == [
            "get_architecture_drift",
            "get_evidence",
            "get_service_dependencies",
            "get_service_dependencies_by_locality",
        ]

        # Q1/Q2: what is published, and who receives (asked through the publisher)
        answer = _publisher_answer(check_ready, 2)
        validate_dependencies(answer)
        assert check_ready.check_answer(answer) == []
        receivers = _receiver_claims(answer)
        assert {n: c["delivery"]["subscription"]["name"] for n, c in receivers.items()} == {
            name: queue for name, (queue, _refs) in check_ready.EXPECTED_RECEIVERS.items()
        }
        [broker] = [c for c in answer["claims"] if c["predicate"] == "USES_BROKER"]
        assert broker["object"]["name"] == check_ready.EXPECTED_BROKER

        # the bounded drill-down: a stale snapshot is refused, a re-asked question resolves
        stale = _call(
            "get_evidence",
            {
                "evidence_refs": answer["evidence_refs"][:1],
                "snapshot_id": "aip:snapshot:v1:" + "0" * 64,
            },
            3,
        )
        assert stale["outcome"] == "NOT_ANSWERED"
        assert [lim["code"] for lim in stale["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]
        stale_answer = {
            **answer,
            "snapshot": {**answer["snapshot"], "snapshot_id": "aip:snapshot:v1:" + "0" * 64},
        }
        resolved_answer, evidence = _drill_down(check_ready, stale_answer, 4)
        assert resolved_answer["snapshot"]["snapshot_id"] == answer["snapshot"]["snapshot_id"]
        assert resolved_answer["claims"] == answer["claims"]

        validate_evidence(evidence)
        assert evidence["snapshot"]["snapshot_id"] == answer["snapshot"]["snapshot_id"]
        assert evidence["data"]["missing_evidence_refs"] == []
        records = {record["id"]: record for record in evidence["data"]["records"]}
        assert set(records) == set(answer["evidence_refs"])

        # Q3: why believe ReportingService receives from the exchange
        reporting = receivers["ReportingService"]
        types = {records[ref]["evidence_type"] for ref in reporting["resolution_evidence_refs"]}
        assert types == {"DECLARED", "OBSERVED"}
        declared = [
            records[ref]
            for ref in reporting["resolution_evidence_refs"]
            if records[ref]["evidence_type"] == "DECLARED"
        ]
        [declared] = declared
        assert declared["source_type"] == "ASYNCAPI"
        assert declared["source_locator"].endswith("overlay/reporting-service/asyncapi.yaml")
        assert any(
            fact["relation_type"] == "RECEIVES_FROM"
            and fact["source_id"] == "service:reporting-service"
            for fact in declared["supports"]
        )

        # Q4: the publisher's qualification, and which receiver routes carry observed evidence
        assert {c["qualification"] for c in receivers.values()} == {"CONFIRMED"}
        observed_routes = {
            name
            for name, claim in receivers.items()
            if any(
                records[ref]["evidence_type"] == "OBSERVED"
                for ref in claim["resolution_evidence_refs"]
            )
        }
        assert observed_routes == set(receivers) - {"AuditlogService"}

        # §4.4: the drift answer is only what the existing rules produce - ANSWERED, no claims
        drift = _call(
            "get_architecture_drift",
            {"service_id": check_ready.SERVICE_ID, "observation_context": check_ready.CONTEXT},
            30,
        )
        assert check_ready.check_drift(drift) == []
        assert (
            drift["outcome"] == "ANSWERED" and drift["claims"] == [] and drift["limitations"] == []
        )

        # Q5: AIP holds no field-level knowledge; no answer carries payload, field or event type
        everything = json.dumps([answer, evidence, drift])
        for forbidden in (
            "StartTime",
            "EndTime",
            "Duration",
            "payload",
            "MaintenanceJob",
            "MessageType",
        ):
            assert forbidden not in everything, forbidden
    finally:
        down = _run("--down", timeout=300)
        assert down.returncode == 0, f"run.sh --down failed:\n{down.stdout}\n{down.stderr}"

    assert _project_containers() == ""
    assert not RUN_DIR.exists()


def test_live_mode_needs_the_instrumented_fork_and_unknown_flags_are_rejected():
    """`--live` without PITSTOP_FORK_DIR fails fast in preflight, before anything is started."""
    env = {k: v for k, v in os.environ.items() if k != "PITSTOP_FORK_DIR"}
    live = subprocess.run(
        [BASH, str(RUN_SH), "--live"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert live.returncode == 1
    assert "PITSTOP_FORK_DIR must point at the instrumented Pitstop fork" in live.stderr
    assert _run("--bogus", timeout=60).returncode == 2
