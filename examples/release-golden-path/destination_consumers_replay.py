"""v0.7.1 I5 scope 4: the published-artifact Kafka replay harness.

Replays the frozen I4.1 package (`docs/specifications/0.7.1/i4-evidence/kafka/`, captures C1 then
C2) against one AIP image through its public HTTP boundary only:

    RELEASE_CANDIDATE_SHA=<40-hex> python examples/release-golden-path/destination_consumers_replay.py <IMAGE_REF> <OUT_DIR>

`golden_path.py` runs the same phase after `api-usage`. The image must already be present locally
and is never rebuilt. A fresh Compose project and a fresh Neo4j volume are used. The declarations,
the mapping and the capture are copied into the container at one fixed root (C2 replaces C1 as one
source updated in place), and `POST /api/import` imports them through the production path.

Every Topic is asked through REST and through an independent negotiated MCP client. Both answers
are compared with the frozen, independently authored I4.1 expectations (`expected.json`) and with
each other. Nothing here authors expected truth; a disagreement is a finding, never a reason to edit
the frozen package. Service-level equality and the A/B identity are not re-claimed from outside the
image; the exact-candidate I4 qualification covers them."""

from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema
import neo4j

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import golden_path as gp

PHASE = "destination-consumers"
SERVICE = "architecture-intelligence"
CONTAINER_ROOT = "/app/golden-path/destination-consumers"
KAFKA = gp.REPO / "docs" / "specifications" / "0.7.1" / "i4-evidence" / "kafka"
EXPECTED = json.loads((KAFKA / "expected.json").read_text())
TOPICS = ("orders.created", "payments.completed", "payments.dlq", "payments.failed")
ANSWER_SCHEMA = gp.SCHEMA_ROOT / "v0.7.1" / "destination-consumers-answer.schema.json"
# Client-supplied member text from the captures; it must never reach a public answer.
MEMBER_TEXT = ("/172.19.", "console-consumer", "segmentio", "consumer-order-service-1")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Surfaces:
    """REST and one negotiated MCP client over the image's public HTTP boundary."""

    def __init__(self) -> None:
        self.client = gp.McpClient()
        self.answers: list[tuple[str, str, dict[str, Any]]] = []

    def tools(self) -> list[str]:
        return self.client.tools_list()

    def ask(self, name: str, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        """The same request through REST (the body is the request without `mode`) and MCP."""
        evidence = request["mode"] == "evidence"
        route = "/api/destination-consumers" + ("/evidence" if evidence else "")
        body = {key: value for key, value in request.items() if key != "mode"}
        status, rest = gp.http("POST", f"{gp.AIP_URL}{route}", body)
        if status != 200:
            raise gp.HarnessError(f"REST {route}: {status} {rest}")
        result = self.client.call("get_destination_consumers", request)
        if result.get("isError") is not False:
            raise gp.HarnessError(f"MCP get_destination_consumers returned isError: {result}")
        mcp = result["structuredContent"]
        self.answers += [(name, "rest", rest), (name, "mcp", mcp)]
        return rest, mcp


def _copy(stack: gp.Stack, source: Path, target: str) -> None:
    stack.compose("exec", "-T", "-u", "root", SERVICE, "mkdir", "-p", target)
    stack.compose("cp", f"{source}/.", f"{SERVICE}:{target}")


def _stage_capture(stack: gp.Stack, capture: str) -> None:
    """Copy one frozen capture over the fixed source path."""
    _copy(stack, KAFKA / capture, f"{CONTAINER_ROOT}/kafka")


def _import(stack: gp.Stack) -> None:
    status, report = gp.http("POST", f"{gp.AIP_URL}/api/import")
    if status != 200 or report.get("committed") is not True:
        raise gp.HarnessError(f"POST /api/import: {status} {report}")


def _topic_ids(password: str) -> dict[str, str]:
    driver = neo4j.GraphDatabase.driver(gp.NEO4J_BOLT, auth=("neo4j", password))
    try:
        with driver.session(database="neo4j", default_access_mode=neo4j.READ_ACCESS) as session:
            records = list(session.run("MATCH (t:Topic) RETURN t.name AS name, t.id AS id"))
    finally:
        driver.close()
    return {record["name"]: record["id"] for record in records}


def _query(topic_ids: dict[str, str], topic: str) -> dict[str, Any]:
    return {
        "mode": "query",
        "destination_id": topic_ids[topic],
        "broker_id": EXPECTED["broker_id"],
        "environment": EXPECTED["environment"],
    }


def _agree(name: str, rest: dict[str, Any], mcp: dict[str, Any]) -> list[str]:
    return [] if _canonical(rest) == _canonical(mcp) else [f"{name}: REST and MCP differ"]


def reading_problems(answer: dict[str, Any], want: dict[str, Any], captured_at: str) -> list[str]:
    """The frozen I4.1 reading of one Topic, as `test_v071_i4_kafka_replay.py` asserts it."""
    problems = []
    if answer.get("outcome") != "PARTIAL":
        return [f"outcome {answer.get('outcome')!r}"]
    codes = [item["code"] for item in answer["limitations"]]
    if codes != want["limitations"]:
        problems.append(f"limitations {codes}")
    rows = answer["data"]["rows"]
    groups = sorted(row["group_id"] for row in rows)
    if groups != sorted(row["group_id"] for row in want["rows"]):
        return [*problems, f"groups {groups}"]
    got = {row["group_id"]: row for row in rows}
    for expected_row in want["rows"]:
        row = got[expected_row["group_id"]]
        group = expected_row["group_id"]
        if row["captured_at"] != captured_at or not row["attachment_evidence_refs"]:
            problems.append(f"{group}: captured_at or attachment evidence")
        if row["outcome"] != expected_row["outcome"]:
            problems.append(f"{group}: outcome {row['outcome']}")
        if "service" in expected_row:
            if row.get("service_id") != f"service:{expected_row['service']}":
                problems.append(f"{group}: service_id {row.get('service_id')!r}")
            if not row["mapping_evidence_refs"]:
                problems.append(f"{group}: no mapping evidence")
        elif row.get("service_id") is not None or row.get("reason") != expected_row["reason"]:
            problems.append(f"{group}: service_id/reason {row.get('service_id')!r}")
    text = json.dumps(answer)
    problems += [f"names {group}" for group in want["never_named"] if f'"{group}"' in text]
    problems += [f"member text {f!r}" for f in MEMBER_TEXT if f in text]
    return problems


def _readings(
    capture: str, topic_ids: dict[str, str], surfaces: Surfaces
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    captured_at = json.loads((KAFKA / capture / "kafka-consumer-state.json").read_text())[
        "captured_at"
    ]
    expected = EXPECTED[capture]["with_mapping"]
    problems: list[str] = []
    answers: dict[str, dict[str, Any]] = {}
    for topic in TOPICS:
        name = f"{capture}-{topic}"
        rest, mcp = surfaces.ask(name, _query(topic_ids, topic))
        problems += [
            f"{name}/rest {p}" for p in reading_problems(rest, expected[topic], captured_at)
        ]
        problems += [f"{name}/mcp {p}" for p in reading_problems(mcp, expected[topic], captured_at)]
        problems += _agree(name, rest, mcp)
        answers[topic] = rest
    return problems, answers


def _evidence_request(query: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    refs = sorted(
        {
            ref
            for row in answer["data"]["rows"]
            for ref in (*row["attachment_evidence_refs"], *row["mapping_evidence_refs"])
        }
    )
    return {**query, "mode": "evidence", "snapshot_id": answer["snapshot"]["snapshot_id"]} | {
        "evidence_refs": refs
    }


def _resolved(answer: dict[str, Any], refs: list[str]) -> bool:
    entries = (answer.get("data") or {}).get("entries", [])
    return (
        answer["outcome"] == "ANSWERED"
        and sorted(entry["ref"] for entry in entries) == refs
        and {entry["status"] for entry in entries} == {"RESOLVED"}
    )


def _identity_problems(
    answers: list[tuple[str, str, dict[str, Any]]], version: str, sha: str
) -> list[str]:
    schema = json.loads(ANSWER_SCHEMA.read_text())
    problems = []
    for name, surface, answer in answers:
        producer = answer.get("producer") or {}
        if answer.get("schema_version") != "0.7.1":
            problems.append(f"{name}/{surface}: schema_version {answer.get('schema_version')!r}")
        if producer.get("version") != version:
            problems.append(f"{name}/{surface}: producer.version {producer.get('version')!r}")
        if producer.get("build_revision") != sha:
            problems.append(f"{name}/{surface}: build_revision {producer.get('build_revision')!r}")
        try:
            jsonschema.validate(instance=answer, schema=schema)
        except jsonschema.ValidationError as exc:
            problems.append(f"{name}/{surface}: schema {exc.message[:120]}")
    return problems


def _drive(stack: gp.Stack, password: str, surfaces: Surfaces, checks: dict[str, Any]) -> None:
    def record(check: str, problems: list[str]) -> None:
        checks[check] = {"passed": not problems, "detail": problems}

    record("tools-six", [] if surfaces.tools() == gp.TOOLS else [f"tools/list {surfaces.tools()}"])

    _copy(stack, KAFKA / "declarations", f"{CONTAINER_ROOT}/declarations")
    _copy(stack, KAFKA / "mapping", f"{CONTAINER_ROOT}/mapping")
    _stage_capture(stack, "c1")
    _import(stack)
    topic_ids = _topic_ids(password)
    missing = sorted(set(TOPICS) - set(topic_ids))
    if missing:
        raise gp.HarnessError(f"declared Topics missing from the graph: {missing}")
    problems, answers = _readings("c1", topic_ids, surfaces)
    record("c1-readings", problems)

    evidence = _evidence_request(_query(topic_ids, "orders.created"), answers["orders.created"])
    rest, mcp = surfaces.ask("c1-evidence", evidence)
    record(
        "evidence-same-snapshot",
        [
            *([] if _resolved(rest, evidence["evidence_refs"]) else ["rest: not all resolved"]),
            *([] if _resolved(mcp, evidence["evidence_refs"]) else ["mcp: not all resolved"]),
            *_agree("c1-evidence", rest, mcp),
        ],
    )

    _stage_capture(stack, "c2")
    _import(stack)
    problems, _ = _readings("c2", topic_ids, surfaces)
    record("c2-readings", problems)


def run_destination_consumers_phase(*, image_ref: str, sha: str, out_dir: Path) -> dict[str, Any]:
    output = out_dir / PHASE
    output.mkdir(parents=True, exist_ok=True)
    password = secrets.token_hex(16)
    stack = gp.Stack(
        PHASE, image_ref=image_ref, config_path="golden-path/config.yaml", password=password
    )
    checks: dict[str, Any] = {}
    error = None
    identity: dict[str, Any] = {}
    stack.compose("down", "-v", "--remove-orphans", check=False)
    try:
        stack.compose("up", "-d", "--force-recreate", timeout=600)
        gp._wait(
            "AIP /health", lambda: gp.http("GET", f"{gp.AIP_URL}/health")[0] == 200, timeout=180
        )
        gp._wait(
            "AIP /health/neo4j",
            lambda: gp.http("GET", f"{gp.AIP_URL}/health/neo4j")[0] == 200,
            timeout=120,
        )
        identity = gp._run_identity(stack, image_ref, sha)
        checks["run-identity"] = {
            "passed": identity["running_image_id"] == identity["image_ref_id"]
            and identity["aip_build_revision"] == sha
            and identity["user"] == "app",
            "detail": identity,
        }
        surfaces = Surfaces()
        try:
            _drive(stack, password, surfaces, checks)
        finally:
            problems = _identity_problems(surfaces.answers, gp.package_version(), sha)
            checks["producer-and-schema"] = {"passed": not problems, "detail": problems}
            answers = output / "answers"
            answers.mkdir(exist_ok=True)
            for name, surface, answer in surfaces.answers:
                (answers / f"{name}.{surface}.json").write_text(_canonical(answer) + "\n")
    except (gp.HarnessError, subprocess.TimeoutExpired, jsonschema.ValidationError) as exc:
        error = str(exc)
        (output / "compose-logs.txt").write_text(stack.compose("logs", "--no-color", check=False))
    finally:
        stack.compose("down", "-v", "--remove-orphans", check=False)
    expected = [
        "run-identity",
        "tools-six",
        "c1-readings",
        "evidence-same-snapshot",
        "c2-readings",
        "producer-and-schema",
    ]
    result = {
        "phase": PHASE,
        "image_ref": image_ref,
        "release_candidate_sha": sha,
        "checks": checks,
        "not_run": sorted(set(expected) - set(checks)),
        "error": error,
        "passed": error is None
        and not set(expected) - set(checks)
        and all(c["passed"] for c in checks.values()),
    }
    (output / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: destination_consumers_replay.py <IMAGE_REF> <OUT_DIR>", file=sys.stderr)
        return 2
    image_ref, out_dir = argv[0], Path(argv[1]).resolve()
    sha = os.environ.get("RELEASE_CANDIDATE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print("RELEASE_CANDIDATE_SHA must be a full 40-character lowercase SHA", file=sys.stderr)
        return 2
    busy = [port for port in gp.HOST_PORTS if gp._port_open(port)]
    if busy:
        print(f"host ports already in use: {busy}", file=sys.stderr)
        return 2
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"OUT_DIR is not empty: {out_dir}", file=sys.stderr)
        return 2
    result = run_destination_consumers_phase(image_ref=image_ref, sha=sha, out_dir=out_dir)
    print(json.dumps({k: result[k] for k in ("phase", "passed", "error", "not_run")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
