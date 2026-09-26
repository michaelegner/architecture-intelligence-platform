"""v0.5.0 I6 §7.3-7.4: the release golden-path harness.

Runs the five frozen phases of `examples/release-golden-path/` against one AIP image and compares
each phase with the frozen `expected.json`. `run.sh` is the only entry point:

    RELEASE_CANDIDATE_SHA=<40-hex> examples/release-golden-path/run.sh <IMAGE_REF> <OUT_DIR>

Each phase starts from a clean stack: a fresh Compose project and a fresh anonymous Neo4j volume.
The phase imports through `POST /api/import` and sends its OTLP through the pinned collector. It
then reads through REST and standard negotiated MCP. The `demo` oracle
(`check_fixture_state.py`) and the `pubsub` graph-fact queries read Neo4j in read-only sessions.

Readiness waits are neutral. They wait for health, or for the revision fence to advance and then
settle, never for the expected answer to appear. So a wrong result is a failed check, not a
timeout that hides it. A disagreement with `expected.json` is an I6 §14 finding, never a reason
to edit the frozen profile.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema
import neo4j
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from app.graph.repository import open_session
from app.version import package_version

GP_DIR = REPO / "examples" / "release-golden-path"
COMPOSE_DIR = GP_DIR / "compose"
BASE_COMPOSE = COMPOSE_DIR / "docker-compose.base.yml"
PHASES = ("demo", "pubsub", "k8s-agree", "k8s-conflict", "k8s-unresolved")
AIP_URL = "http://localhost:8000"
COLLECTOR_TRACES_URL = "http://localhost:4318/v1/traces"
NEO4J_BOLT = "bolt://127.0.0.1:17687"
HOST_PORTS = (8000, 4318, 17687)
MCP_PROTOCOL_VERSION = "2025-11-25"
DRIFT_QUALIFICATIONS = ("OBSERVED_ONLY", "NOT_OBSERVED_IN_WINDOW")
TOOLS = ["get_architecture_drift", "get_evidence", "get_service_dependencies"]
SCHEMA_DIR = REPO / "schemas" / "architecture_intelligence" / "v0.5"
SCHEMAS = {
    "dependencies": "architecture-answer.schema.json",
    "drift": "drift-answer.schema.json",
    "evidence": "evidence-answer.schema.json",
}

# Verbatim from tests/integration/test_i4_pubsub_qualification.py:72-91 and :196-202 (the pubsub
# component's own read-only oracle queries). tests/unit/test_release_golden_path_harness.py asserts
# they stay identical.
_IN_SCOPE_RELATIONS = (
    "SENDS",
    "RECEIVES_FROM",
    "PUBLISHES_TO",
    "SUBSCRIPTION_OF",
    "CARRIES",
    "DEAD_LETTERS_TO",
)
FACTS_QUERY = (
    f"MATCH (a)-[r:{'|'.join(_IN_SCOPE_RELATIONS)}]->(b) "
    "RETURN type(r) AS type, labels(a)[0] + ':' + a.name AS source, "
    "labels(b)[0] + ':' + b.name AS target, "
    "any(eid IN coalesce(r.evidence_ids, []) WHERE exists { "
    "MATCH (:Evidence {id: eid, evidence_type: 'OBSERVED'}) }) AS observed"
)
DEAD_LETTER_QUERY = (
    "MATCH (c:SubscriptionDeadLetterConfiguration) "
    "OPTIONAL MATCH (s:Subscription {id: c.subscription_id}) "
    "RETURN s.name AS subscription, c.target_token AS target, c.target_kind_token AS kind"
)
ENTITY_QUERY = "MATCH (n:{label}) RETURN n.name AS name"


class HarnessError(Exception):
    """Infrastructure failure (not a check result): the phase cannot be evaluated."""


# --- compose, docker, http ----------------------------------------------------------------------


def compose_argv(phase: str, *args: str) -> list[str]:
    """The one frozen Compose invocation (I6 §7.4)."""
    return [
        "docker",
        "compose",
        "-p",
        f"gp-{phase}",
        "--project-directory",
        str(REPO),
        "-f",
        str(BASE_COMPOSE),
        "-f",
        str(COMPOSE_DIR / f"{phase}.yml"),
        "--env-file",
        "/dev/null",
        *args,
    ]


class Stack:
    def __init__(self, phase: str, *, image_ref: str, config_path: str, password: str):
        self.phase = phase
        self.env = {k: v for k, v in os.environ.items() if k != "COMPOSE_PROFILES"}
        self.env.update(GP_IMAGE=image_ref, GP_CONFIG_PATH=config_path, GP_NEO4J_PASSWORD=password)

    def compose(self, *args: str, check: bool = True, timeout: float = 300) -> str:
        result = subprocess.run(
            compose_argv(self.phase, *args),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if check and result.returncode != 0:
            raise HarnessError(f"compose {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout

    def exec_aip(self, *command: str) -> str:
        return self.compose("exec", "-T", "architecture-intelligence", *command)


def _docker(*args: str) -> str:
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=60, check=False
    )
    if result.returncode != 0:
        raise HarnessError(f"docker {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def http(method: str, url: str, body: Any = None, headers: dict | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("content-type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else None
        except json.JSONDecodeError:
            return exc.code, raw.decode(errors="replace")


def _wait(description: str, probe: Callable[[], bool], *, timeout: float, interval: float = 2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if probe():
                return
        except (OSError, urllib.error.URLError, HarnessError):
            pass
        time.sleep(interval)
    raise HarnessError(f"timed out waiting for {description}")


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


# --- negotiated MCP (the request shapes of tests/integration/independent_mcp_client.py) ---------


class McpClient:
    """A fresh client is a fresh negotiated lifecycle. The server is stateless, so reconnecting
    means initializing again."""

    def __init__(self):
        self._id = 0
        status, body = self._post(
            {
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "aip-release-golden-path", "version": "1"},
                },
            },
            with_version=False,
        )
        if status != 200 or body["result"]["protocolVersion"] != MCP_PROTOCOL_VERSION:
            raise HarnessError(f"MCP initialize failed: {status} {body}")
        self.initialize_result = body["result"]
        status, _ = self._post({"method": "notifications/initialized"}, notification=True)
        if status not in (200, 202):
            raise HarnessError(f"MCP notifications/initialized failed: {status}")

    def _post(self, message: dict, *, with_version: bool = True, notification: bool = False):
        payload = {"jsonrpc": "2.0", **message}
        if not notification:
            self._id += 1
            payload["id"] = self._id
        headers = {"accept": "application/json, text/event-stream"}
        if with_version:
            headers["mcp-protocol-version"] = MCP_PROTOCOL_VERSION
        return http("POST", f"{AIP_URL}/mcp", payload, headers)

    def tools_list(self) -> list[str]:
        status, body = self._post({"method": "tools/list", "params": {}})
        if status != 200:
            raise HarnessError(f"tools/list failed: {status} {body}")
        return [tool["name"] for tool in body["result"]["tools"]]

    def call(self, name: str, request: dict) -> dict:
        status, body = self._post(
            {"method": "tools/call", "params": {"name": name, "arguments": {"request": request}}}
        )
        if status != 200:
            raise HarnessError(f"tools/call {name} failed: {status} {body}")
        return body["result"]


# --- the phase context ---------------------------------------------------------------------------


class Phase:
    def __init__(self, name: str, stack: Stack, expected: dict, out_dir: Path, *, sha: str):
        self.name = name
        self.stack = stack
        self.expected = expected
        self.out_dir = out_dir
        self.sha = sha
        spec = yaml.safe_load((GP_DIR / "profile" / name / "phase.yaml").read_text())
        self.context = spec["observation_context"]
        self.answers: list[dict] = []
        self.records: dict[str, Any] = {}

    def record(self, key: str, value: Any) -> Any:
        self.records[key] = value
        (self.out_dir / f"{key}.json").write_text(json.dumps(value, indent=2, sort_keys=True))
        return value

    def request(self, service_id: str) -> dict:
        return {"service_id": service_id, "observation_context": dict(self.context)}

    def rest(self, kind: str, service_id: str) -> dict:
        query = urllib.parse.urlencode(
            {
                "environment": self.context["environment"],
                "from": self.context["window_start"],
                "to": self.context["window_end"],
            }
        )
        status, body = http("GET", f"{AIP_URL}/api/services/{service_id}/{kind}?{query}")
        if status != 200:
            raise HarnessError(f"GET {kind} {service_id}: {status} {body}")
        if kind != "deployments":
            self.answers.append(body)
        return body

    def rest_evidence(self, evidence_refs: list[str], snapshot_id: str) -> dict:
        status, body = http(
            "POST",
            f"{AIP_URL}/api/evidence/resolve",
            {"evidence_refs": evidence_refs, "snapshot_id": snapshot_id},
        )
        if status != 200:
            raise HarnessError(f"POST evidence/resolve: {status} {body}")
        self.answers.append(body)
        return body

    def mcp(self, client: McpClient, name: str, request: dict) -> dict:
        result = client.call(name, request)
        if result.get("isError") is not False:
            raise HarnessError(f"MCP {name} returned isError: {result}")
        self.answers.append(result["structuredContent"])
        return result["structuredContent"]

    def fence(self) -> int | None:
        return json.loads(
            self.stack.exec_aip("python", "examples/runtime-demo/read_revision_fence.py", "--json")
        )["revision"]

    def fixture_state(self) -> dict:
        return json.loads(
            self.stack.exec_aip("python", "examples/runtime-demo/check_fixture_state.py", "--json")
        )


# --- pure comparisons (unit-tested) --------------------------------------------------------------


def project_drift_claims(answer: dict) -> list[dict]:
    """JSON twin of examples/runtime-demo/check_fixture_state.py:251-267 `project_drift_claims`."""
    if answer["outcome"] == "NOT_ANSWERED":
        return []
    claims = [
        {
            "subject": claim["subject"]["id"],
            "target": claim["object"]["name"],
            "via": claim["delivery"]["via"]["name"],
            "qualification": claim["qualification"],
            "evidence_refs": sorted(claim["evidence_refs"]),
        }
        for claim in answer["claims"]
    ]
    return sorted(claims, key=lambda c: (c["target"], c["qualification"]))


def claim_shape(claim: dict) -> list:
    """Verbatim from tests/integration/test_i4_pubsub_qualification.py:241-249 `_claim_shape`."""
    object_ref, delivery = claim["object"], claim["delivery"]
    return [
        f"{object_ref['type'].title()}:{object_ref['name']}",
        f"{delivery['via']['type'].title()}:{delivery['via']['name']}",
        delivery["subscription"]["name"] if delivery["subscription"] else None,
        claim["destination_resolution"],
        claim["qualification"],
    ]


def answer_refs(answer: dict) -> list[str]:
    """Verbatim logic of tests/integration/test_i4_pubsub_qualification.py:144-148 `_answer_refs`."""
    refs = set(answer["evidence_refs"])
    for claim in answer["claims"]:
        refs.update(claim["evidence_refs"])
        refs.update(claim["resolution_evidence_refs"])
    return sorted(refs)


def drift_subset(dependencies: dict) -> list[dict]:
    return [c for c in dependencies["claims"] if c["qualification"] in DRIFT_QUALIFICATIONS]


def deployment_claims(answer: dict) -> list[dict]:
    return [c for c in answer["claims"] if c.get("predicate") == "DEPLOYED_AS"]


def source_results_by_slug(report: dict) -> dict[str, dict]:
    """Keyed like test_i4_pubsub_qualification.py:168-178: the parent directory of each locator."""
    return {
        Path(result["locator"]).parent.name: {
            "result": result["result"],
            "diagnostics": sorted([d["code"], d["source_pointer"]] for d in result["diagnostics"]),
        }
        for run in report["runs"]
        for result in run["source_results"]
    }


def producer_identity_mismatches(answers: list[dict], *, version: str, sha: str) -> list[str]:
    problems = []
    for index, answer in enumerate(answers):
        producer = answer.get("producer") or {}
        if answer.get("schema_version") != "0.5":
            problems.append(f"answer {index}: schema_version {answer.get('schema_version')!r}")
        if producer.get("version") != version:
            problems.append(f"answer {index}: producer.version {producer.get('version')!r}")
        if producer.get("build_revision") != sha:
            problems.append(f"answer {index}: build_revision {producer.get('build_revision')!r}")
    return problems


def validate_schema(kind: str, answer: dict) -> None:
    schema = json.loads((SCHEMA_DIR / SCHEMAS[kind]).read_text())
    jsonschema.validate(instance=answer, schema=schema)


# --- checks ---------------------------------------------------------------------------------------

Result = tuple[bool, Any]


def _eq(actual: Any, expected: Any) -> Result:
    return actual == expected, {"actual": actual, "expected": expected}


def check_import_demo(p: Phase) -> Result:
    report = p.records["import"]
    [run] = report["runs"]
    actual = {
        "committed": report["committed"],
        "sources_count": len(report["sources"]),
        "report_version": report["report_version"],
        "run": [run["inventory_status"], run["committed"]],
        "source_result_ids_match": {r["source_instance_id"] for r in run["source_results"]}
        == set(report["sources"]),
    }
    return _eq(
        actual,
        {
            "committed": True,
            "sources_count": 6,
            "report_version": "aip-import-report/1",
            "run": ["COMPLETE", True],
            "source_result_ids_match": True,
        },
    )


def check_import_pubsub(p: Phase) -> Result:
    report = p.records["import"]
    [run] = report["runs"]
    expect = p.expected["checks"]["import"]["expect"]
    actual = {
        "committed": report["committed"],
        "inventory_status": run["inventory_status"],
        "sources": source_results_by_slug(report),
    }
    return _eq(
        actual,
        {
            "committed": expect["committed"],
            "inventory_status": expect["inventory_status"],
            "sources": expect["sources"],
        },
    )


def check_import_k8s(p: Phase) -> Result:
    report = p.records["import"]
    runs = {run["kind"]: run for run in report["runs"]}
    fs, k8s = runs.get("filesystem"), runs.get("kubernetes")
    actual = {
        "committed": report["committed"],
        "report_version": report["report_version"],
        "run_kinds": sorted(runs),
        "filesystem": [
            fs["inventory_status"],
            fs["committed"],
            sorted({r["result"] for r in fs["source_results"]}),
            [d for r in fs["source_results"] for d in r["diagnostics"]],
        ]
        if fs
        else None,
        "kubernetes": [
            k8s["configured_source_id"],
            k8s["inventory_status"],
            k8s["committed"],
            sorted({r["result"] for r in k8s["source_results"]}),
            [d for r in k8s["source_results"] for d in r["diagnostics"]],
        ]
        if k8s
        else None,
    }
    return _eq(
        actual,
        {
            "committed": True,
            "report_version": "aip-import-report/1",
            "run_kinds": ["filesystem", "kubernetes"],
            "filesystem": ["COMPLETE", True, ["ACCEPTED"], []],
            "kubernetes": ["aip-i2-independent-capture", "COMPLETE", True, ["ACCEPTED"], []],
        },
    )


def check_fixture_state(p: Phase) -> Result:
    state = p.records["fixture_state"]
    expect = p.expected["checks"]["fixture-state"]["expect"]
    return _eq(
        {k: state[k] for k in ("classification", "mismatches", "actual_snapshot_id")},
        {k: expect[k] for k in ("classification", "mismatches", "actual_snapshot_id")},
    )


def check_drift_demo(p: Phase) -> Result:
    manifest = json.loads((REPO / "examples/runtime-demo/fixture-state.json").read_text())
    rest, mcp = p.records["drift_rest"], p.records["drift_mcp"]
    snapshot = p.records["fixture_state"]["actual_snapshot_id"]
    return _eq(
        {
            "rest": project_drift_claims(rest),
            "mcp": project_drift_claims(mcp),
            "snapshots": [rest["snapshot"]["snapshot_id"], mcp["snapshot"]["snapshot_id"]],
        },
        {
            "rest": manifest["expected_drift_claims"],
            "mcp": manifest["expected_drift_claims"],
            "snapshots": [snapshot, snapshot],
        },
    )


def check_dependencies_demo(p: Phase) -> Result:
    deps, drift = p.records["dependencies_rest"], p.records["drift_rest"]
    snapshot = p.records["fixture_state"]["actual_snapshot_id"]
    return _eq(
        {"drift_claims": drift["claims"], "snapshot": deps["snapshot"]["snapshot_id"]},
        {"drift_claims": drift_subset(deps), "snapshot": snapshot},
    )


def _evidence_ok(*answers: dict) -> Result:
    actual = [[a["outcome"], a["data"]["missing_evidence_refs"]] for a in answers]
    return _eq(actual, [["ANSWERED", []] for _ in answers])


def check_evidence_demo(p: Phase) -> Result:
    return _evidence_ok(p.records["evidence_rest"], p.records["evidence_mcp"])


def check_mcp_tools(p: Phase) -> Result:
    return _eq(p.records["tools"], TOOLS)


def check_cross_surface(p: Phase) -> Result:
    pairs = p.records["cross_surface_pairs"]
    return _eq(
        {name: p.records[f"{name}_rest"] == p.records[f"{name}_mcp"] for name in pairs},
        {name: True for name in pairs},
    )


def check_reconnect(p: Phase) -> Result:
    first, again = p.records["dependencies_rest"], p.records["dependencies_reconnect"]
    return _eq(
        {"claims": again["claims"], "snapshot": again["snapshot"]["snapshot_id"]},
        {"claims": first["claims"], "snapshot": first["snapshot"]["snapshot_id"]},
    )


def check_zero_writes(p: Phase) -> Result:
    before, after = p.records["fence_before"], p.records["fence_after"]
    return (before is not None and before == after), {"before": before, "after": after}


def check_fixture_state_after(p: Phase) -> Result:
    before, after = p.records["fixture_state"], p.records["fixture_state_after"]
    return _eq(
        [after["classification"], after["actual_snapshot_id"]],
        ["COMPLETE", before["actual_snapshot_id"]],
    )


def check_producer_identity(p: Phase) -> Result:
    problems = producer_identity_mismatches(p.answers, version=package_version(), sha=p.sha)
    return (not problems and bool(p.answers)), {"answers": len(p.answers), "problems": problems}


def check_graph_facts(p: Phase) -> Result:
    expect = p.expected["checks"]["graph-facts"]["expect"]
    actual = p.records["graph_facts"]
    return _eq(
        actual,
        {
            "facts": sorted(expect["facts"]),
            "observed": sorted(expect["observed"]),
            "entities": expect["entities"],
            "dead_letter_carriers": sorted(expect["dead_letter_carriers"]),
        },
    )


def check_answers_pubsub(p: Phase) -> Result:
    expect = p.expected["checks"]["answers"]["expect"]
    actual, wanted = {}, {}
    for slug in ("checkout", "fulfillment", "analytics"):
        deps, drift = p.records[f"{slug}_dependencies"], p.records[f"{slug}_drift"]
        evidence = p.records.get(f"{slug}_evidence")
        actual[slug] = {
            "claims": sorted(claim_shape(c) for c in deps["claims"]),
            "limitations": sorted(lim["code"] for lim in deps["limitations"]),
            "drift_is_subset": drift["claims"] == drift_subset(deps),
            "missing_evidence_refs": None
            if evidence is None
            else evidence["data"]["missing_evidence_refs"],
        }
        wanted[slug] = {
            "claims": sorted(expect[slug]["claims"]),
            "limitations": sorted(expect[slug]["limitations"]),
            "drift_is_subset": True,
            "missing_evidence_refs": None if evidence is None else [],
        }
    return _eq(actual, wanted)


def check_deployment_agree(p: Phase) -> Result:
    mcp, rest = p.records["deployment_mcp"], p.records["deployment_rest"]
    [claim] = deployment_claims(mcp) or [None]
    data = mcp.get("data") or {}
    actual = {
        "outcome": mcp["outcome"],
        "deployment_claim_count": len(data.get("deployment_claim_ids", [])),
        "dependency_claim_ids": data.get("dependency_claim_ids"),
        "resolutions": [
            {
                "status": r["status"],
                "service_id": r["service_id"],
                "workload.name": (r["workload"] or {}).get("name"),
            }
            for r in data.get("deployment_resolutions", [])
        ],
        "deployment_claim": None
        if claim is None
        else {
            "resolution_method": claim["resolution_method"],
            "supporting_methods": claim["supporting_methods"],
            "evidence_ref_prefixes": [
                prefix
                for prefix in ("evidence:kubernetes:", "evidence:mapping:", "evidence:otel:")
                if any(ref.startswith(prefix) for ref in claim["evidence_refs"])
            ],
        },
        "rest_matches_mcp": [
            rest["deployment_resolutions"] == data.get("deployment_resolutions"),
            rest["deployment_claims"] == deployment_claims(mcp),
        ],
    }
    wanted = dict(p.expected["checks"]["deployment"]["expect"])
    wanted["rest_matches_mcp"] = [True, True]
    return _eq(actual, wanted)


def check_evidence_agree(p: Phase) -> Result:
    return _eq(
        [
            p.records["evidence_rest"]["data"]["missing_evidence_refs"],
            p.records["evidence_rest"] == p.records["evidence_mcp"],
        ],
        [[], True],
    )


def check_deployment_conflict(p: Phase) -> Result:
    each = p.expected["checks"]["deployment"]["expect"]["each"]
    actual, wanted = {}, {}
    for service_id in ("service:runtime-demo", "service:runtime-demo-alt"):
        mcp, rest = p.records[f"{service_id}_mcp"], p.records[f"{service_id}_rest"]
        data = mcp.get("data") or {}
        actual[service_id] = {
            "outcome": mcp["outcome"],
            "deployment_claim_ids": data.get("deployment_claim_ids"),
            "resolutions": [
                {"status": r["status"], "candidate_service_ids": r["candidate_service_ids"]}
                for r in data.get("deployment_resolutions", [])
            ],
            "deployment_claims": deployment_claims(mcp),
            "rest_matches_mcp": rest["deployment_resolutions"] == data.get("deployment_resolutions")
            and rest["deployment_claims"] == [],
        }
        wanted[service_id] = {**each, "rest_matches_mcp": True}
    return _eq(actual, wanted)


def check_deployment_unresolved(p: Phase) -> Result:
    mcp, rest = p.records["deployment_mcp"], p.records["deployment_rest"]
    resolutions = (mcp.get("data") or {}).get("deployment_resolutions", [])
    unresolved = [r for r in resolutions if r["service_id"] is None and r["workload"] is None]
    expect = p.expected["checks"]["deployment"]["expect"]["unresolved_resolutions"]
    return _eq(
        {
            "count": len(unresolved),
            "distinct_resolution_ids": len({r["resolution_id"] for r in unresolved}),
            "statuses": sorted({r["status"] for r in unresolved}),
            "rest_matches_mcp": rest["deployment_resolutions"] == resolutions,
        },
        {
            "count": expect["count"],
            "distinct_resolution_ids": expect["distinct_resolution_ids"],
            "statuses": ["UNRESOLVED"],
            "rest_matches_mcp": True,
        },
    )


CHECKS: dict[str, dict[str, Callable[[Phase], Result]]] = {
    "demo": {
        "import": check_import_demo,
        "fixture-state": check_fixture_state,
        "drift": check_drift_demo,
        "dependencies": check_dependencies_demo,
        "evidence": check_evidence_demo,
        "mcp-tools": check_mcp_tools,
        "cross-surface": check_cross_surface,
        "reconnect": check_reconnect,
        "zero-writes": check_zero_writes,
        "fixture-state-after": check_fixture_state_after,
        "producer-identity": check_producer_identity,
    },
    "pubsub": {
        "import": check_import_pubsub,
        "graph-facts": check_graph_facts,
        "answers": check_answers_pubsub,
        "mcp-tools": check_mcp_tools,
        "cross-surface": check_cross_surface,
        "zero-writes": check_zero_writes,
        "producer-identity": check_producer_identity,
    },
    "k8s-agree": {
        "import": check_import_k8s,
        "deployment": check_deployment_agree,
        "evidence": check_evidence_agree,
        "zero-writes": check_zero_writes,
        "producer-identity": check_producer_identity,
    },
    "k8s-conflict": {
        "import": check_import_k8s,
        "deployment": check_deployment_conflict,
        "zero-writes": check_zero_writes,
        "producer-identity": check_producer_identity,
    },
    "k8s-unresolved": {
        "import": check_import_k8s,
        "deployment": check_deployment_unresolved,
        "zero-writes": check_zero_writes,
        "producer-identity": check_producer_identity,
    },
}


# --- phase drivers (collect records; the checks above judge them) ---------------------------------


def _wait_for_revision_to_settle(p: Phase, previous: int | None) -> None:
    """Neutral readiness: the fence advanced past `previous`, then held for two reads."""
    last: list[int | None] = [None]

    def settled() -> bool:
        current = p.fence()
        stable = current is not None and current != previous and current == last[0]
        last[0] = current
        return stable

    _wait("the revision fence to advance and settle", settled, timeout=90, interval=3)


def _post_otlp(p: Phase, relative: str) -> None:
    before = p.fence()
    status, body = http("POST", COLLECTOR_TRACES_URL, json.loads((REPO / relative).read_text()))
    if status != 200:
        raise HarnessError(f"collector rejected {relative}: {status} {body}")
    _wait_for_revision_to_settle(p, before)


def drive_demo(p: Phase) -> None:
    before = p.fence()
    env = {
        **os.environ,
        "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4318",
        "AIP_BASE_URL": AIP_URL,
        "DEMO_ENVIRONMENT": p.context["environment"],
    }
    seed = subprocess.run(
        [sys.executable, str(REPO / "examples/runtime-demo/seed_frozen_evidence.py")],
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if seed.returncode != 0:
        raise HarnessError(f"seed_frozen_evidence.py failed: {seed.stderr.strip()}")
    _wait_for_revision_to_settle(p, before)
    p.record("fixture_state", p.fixture_state())

    p.record("fence_before", p.fence())
    client = McpClient()
    p.record("tools", client.tools_list())
    service = "service:order-service"
    p.record("drift_rest", p.rest("drift", service))
    p.record("drift_mcp", p.mcp(client, "get_architecture_drift", p.request(service)))
    p.record("dependencies_rest", p.rest("dependencies", service))
    p.record("dependencies_mcp", p.mcp(client, "get_service_dependencies", p.request(service)))
    drift = p.records["drift_rest"]
    evidence_request = {
        "evidence_refs": drift["evidence_refs"],
        "snapshot_id": drift["snapshot"]["snapshot_id"],
    }
    p.record("evidence_rest", p.rest_evidence(**evidence_request))
    p.record("evidence_mcp", p.mcp(client, "get_evidence", evidence_request))
    p.record("cross_surface_pairs", ["drift", "dependencies", "evidence"])
    reconnected = McpClient()
    p.record(
        "dependencies_reconnect", p.mcp(reconnected, "get_service_dependencies", p.request(service))
    )
    p.record("fence_after", p.fence())
    p.record("fixture_state_after", p.fixture_state())


def drive_pubsub(p: Phase) -> None:
    _post_otlp(p, "examples/release-golden-path/profile/pubsub/otlp.json")
    p.record("fence_before", p.fence())
    # The component's query names relationship types absent from this graph; the server's
    # "type does not exist" notices are expected, so they are not logged.
    driver = neo4j.GraphDatabase.driver(
        NEO4J_BOLT,
        auth=("neo4j", p.stack.env["GP_NEO4J_PASSWORD"]),
        notifications_min_severity="OFF",
    )
    try:
        with open_session(driver, database="neo4j", read_only=True) as session:
            rows = [record.data() for record in session.run(FACTS_QUERY)]
            entities = {
                label: sorted(r["name"] for r in session.run(ENTITY_QUERY.format(label=label)))
                for label in ("Queue", "Topic", "Subscription")
            }
            dead_letters = sorted(
                [r["subscription"], r["target"], r["kind"]] for r in session.run(DEAD_LETTER_QUERY)
            )
    finally:
        driver.close()
    p.record(
        "graph_facts",
        {
            "facts": sorted([r["type"], r["source"], r["target"]] for r in rows),
            "observed": sorted(
                [r["type"], r["source"], r["target"]] for r in rows if r["observed"]
            ),
            "entities": entities,
            "dead_letter_carriers": dead_letters,
        },
    )
    for slug in ("checkout", "fulfillment", "analytics"):
        service = f"service:{slug}"
        deps = p.record(f"{slug}_dependencies", p.rest("dependencies", service))
        drift = p.record(f"{slug}_drift", p.rest("drift", service))
        validate_schema("dependencies", deps)
        validate_schema("drift", drift)
        refs = answer_refs(deps)
        if refs:
            evidence = p.record(
                f"{slug}_evidence", p.rest_evidence(refs, deps["snapshot"]["snapshot_id"])
            )
            validate_schema("evidence", evidence)
    client = McpClient()
    p.record("tools", client.tools_list())
    checkout = p.request("service:checkout")
    p.record("dependencies_rest", p.records["checkout_dependencies"])
    p.record("drift_rest", p.records["checkout_drift"])
    p.record("dependencies_mcp", p.mcp(client, "get_service_dependencies", checkout))
    p.record("drift_mcp", p.mcp(client, "get_architecture_drift", checkout))
    pairs = ["dependencies", "drift"]
    if "checkout_evidence" in p.records:
        deps = p.records["checkout_dependencies"]
        p.record("evidence_rest", p.records["checkout_evidence"])
        p.record(
            "evidence_mcp",
            p.mcp(
                client,
                "get_evidence",
                {
                    "evidence_refs": answer_refs(deps),
                    "snapshot_id": deps["snapshot"]["snapshot_id"],
                },
            ),
        )
        pairs.append("evidence")
    p.record("cross_surface_pairs", pairs)
    p.record("fence_after", p.fence())


def _deployment_reads(p: Phase, client: McpClient, service_id: str, key: str) -> None:
    p.record(f"{key}_rest", p.rest("deployments", service_id))
    p.record(f"{key}_mcp", p.mcp(client, "get_service_dependencies", p.request(service_id)))


def drive_k8s_agree(p: Phase) -> None:
    _post_otlp(p, "examples/release-golden-path/profile/k8s-agree/otlp.json")
    p.record("fence_before", p.fence())
    client = McpClient()
    _deployment_reads(p, client, "service:runtime-demo", "deployment")
    mcp = p.records["deployment_mcp"]
    [claim] = deployment_claims(mcp) or [{"evidence_refs": []}]
    request = {
        "evidence_refs": sorted(claim["evidence_refs"]),
        "snapshot_id": mcp["snapshot"]["snapshot_id"],
    }
    p.record("evidence_rest", p.rest_evidence(**request))
    p.record("evidence_mcp", p.mcp(client, "get_evidence", request))
    p.record("fence_after", p.fence())


def drive_k8s_conflict(p: Phase) -> None:
    p.record("fence_before", p.fence())
    client = McpClient()
    for service_id in ("service:runtime-demo", "service:runtime-demo-alt"):
        _deployment_reads(p, client, service_id, service_id)
    p.record("fence_after", p.fence())


def drive_k8s_unresolved(p: Phase) -> None:
    p.record("fence_before", p.fence())
    client = McpClient()
    _deployment_reads(p, client, "service:runtime-demo", "deployment")
    p.record("fence_after", p.fence())


DRIVERS: dict[str, Callable[[Phase], None]] = {
    "demo": drive_demo,
    "pubsub": drive_pubsub,
    "k8s-agree": drive_k8s_agree,
    "k8s-conflict": drive_k8s_conflict,
    "k8s-unresolved": drive_k8s_unresolved,
}


# --- orchestration -------------------------------------------------------------------------------


def _run_identity(stack: Stack, image_ref: str, sha: str) -> dict:
    container = stack.compose("ps", "-q", "architecture-intelligence").strip()
    return {
        "running_image_id": _docker("inspect", "--format", "{{.Image}}", container),
        "image_ref_id": _docker("image", "inspect", "--format", "{{.Id}}", image_ref),
        "aip_build_revision": stack.exec_aip("printenv", "AIP_BUILD_REVISION").strip(),
        "user": stack.exec_aip("whoami").strip(),
        "expected_build_revision": sha,
    }


def run_phase(name: str, *, image_ref: str, sha: str, expected: dict, out_dir: Path) -> dict:
    phase_out = out_dir / name
    phase_out.mkdir(parents=True)
    spec = yaml.safe_load((GP_DIR / "profile" / name / "phase.yaml").read_text())
    stack = Stack(
        name, image_ref=image_ref, config_path=spec["config_path"], password=secrets.token_hex(16)
    )
    phase = Phase(name, stack, expected, phase_out, sha=sha)
    checks: dict[str, dict] = {}
    error = None
    stack.compose("down", "-v", "--remove-orphans", check=False)
    try:
        stack.compose("up", "-d", "--force-recreate", timeout=600)
        _wait("AIP /health", lambda: http("GET", f"{AIP_URL}/health")[0] == 200, timeout=180)
        _wait(
            "AIP /health/neo4j",
            lambda: http("GET", f"{AIP_URL}/health/neo4j")[0] == 200,
            timeout=120,
        )
        _wait("the collector on 4318", lambda: _port_open(4318), timeout=60)
        identity = phase.record("run_identity", _run_identity(stack, image_ref, sha))
        checks["run-identity"] = {
            "passed": identity["running_image_id"] == identity["image_ref_id"]
            and identity["aip_build_revision"] == sha
            and identity["user"] == "app",
            "detail": identity,
        }
        status, report = http("POST", f"{AIP_URL}/api/import")
        if status != 200:
            raise HarnessError(f"POST /api/import: {status} {report}")
        phase.record("import", report)
        DRIVERS[name](phase)
        for check_id, check in CHECKS[name].items():
            try:
                passed, detail = check(phase)
            except (KeyError, TypeError, ValueError, jsonschema.ValidationError) as exc:
                passed, detail = False, {"error": repr(exc)}
            checks[check_id] = {"passed": bool(passed), "detail": detail}
    except (HarnessError, subprocess.TimeoutExpired, jsonschema.ValidationError) as exc:
        error = str(exc)
        (phase_out / "compose-logs.txt").write_text(
            stack.compose("logs", "--no-color", check=False)
        )
    finally:
        stack.compose("down", "-v", "--remove-orphans", check=False)
    missing = sorted(set(CHECKS[name]) - set(checks))
    result = {
        "phase": name,
        "passed": error is None and not missing and all(c["passed"] for c in checks.values()),
        "error": error,
        "not_run": missing,
        "checks": checks,
    }
    (phase_out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True))
    return result


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: golden_path.py <IMAGE_REF> <OUT_DIR>", file=sys.stderr)
        return 2
    image_ref, out_dir = argv[0], Path(argv[1]).resolve()
    sha = os.environ.get("RELEASE_CANDIDATE_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        print("RELEASE_CANDIDATE_SHA must be a full 40-character lowercase SHA", file=sys.stderr)
        return 2
    busy = [port for port in HOST_PORTS if _port_open(port)]
    if busy:
        print(f"host ports already in use: {busy}", file=sys.stderr)
        return 2
    expected = json.loads((GP_DIR / "expected.json").read_text())["phases"]
    for name in PHASES:
        expected[name]["checks"] = {c["id"]: c for c in expected[name]["checks"]}
    results = [
        run_phase(name, image_ref=image_ref, sha=sha, expected=expected[name], out_dir=out_dir)
        for name in PHASES
    ]
    summary = {
        "image_ref": image_ref,
        "release_candidate_sha": sha,
        "package_version": package_version(),
        "passed": all(r["passed"] for r in results),
        "phases": {
            r["phase"]: {
                "passed": r["passed"],
                "error": r["error"],
                "failed_checks": sorted(k for k, c in r["checks"].items() if not c["passed"]),
            }
            for r in results
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
