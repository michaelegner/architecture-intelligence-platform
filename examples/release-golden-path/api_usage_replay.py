"""v0.7.0 I5 §4.5, §5.5, §9.5: the published-artifact APISIX replay harness.

Replays the frozen I4 APISIX package (`docs/specifications/0.7.0/i4-replay/`, revisions R1 then R2)
against one AIP image through its public HTTP boundary only:

    RELEASE_CANDIDATE_SHA=<40-hex> python examples/release-golden-path/api_usage_replay.py <IMAGE_REF> <OUT_DIR>

`golden_path.py` runs the same phase after `locality`. The image must already be present locally
and is never rebuilt. A fresh Compose project and a fresh Neo4j volume are used, the captured files
are copied into the container at one fixed root (so R2 replaces R1 as one source updated in place),
and `POST /api/import` imports them through the production path.

Each frozen case is asked through REST and through an independent negotiated MCP client. Both
answers are compared with the frozen I4 expected reading (`expected-replay.json`, through
`evaluation/i4/apisix_replay.py`) and with each other. Nothing here authors expected truth; a
disagreement is a finding, never a reason to edit the frozen package. Direct in-process service
equality is not re-claimed from outside the image; the exact-candidate I4 A/B run covers it."""

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
sys.path.insert(0, str(HERE.parents[1]))

import golden_path as gp

from evaluation.i4 import apisix_replay as replay

PHASE = "api-usage"
SERVICE = "architecture-intelligence"
CONTAINER_ROOT = "/app/golden-path/api-usage"
R1_CASES = ("P1", "P2", "N1", "N3", "OBS")
R2_CASES = ("REVa", "REVb", "REVc")
ANSWER_SCHEMA = (
    gp.SCHEMA_ROOT / "v0.7" / "api-consumer-usage-answer.schema.json"
)  # the published 0.7 contract
MAX_EVIDENCE_REFS = 20
CONTEXT = ("target", "gateway_instance_id", "environment", "window_start", "window_end")


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
        route = "/api/api-consumer-usage" + ("/evidence" if evidence else "")
        body = {key: value for key, value in request.items() if key != "mode"}
        status, rest = gp.http("POST", f"{gp.AIP_URL}{route}", body)
        if status != 200:
            raise gp.HarnessError(f"REST {route}: {status} {rest}")
        result = self.client.call("get_api_consumer_usage", request)
        if result.get("isError") is not False:
            raise gp.HarnessError(f"MCP get_api_consumer_usage returned isError: {result}")
        mcp = result["structuredContent"]
        self.answers += [(name, "rest", rest), (name, "mcp", mcp)]
        return rest, mcp


def _stage(stack: gp.Stack, revision: str) -> None:
    """Copy the frozen files of one revision over the fixed container root."""
    for part in ("gateway", "metrics"):
        source = replay.REPLAY / revision / part
        target = f"{CONTAINER_ROOT}/{part}"
        stack.compose("exec", "-T", "-u", "root", SERVICE, "mkdir", "-p", target)
        stack.compose("cp", f"{source}/.", f"{SERVICE}:{target}")


def _import(stack: gp.Stack) -> dict[str, Any]:
    status, report = gp.http("POST", f"{gp.AIP_URL}/api/import")
    if status != 200 or report.get("committed") is not True:
        raise gp.HarnessError(f"POST /api/import: {status} {report}")
    return report


def _read_state(password: str) -> dict[str, Any]:
    driver = neo4j.GraphDatabase.driver(gp.NEO4J_BOLT, auth=("neo4j", password))
    try:
        return replay.read_state(driver)
    finally:
        driver.close()


def _refused_as_stale(answer: dict[str, Any]) -> bool:
    return answer["data"] is None and [x["code"] for x in answer["limitations"]] == [
        "SNAPSHOT_NOT_AVAILABLE"
    ]


def _agree(name: str, rest: dict[str, Any], mcp: dict[str, Any]) -> list[str]:
    return [] if _canonical(rest) == _canonical(mcp) else [f"{name}: REST and MCP differ"]


def _reading(case: dict[str, Any], state: dict[str, Any], surfaces: Surfaces, **kw: Any):
    request = replay.request_for(case, state, **kw)
    rest, mcp = surfaces.ask(case["id"], request)
    problems = [
        *(f"rest {p}" for p in replay.reading_problems(case, rest, state)),
        *(f"mcp {p}" for p in replay.reading_problems(case, mcp, state)),
        *_agree(case["id"], rest, mcp),
    ]
    return problems, rest


def _identity_problems(
    answers: list[tuple[str, str, dict[str, Any]]], version: str, sha: str
) -> list[str]:
    schema = json.loads(ANSWER_SCHEMA.read_text())
    problems = []
    for name, surface, answer in answers:
        producer = answer.get("producer") or {}
        if answer.get("schema_version") != "0.7":
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


def _evidence_request(p1_request: dict[str, Any], p1: dict[str, Any]) -> dict[str, Any]:
    page = p1["data"]
    refs = sorted(
        {
            *page["window"]["evidence_refs"],
            *(r for route in page["selected_routes"] for r in route["evidence_refs"]),
            *(r for row in page["rows"] for r in row["evidence_refs"]),
        }
    )[:MAX_EVIDENCE_REFS]
    return {
        "mode": "evidence",
        "snapshot_id": p1["snapshot"]["snapshot_id"],
        "evidence_refs": refs,
        "consumer_id": p1_request["consumer_id"],
        **{key: p1_request[key] for key in CONTEXT},
    }


def _resolved(answer: dict[str, Any]) -> bool:
    return answer["outcome"] == "ANSWERED" and {e["status"] for e in answer["data"]["entries"]} == {
        "RESOLVED"
    }


def _drive(stack: gp.Stack, password: str, surfaces: Surfaces, checks: dict[str, Any]) -> None:
    cases = {case["id"]: case for case in replay.PLAN["cases"]}

    def record(check: str, problems: list[str]) -> None:
        checks[check] = {"passed": not problems, "detail": problems}

    record("tools-five", [] if surfaces.tools() == gp.TOOLS else [f"tools/list {surfaces.tools()}"])

    _stage(stack, "r1")
    _import(stack)
    state1 = _read_state(password)
    problems: list[str] = []
    answers: dict[str, dict[str, Any]] = {}
    for case_id in R1_CASES:
        found, rest = _reading(cases[case_id], state1, surfaces)
        problems += found
        answers[case_id] = rest
    record("replay-r1-readings", problems)

    p1_request = replay.request_for(cases["P1"], state1)
    evidence = _evidence_request(p1_request, answers["P1"])
    rest, mcp = surfaces.ask("EV", evidence)
    record(
        "evidence-same-snapshot",
        [*([] if _resolved(rest) else ["rest: not all resolved"])]
        + ([] if _resolved(mcp) else ["mcp: not all resolved"])
        + _agree("EV", rest, mcp),
    )

    orders = replay.request_for(cases["P1"], state1) | {"limit": 1}
    orders.pop("consumer_id", None)
    _, page_one = gp.http(
        "POST",
        f"{gp.AIP_URL}/api/api-consumer-usage",
        {k: v for k, v in orders.items() if k != "mode"},
    )
    cursor = (page_one["data"] or {}).get("page", {}).get("next_cursor")
    if not cursor:
        raise gp.HarnessError("the R1 Route has no second page; cannot mint a continuation")
    stale_query = {
        **orders,
        "cursor": cursor,
        "snapshot_id": page_one["snapshot"]["snapshot_id"],
    }
    stale_evidence = {**evidence, "snapshot_id": page_one["snapshot"]["snapshot_id"]}

    _stage(stack, "r2")
    _import(stack)
    state2 = _read_state(password)
    removed = replay.route_ids(state1)
    problems = []
    for case_id in R2_CASES:
        found, _ = _reading(cases[case_id], state2, surfaces, removed_routes=removed)
        problems += found
    record("replay-r2-readings", problems)

    problems = []
    for name, request in (("REVd", stale_query), ("REVe", stale_evidence)):
        rest, mcp = surfaces.ask(name, request)
        problems += [
            f"{name}/{s}: not refused as stale"
            for s, a in (("rest", rest), ("mcp", mcp))
            if not _refused_as_stale(a)
        ]
        problems += _agree(name, rest, mcp)
    record("stale-refusals", problems)


def run_api_usage_phase(*, image_ref: str, sha: str, out_dir: Path) -> dict[str, Any]:
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
        "tools-five",
        "replay-r1-readings",
        "evidence-same-snapshot",
        "replay-r2-readings",
        "stale-refusals",
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
        print("usage: api_usage_replay.py <IMAGE_REF> <OUT_DIR>", file=sys.stderr)
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
    result = run_api_usage_phase(image_ref=image_ref, sha=sha, out_dir=out_dir)
    print(json.dumps({k: result[k] for k in ("phase", "passed", "error", "not_run")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
