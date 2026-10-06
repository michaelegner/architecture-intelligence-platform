"""v0.5.1 I3 smoke test for `examples/quarkus-super-heroes-demo/` (spec §6).

Runs the real `run.sh` against the real Compose stack, the same way a user would, then re-checks
the result independently over standard negotiated MCP:

- `run.sh` exits 0, which means its own `check_ready.py` accepted the §4 step 5 answer shape;
- `tools/list` advertises exactly the four read-only tools (the fourth since v0.6.0 I3.3b);
- the MCP `get_service_dependencies` answer validates against the published answer schema for its own
  `schema_version` (v0.6: `rest-fights` declares a Broker, v0.6.1 spec §5.2) and passes the same
  pinned shape (`check_ready.check_answer`, imported rather than duplicated);
- the v0.6.1 §6.3 two-sided Broker question over the real transport: exactly one Broker claim for
  `rest-fights`, backed by the overlay's `kafka:fights-kafka` evidence, **and** the
  `PUBLISHES_TO Topic:fights` path still does not resolve a Subscription or consumer (the answer
  stays `PARTIAL` with the existing `UNRESOLVED_IDENTITY` limitation, no invented Subscription claim
  or entity);
- one `get_evidence` drill-down resolves every reference at the answer's own snapshot, and every
  Broker-claim reference resolves to the exact `(USES_BROKER, rest-fights, Broker)` fact;
- the replay is finished: the Collector is stopped, so nothing can ingest any more;
- `run.sh --down` removes the stack and the run-local state.

Isolation: `run.sh` uses a fixed Compose project (`aip-qsh-demo`) and fixed host ports (8000,
4318). The test skips, rather than touching anything, when that project is already running or a
port is taken, so a developer's own running demo is never torn down. It tears down only a stack it
started itself.
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
DEMO_DIR = REPO_ROOT / "examples" / "quarkus-super-heroes-demo"
RUN_SH = DEMO_DIR / "run.sh"
RUN_DIR = REPO_ROOT / ".aip-qsh-demo"
BASH = shutil.which("bash")
DOCKER = shutil.which("docker")
PROJECT = "aip-qsh-demo"
MCP_URL = "http://localhost:8000/mcp"
MCP_HEADERS = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
    "mcp-protocol-version": "2025-11-25",
}

pytestmark = [
    pytest.mark.demo_e2e,
    pytest.mark.skipif(DOCKER is None, reason="requires Docker + Compose to run the real demo"),
]


def _check_ready():
    """The demo's own readiness checker, so the pinned answer shape lives in one place."""
    spec = importlib.util.spec_from_file_location("qsh_check_ready", DEMO_DIR / "check_ready.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _project_containers() -> str:
    """The demo project's containers, read through the exact Compose contract run.sh uses: the
    demo's own compose file, the repository as project directory and no .env file. The bare
    `docker compose -p` form would load the repository's root docker-compose.yml, a different
    definition whose required NEO4J_PASSWORD may be unset in a fresh checkout."""
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
        env={**os.environ, "QSH_DEMO_NEO4J_PASSWORD": "unused"},
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


def _assert_the_broker_answer_and_its_boundary(answer: dict, evidence: dict) -> None:
    """Spec §6.3's two sides of one answer. 1: exactly one Broker claim for rest-fights, backed by the
    overlay's `kafka:fights-kafka` evidence. 2: knowing the Broker does not resolve the Subscription."""
    assert answer["schema_version"] == "0.6" and evidence["schema_version"] == "0.6"

    broker_claims = [c for c in answer["claims"] if c["predicate"] == "USES_BROKER"]
    assert len(broker_claims) == 1
    [claim] = broker_claims
    assert claim["subject"]["id"] == "service:rest-fights"
    assert claim["object"]["type"] == "BROKER" and claim["object"]["name"] == "kafka:fights-kafka"
    assert answer["data"]["broker_claim_ids"] == [claim["claim_id"]]
    records = {record["id"]: record for record in evidence["data"]["records"]}
    assert claim["evidence_refs"], "the Broker claim must be evidence-backed"
    for ref in claim["evidence_refs"]:
        # the overlay's own AsyncAPI source (declared evidence), resolving to the exact Broker fact
        assert records[ref]["source_type"] == "ASYNCAPI"
        assert records[ref]["source_locator"].endswith("overlay/rest-fights/asyncapi.yaml")
        assert any(
            fact["relation_type"] == "USES_BROKER"
            and fact["source_id"] == "service:rest-fights"
            and fact["target_id"] == claim["object"]["id"]
            and fact["broker"]["name"] == "kafka:fights-kafka"
            for fact in records[ref]["supports"]
        ), ref

    # the existing Topic/Subscription limit is unchanged: PARTIAL, one UNRESOLVED_IDENTITY on the
    # PUBLISHES_TO claim, and no invented Subscription claim or entity anywhere in the answer
    assert answer["outcome"] == "PARTIAL"
    published = [
        c
        for c in answer["claims"]
        if (c.get("delivery") or {}).get("relation_type") == "PUBLISHES_TO"
    ]
    assert len(published) == 1 and published[0]["delivery"].get("subscription") is None
    assert [(lim["code"], lim["claim_ids"]) for lim in answer["limitations"]] == [
        ("UNRESOLVED_IDENTITY", [published[0]["claim_id"]])
    ]
    assert not [c for c in answer["claims"] if "SUBSCRIPTION" in json.dumps(c)]
    assert not [
        fact
        for record in evidence["data"]["records"]
        for fact in record["supports"]
        if fact["relation_type"] == "SUBSCRIPTION_OF"
    ]


def test_one_command_demo_answers_and_drills_down_at_one_snapshot():
    if _project_containers():
        pytest.skip(f"Compose project {PROJECT} already exists; leaving a developer's demo alone")
    if _port_open(8000) or _port_open(4318):
        pytest.skip("port 8000 or 4318 is in use; the demo needs both")

    check_ready = _check_ready()
    # The guard above proved the project did not exist, so anything run.sh creates from here on
    # is this test's own: tear it down on every exit path, including a run.sh timeout.
    try:
        run = _run(timeout=900)
        assert run.returncode == 0, f"run.sh failed:\n{run.stdout}\n{run.stderr}"
        assert "demo is ready" in run.stdout

        # The replay is finished: the Collector is stopped, and the printed prompt carries the
        # frozen observation context.
        assert not _port_open(4318)
        prompt = (RUN_DIR / "prompt.txt").read_text()
        for value in check_ready.CONTEXT.values():
            assert value in prompt

        tools = [tool["name"] for tool in _mcp("tools/list", {}, 1)["tools"]]
        assert tools == [
            "get_architecture_drift",
            "get_evidence",
            "get_service_dependencies",
            "get_service_dependencies_by_locality",
        ]

        answer = _call(
            "get_service_dependencies",
            {"service_id": check_ready.SERVICE_ID, "observation_context": check_ready.CONTEXT},
            2,
        )
        validate_dependencies(answer)
        assert check_ready.check_answer(answer) == []

        snapshot_id = answer["snapshot"]["snapshot_id"]
        evidence = _call(
            "get_evidence",
            {"evidence_refs": answer["evidence_refs"], "snapshot_id": snapshot_id},
            3,
        )
        validate_evidence(evidence)
        assert evidence["outcome"] == "ANSWERED"
        assert evidence["snapshot"]["snapshot_id"] == snapshot_id
        assert evidence["data"]["missing_evidence_refs"] == []
        resolved = {record["id"] for record in evidence["data"]["records"]}
        assert resolved == set(answer["evidence_refs"])
        _assert_the_broker_answer_and_its_boundary(answer, evidence)
    finally:
        down = _run("--down", timeout=300)
        assert down.returncode == 0, f"run.sh --down failed:\n{down.stdout}\n{down.stderr}"

    assert _project_containers() == ""
    assert not RUN_DIR.exists()
