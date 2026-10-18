"""One run (A or B) of the v0.7 qualification (I4 spec §3, §4, §7; decision record D1, D8).

    python -m evaluation.i4.api_usage_runner --candidate-sha <sha> --run A --out <dir>

It verifies the candidate, then, in one process and without normalizing any payload:
1. executes every answer case of the frozen I3 oracle and of the I4 bridge vector through the
   service, REST and negotiated MCP, and checks each surface's answer against the independently
   frozen expected answer (the I3 matrix §2 matching);
2. executes every request-validation case through REST (422) and negotiated MCP (tool error);
3. checks the property cases over the actual answers;
4. against a fresh disposable Neo4j, imports a generated APISIX configuration and measurement source
   through the production import path and asks the same questions of the real service, REST,
   negotiated MCP and an httpx-only client over real HTTP (query, a cursor continuation, evidence
   and a reconnect, plus a stale-snapshot refusal).

It writes `ledger.json` (the `i4-ledger/1` schema of the v0.6 plugin, plus `profile`) and the raw
canonical bytes of every answer under `bytes/`. The comparator (`evaluation.i4.__main__`) decides
equality; this module only records. `--development` records local checks that can never qualify.
The oracle cases need no database, so the Neo4j-backed step is where the container identity and the
clean-state proof come from; the I4.1c replay package joins that step.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
import re
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from mcp.server import MCPServer

import app.main
from app.api import api_consumer_usage, errors
from app.architecture_intelligence.api_usage_contracts import (
    API_USAGE_TOOL_NAME,
    ApiConsumerUsageEvidenceRequest,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.api_usage_evidence import resolve_api_consumer_usage_evidence
from app.architecture_intelligence.api_usage_projection import project_api_consumer_usage
from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Producer, SnapshotRef
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.deps import get_architecture_intelligence_service
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.version import package_version
from benchmarks import api_usage_cost
from evaluation.i4.__main__ import ROOT, verify_candidate
from evaluation.i4.profiles import V07
from tests.api_usage_oracle.matcher import first_difference
from tests.api_usage_oracle.properties import check_property
from tests.integration import independent_mcp_client
from tests.integration.support.live_server import free_loopback_port, serve_over_real_http
from tests.support.negotiated_mcp_client import call_negotiated

SPEC = ROOT / "docs/specifications/0.7.0"
ORIGIN = "http://localhost"
DATABASE = "neo4j"
ROUTES = {"query": "/api/api-consumer-usage", "evidence": "/api/api-consumer-usage/evidence"}
SCHEMA = "i4-ledger/1"
# The generated real-import world: small, but with more rows than one page of the questions below.
REAL_POINT = api_usage_cost.Point(
    "i4-real-import", consumers=12, routes=4, whitelist=5, observed=2, extra=1
)
REAL_PAGE = 10


def _pins() -> dict[str, str]:
    roots = [
        SPEC,
        ROOT / "schemas/architecture_intelligence",
        ROOT / "tests/api_usage_oracle",
        ROOT / "evaluation/i4",
        ROOT / "benchmarks",
    ]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def _register_keys() -> dict[str, list[str]]:
    keys: dict[str, list[str]] = {}
    for line in V07.register.read_text().splitlines():
        if line.startswith("| S22-"):
            key = line.split("|")[1].strip()
            for case in re.findall(r"`([AEVBKC]\d\d[a-c]?)`", line.split("|")[3]):
                keys.setdefault(case, []).append(key)
    return keys


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


class Recorder:
    """Writes canonical answer bytes and the ledger; it normalizes nothing."""

    def __init__(self, out: Path, sha: str, run: str, development: bool) -> None:
        self.out, self.sha, self.run = out, sha, run
        self.records: list[dict[str, Any]] = []
        self.resets: list[dict[str, Any]] = []
        self.pins = _pins()
        self.register = _register_keys()
        self.ledger: dict[str, Any] = {
            "schema": SCHEMA,
            "profile": V07.name,
            "run": run,
            "candidate_sha": sha,
            "head": sha,
            "producer_version": package_version(),
            "qualification_eligible": not development,
            "process_id": os.getpid(),
            "container_id": None,
            "runtime": {"python": platform.python_version(), "platform": platform.platform()},
            "input_pins": self.pins,
            "command": sys.argv,
            "configuration": {"I4_CANDIDATE_SHA": sha, "AIP_BUILD_REVISION": sha},
        }

    def write(
        self,
        payload: Any,
        *,
        surface: str,
        comparison_key: str,
        case_id: str,
        request: Any,
        oracle_match: bool | None,
        classification: str,
    ) -> None:
        raw = canonical_json_bytes(payload)
        key = f"{comparison_key}/{surface}"
        relative = "bytes/" + hashlib.sha256(key.encode()).hexdigest() + ".json"
        target = self.out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), f"duplicate capture key: {key}"
        target.write_bytes(raw)
        producer = payload.get("producer") if isinstance(payload, dict) else None
        self.records.append(
            {
                "key": key,
                "comparison_key": comparison_key,
                "case_id": case_id,
                "register_keys": self.register.get(case_id, []),
                "state": comparison_key.rsplit("/", 1)[-1],
                "surface": surface,
                "candidate_sha": self.sha,
                "head": self.sha,
                "producer_build_revision": (producer or {}).get("build_revision"),
                "request": request,
                "canonical_digest": hashlib.sha256(raw).hexdigest(),
                "bytes_ref": relative,
                "oracle_match": oracle_match,
                "classification": classification,
                "skipped": False,
                "run": self.run,
                "process_id": self.ledger["process_id"],
                "container_id": self.ledger["container_id"],
                "input_digest": _digest(self.pins),
                "oracle_digest": _digest({k: v for k, v in self.pins.items() if "vectors/" in k}),
                "schema_digest": _digest(
                    {k: v for k, v in self.pins.items() if k.startswith("schemas/")}
                ),
                "config_digest": _digest(self.ledger["configuration"]),
            }
        )

    def finish(self, exit_code: int, development: bool) -> None:
        try:
            verify_candidate(self.sha, development=development)
        except (ValueError, AssertionError):
            self.ledger["qualification_eligible"] = False
            self.ledger["identity_failure"] = (
                "checkout identity or cleanliness changed during execution"
            )
        self.ledger.update(exit_code=exit_code, records=self.records, tests=[], resets=self.resets)
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "ledger.json").write_bytes(canonical_json_bytes(self.ledger) + b"\n")


# --- The surfaces --------------------------------------------------------------------------------


class WorldService:
    """The service contract over one oracle world: the projection that the real service calls, on
    the case's frozen snapshot state with its synthetic snapshot injected (matrix §2.5)."""

    def __init__(self, producer: Producer) -> None:
        self.producer = producer
        self.state: dict[str, Any] = {}
        self.snapshot: SnapshotRef | None = None
        self.calls = 0

    def use(self, state: dict[str, Any], snapshot: dict[str, str]) -> None:
        self.state, self.snapshot = state, SnapshotRef(**snapshot)

    def get_api_consumer_usage(self, request: ApiConsumerUsageQueryRequest):
        self.calls += 1
        assert self.snapshot is not None
        return project_api_consumer_usage(
            request, self.state, snapshot=self.snapshot, producer=self.producer
        )

    def get_api_consumer_usage_evidence(self, request: ApiConsumerUsageEvidenceRequest):
        self.calls += 1
        assert self.snapshot is not None
        return resolve_api_consumer_usage_evidence(
            request, self.state, snapshot=self.snapshot, producer=self.producer
        )


def _rest_client(service: Any) -> TestClient:
    application = FastAPI()
    application.include_router(api_consumer_usage.router)
    errors.register_exception_handlers(application)
    application.dependency_overrides[get_architecture_intelligence_service] = lambda: service
    return TestClient(application)


def _body(request: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in request.items() if key != "mode"}


def rest_post(service: Any, request: dict[str, Any], *, whole: bool = False) -> httpx.Response:
    """POST the request to its route. `whole` keeps the `mode` field, which the route supplies: an
    unknown mode (which REST cannot express) is then rejected as an unknown body field."""
    body = request if whole else _body(request)
    route = ROUTES["evidence" if request.get("mode") == "evidence" else "query"]
    return _rest_client(service).post(route, json=body)


def service_answer(service: Any, request: dict[str, Any]) -> dict[str, Any]:
    if request["mode"] == "evidence":
        answer = service.get_api_consumer_usage_evidence(
            ApiConsumerUsageEvidenceRequest.model_validate(request)
        )
    else:
        answer = service.get_api_consumer_usage(
            ApiConsumerUsageQueryRequest.model_validate(request)
        )
    return answer.model_dump(mode="json")


async def _mcp_batch(
    service: Any, items: list[tuple[Callable[[], None], dict[str, Any]]]
) -> list[dict[str, Any]]:
    server = MCPServer(name="architecture-intelligence-platform-i4", version=package_version())
    register_tools(server, get_service=lambda: service)
    mcp_app = build_mcp_app(allowed_origins=[ORIGIN], allowed_hosts=["localhost"], server=server)
    results = []
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=mcp_app)
        async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
            for prepare, request in items:
                prepare()
                results.append(
                    await call_negotiated(
                        client,
                        origin=ORIGIN,
                        name=API_USAGE_TOOL_NAME,
                        arguments={"request": request},
                    )
                )
    return results


def mcp_calls(
    service: Any, items: list[tuple[Callable[[], None], dict[str, Any]]]
) -> list[dict[str, Any]]:
    # A fresh thread owns its event loop, so this also works under a caller's running loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(_mcp_batch(service, items))).result()


# --- The frozen oracle ---------------------------------------------------------------------------


def _classification(case_id: str, matched: bool) -> str:
    """The label of a case is a property of its frozen expectation; a mismatch is a defect."""
    if not matched:
        return "I4_SEMANTIC_DEFECT"
    expected = V07.expected_classification(case_id)
    assert expected is not None, f"{case_id} has no frozen classification"
    return expected


def run_oracle(recorder: Recorder, producer: Producer) -> None:
    i3 = json.loads((SPEC / "i3-vectors/expected-answers.json").read_text(encoding="utf-8"))
    i4 = json.loads((SPEC / "i4-vectors/expected-i4.json").read_text(encoding="utf-8"))
    worlds = {**i3["worlds"], **i4["worlds"]}
    snapshots = {"i3": i3["snapshots"], "i4": i4["snapshots"]}
    service = WorldService(producer)

    def load(case: dict[str, Any], origin: str) -> None:
        service.use(
            worlds[case["inputs"]["world"]]["snapshot_state"],
            snapshots[origin][case["inputs"]["current_snapshot"]],
        )

    answers = [
        (case, origin)
        for origin, doc in (("i3", i3), ("i4", i4))
        for case in doc["cases"]
        if case["kind"] == "answer"
    ]
    mcp_results = mcp_calls(
        service,
        [(lambda c=case, o=origin: load(c, o), case["request"]) for case, origin in answers],
    )
    executed: dict[str, dict[str, Any]] = {}
    for (case, origin), mcp in zip(answers, mcp_results, strict=True):
        load(case, origin)
        expected, request = case["expected"], case["request"]
        service_payload = service_answer(service, request)
        rest = rest_post(service, request)
        assert rest.status_code == 200, case["id"]
        assert mcp["isError"] is False, case["id"]
        executed[case["id"]] = {**case, "expected": service_payload}
        for surface, payload in (
            ("service", service_payload),
            ("rest", rest.json()),
            ("mcp", mcp["structuredContent"]),
        ):
            matched = first_difference(expected, payload) is None
            recorder.write(
                payload,
                surface=surface,
                comparison_key=f"{case['id']}/1",
                case_id=case["id"],
                request=request,
                oracle_match=matched,
                classification=_classification(case["id"], matched),
            )
    run_requests(recorder, i3, service)
    run_properties(recorder, i3, executed)


def run_requests(recorder: Recorder, i3: dict[str, Any], service: WorldService) -> None:
    cases = [case for case in i3["cases"] if case["kind"] == "request"]
    service.calls = 0
    mcp_results = mcp_calls(service, [(lambda: None, case["request"]) for case in cases])
    for case, mcp in zip(cases, mcp_results, strict=True):
        request = case["request"]
        rest = rest_post(service, request, whole=request.get("mode") not in ROUTES)
        rejected_rest = rest.status_code == 422
        rejected_mcp = mcp["isError"] is True
        key = f"{case['id']}/1"
        for surface, payload, rejected in (
            ("rest", {"status_code": rest.status_code, "body": rest.json()}, rejected_rest),
            ("mcp", mcp, rejected_mcp),
        ):
            recorder.write(
                payload,
                surface=surface,
                comparison_key=key,
                case_id=case["id"],
                request=request,
                oracle_match=rejected,
                classification=_classification(case["id"], rejected),
            )
    assert service.calls == 0, "a rejected request reached the service"


def run_properties(
    recorder: Recorder, i3: dict[str, Any], executed: dict[str, dict[str, Any]]
) -> None:
    canary = i3["worlds"]["base"]["internal_only"]["credential_canary"]
    world_text = json.dumps(i3["worlds"]["base"]["internal_only"])
    for case in (c for c in i3["cases"] if c["kind"] == "property"):
        holds, detail = True, None
        try:
            for item in case["assert"]:
                check_property(item, cases=executed, world_text=world_text)
        except AssertionError as error:
            holds, detail = False, str(error)
        assert canary  # the canary is a harness input, never part of a recorded payload
        recorder.write(
            {"property": case["id"], "holds": holds, "detail": detail},
            surface="derived-properties",
            comparison_key=f"{case['id']}/1",
            case_id=case["id"],
            request={"steps": case["steps"]},
            oracle_match=holds,
            classification=_classification(case["id"], holds),
        )


# --- A real import, a real service, a real client -------------------------------------------------


def _clean_state(recorder: Recorder, driver: Any) -> None:
    """Empty the database, prove it is empty, then apply the schema (the v0.6 clean-state proof)."""
    from app.graph.schema import ensure_schema

    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        nodes = session.run("MATCH (n) RETURN count(n) AS n").single()["n"]
        assert nodes == 0, "the database is not empty after the reset"
        ensure_schema(session)
    recorder.resets.append({"nodes_before_schema": nodes})


def _real_requests(state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    window = state["api_usage_v1"]["windows"][0]
    context = {
        "gateway_instance_id": window["gateway_instance_id"],
        "environment": window["environment"],
        "window_start": window["window_start"],
        "window_end": window["window_end"],
    }
    service = {"kind": "APPLICATION_SERVICE", "id": api_usage_cost.SERVICE}
    return [("RT01", {"mode": "query", "target": service, "limit": REAL_PAGE, **context})]


def run_real_import(recorder: Recorder, driver: Any, producer: Producer, work: Path) -> None:
    _clean_state(recorder, driver)
    api_usage_cost.build(driver, REAL_POINT, work)
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=producer)
    from app.architecture_intelligence.repository import canonical_snapshot_state

    with driver.session(database=DATABASE) as session:
        state = canonical_snapshot_state(session, coverage_qualification_enabled=True)
    ((case_id, first),) = _real_requests(state)
    page_one = service_answer(service, first)
    snapshot_id = page_one["snapshot"]["snapshot_id"]
    second = {
        **first,
        "cursor": page_one["data"]["page"]["next_cursor"],
        "snapshot_id": snapshot_id,
    }
    refs = sorted(
        {
            *page_one["data"]["window"]["evidence_refs"],
            *(r for route in page_one["data"]["selected_routes"] for r in route["evidence_refs"]),
            *(r for row in page_one["data"]["rows"] for r in row["evidence_refs"]),
        }
    )[: api_usage_cost.MAX_EVIDENCE_REFS]
    context_keys = ("target", "gateway_instance_id", "environment", "window_start", "window_end")
    evidence = {
        "mode": "evidence",
        "snapshot_id": snapshot_id,
        "evidence_refs": refs,
        **{key: first[key] for key in context_keys},
    }
    stale = {**first, "snapshot_id": "aip:snapshot:v1:" + "0" * 64}
    asked = [
        (f"{case_id}a", first),
        (f"{case_id}b", second),
        (f"{case_id}c", evidence),
        (f"{case_id}d", stale),
    ]
    mcp_results = mcp_calls(service, [(lambda: None, request) for _, request in asked])
    independent = _independent_client(driver, asked)
    seen_rows: dict[str, set[tuple[str, str]]] = {}
    for (name, request), mcp in zip(asked, mcp_results, strict=True):
        rest = rest_post(service, request)
        assert rest.status_code == 200 and mcp["isError"] is False, name
        payloads = [
            ("service", service_answer(service, request)),
            ("rest", rest.json()),
            ("mcp", mcp["structuredContent"]),
        ]
        if name in independent:
            payloads.append(("mcp-independent-client", independent[name]))
        for surface, payload in payloads:
            expected_true = _real_expectation_holds(name, payload, seen_rows)
            recorder.write(
                payload,
                surface=surface,
                comparison_key=f"{name}/1",
                case_id=name,
                request=request,
                oracle_match=expected_true,
                classification=_classification(name, expected_true),
            )


def _real_expectation_holds(
    name: str, payload: dict[str, Any], seen_rows: dict[str, set[tuple[str, str]]]
) -> bool:
    """The structural expectations of the generated world, fixed by `REAL_POINT` and independent of
    the answer: 24 rows over a page of ten, a continuation that repeats no row, evidence that all
    resolves, and a stale snapshot that is refused. (The frozen semantic truth is the oracle above;
    the I4.1c replay package carries the real-source readings.)"""
    data = payload["data"]
    if name.endswith("d"):
        return data is None and [item["code"] for item in payload["limitations"]] == [
            "SNAPSHOT_NOT_AVAILABLE"
        ]
    if name.endswith("c"):
        entries = data["entries"]
        return payload["outcome"] == "ANSWERED" and {e["status"] for e in entries} == {"RESOLVED"}
    keys = [(row["consumer"]["id"], row["gateway_route"]["id"]) for row in data["rows"]]
    seen_rows.setdefault(name, set(keys))
    # the rows of the other page of the same question (every surface repeats its own page)
    fresh = not any(set(keys) & rows for other, rows in seen_rows.items() if other != name)
    if name.endswith("a"):
        return len(keys) == REAL_PAGE and data["page"]["next_cursor"] is not None and fresh
    return len(keys) == REAL_PAGE and fresh


def _independent_client(driver: Any, asked: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    """The httpx-only client over real HTTP against the production app, on the same graph. A fresh
    client (a reconnect) must return the identical first answer, checked here and not re-recorded."""
    port = free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    with tempfile.TemporaryDirectory(prefix="aip-i4-app-") as work:
        config_path = Path(work) / "config.yaml"
        config_path.write_text(
            "architecture_intelligence:\n  mcp:\n"
            f'    allowed-origins: ["{base_url}"]\n    allowed-hosts: ["127.0.0.1:{port}"]\n'
        )
        app.main.CONFIG_PATH = config_path
        os.environ.pop("OPENAI_API_KEY", None)
        real_app = app.main.create_app()
        recorded: dict[str, Any] = {}
        with (
            serve_over_real_http(real_app, port=port),
            httpx.Client(base_url=base_url, headers={"origin": base_url}, timeout=60.0) as client,
        ):
            tools = [t["name"] for t in independent_mcp_client.tools_list(client)["tools"]]
            # v0.7.1 I3.2 added the sixth tool, `get_destination_consumers`.
            assert API_USAGE_TOOL_NAME in tools and len(tools) == 6, tools
            for name, request in asked[:3]:
                result = independent_mcp_client.call_tool(
                    client, name=API_USAGE_TOOL_NAME, arguments={"request": request}
                )
                assert result["isError"] is False, name
                recorded[name] = result["structuredContent"]
            with httpx.Client(
                base_url=base_url, headers={"origin": base_url}, timeout=60.0
            ) as reconnected:
                again = independent_mcp_client.call_tool(
                    reconnected, name=API_USAGE_TOOL_NAME, arguments={"request": asked[0][1]}
                )
            assert again["structuredContent"] == recorded[asked[0][0]], "reconnect differs"
    return recorded


# --- The APISIX replay package -----------------------------------------------------------------------


def _ask_three(
    recorder: Recorder,
    service: Any,
    items: list[tuple[str, dict[str, Any]]],
    judge: Callable[[str, dict[str, Any]], bool],
) -> dict[str, dict[str, Any]]:
    """Ask each question of the real service, REST and negotiated MCP and record all three answers;
    `judge` decides, from the frozen reading, whether an answer is the expected one."""
    mcp_results = mcp_calls(service, [(lambda: None, request) for _, request in items])
    answers: dict[str, dict[str, Any]] = {}
    for (case_id, request), mcp in zip(items, mcp_results, strict=True):
        rest = rest_post(service, request)
        assert rest.status_code == 200 and mcp["isError"] is False, case_id
        payloads = [
            ("service", service_answer(service, request)),
            ("rest", rest.json()),
            ("mcp", mcp["structuredContent"]),
        ]
        answers[case_id] = payloads[0][1]
        for surface, payload in payloads:
            ok = judge(case_id, payload)
            recorder.write(
                payload,
                surface=surface,
                comparison_key=f"{case_id}/1",
                case_id=case_id,
                request=request,
                oracle_match=ok,
                classification=_classification(case_id, ok),
            )
    return answers


def _refused_as_stale(_: str, payload: dict[str, Any]) -> bool:
    return payload["data"] is None and [x["code"] for x in payload["limitations"]] == [
        "SNAPSHOT_NOT_AVAILABLE"
    ]


def run_replay(recorder: Recorder, driver: Any, producer: Producer, work: Path) -> None:
    """The real APISIX captures, imported through the production path, asked of the service, REST and
    MCP, against the frozen readings (decision record D4)."""
    from evaluation.i4 import apisix_replay as replay

    cases = {case["id"]: case for case in replay.PLAN["cases"]}
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=producer)

    def readings(state: dict[str, Any]) -> Callable[[str, dict[str, Any]], bool]:
        return lambda case_id, payload: not replay.reading_problems(cases[case_id], payload, state)

    # R1 / W1: the real captures P1, P2, N1-N4, OBS and the never-imported window
    assert not replay.package_problems(), replay.package_problems()
    _clean_state(recorder, driver)
    replay.import_revision(driver, "r1", work)
    state1 = replay.read_state(driver)
    first = [c for c in replay.PLAN["cases"] if c["world"] == "r1" and c["id"] != "W-INVALID"]
    asked = [(c["id"], replay.request_for(c, state1)) for c in first]
    answers = _ask_three(recorder, service, asked, readings(state1))

    # evidence of the first answer resolves at its own snapshot
    page = answers["P1"]["data"]
    refs = sorted(
        {
            *page["window"]["evidence_refs"],
            *(r for route in page["selected_routes"] for r in route["evidence_refs"]),
            *(r for row in page["rows"] for r in row["evidence_refs"]),
        }
    )[: api_usage_cost.MAX_EVIDENCE_REFS]
    context = ("target", "gateway_instance_id", "environment", "window_start", "window_end")
    p1 = dict(asked)["P1"]
    evidence = {
        "mode": "evidence",
        "snapshot_id": answers["P1"]["snapshot"]["snapshot_id"],
        "evidence_refs": refs,
        "consumer_id": p1["consumer_id"],
        **{key: p1[key] for key in context},
    }
    _ask_three(
        recorder,
        service,
        [("EV", evidence)],
        lambda _, payload: (
            payload["outcome"] == "ANSWERED"
            and {e["status"] for e in payload["data"]["entries"]} == {"RESOLVED"}
        ),
    )

    # the derived variant: the real W1 manifest with an unsettled end boundary
    replay.import_revision(driver, "r1", work, unsettled_end=True)
    unsettled = replay.read_state(driver)
    invalid = cases["W-INVALID"]
    _ask_three(
        recorder,
        service,
        [("W-INVALID", replay.request_for(invalid, unsettled))],
        readings(unsettled),
    )

    # R1 again (the same bytes, so the same snapshot), a cursor and a ref minted under it
    replay.import_revision(driver, "r1", work)
    state_again = replay.read_state(driver)
    orders = replay.request_for(cases["P1"], state_again) | {"limit": 1}
    orders.pop("consumer_id", None)
    page_one = service_answer(service, orders)
    assert page_one["data"]["page"]["next_cursor"], "the R1 Route has more than one row"
    stale_query = {
        **orders,
        "cursor": page_one["data"]["page"]["next_cursor"],
        "snapshot_id": page_one["snapshot"]["snapshot_id"],
    }
    # the same context as EV, so that after R2 only the snapshot differs
    stale_evidence = {**evidence, "snapshot_id": page_one["snapshot"]["snapshot_id"]}
    before = service_answer(service, stale_evidence)
    assert {e["status"] for e in before["data"]["entries"]} == {"RESOLVED"}, "resolves under R1"

    # R2 / W2: authoritative update after a restart
    replay.import_revision(driver, "r2", work)
    state2 = replay.read_state(driver)
    removed = replay.route_ids(state1)
    second = [c for c in replay.PLAN["cases"] if c["world"] == "r2"]
    _ask_three(
        recorder,
        service,
        [(c["id"], replay.request_for(c, state2, removed_routes=removed)) for c in second],
        readings(state2),
    )
    _ask_three(recorder, service, [("REVd", stale_query)], _refused_as_stale)
    _ask_three(recorder, service, [("REVe", stale_evidence)], _refused_as_stale)


# --- Entry point -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--run", choices=("A", "B"), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--development", action="store_true", help="record local checks, never eligible"
    )
    args = parser.parse_args(argv)
    verify_candidate(args.candidate_sha, development=args.development)
    if args.development:
        os.environ.setdefault("I4_CANDIDATE_SHA", args.candidate_sha)
        os.environ.setdefault("AIP_BUILD_REVISION", args.candidate_sha)
    assert os.environ.get("I4_CANDIDATE_SHA") == args.candidate_sha
    assert os.environ.get("AIP_BUILD_REVISION") == args.candidate_sha
    producer = Producer(
        name="architecture-intelligence-platform",
        version=package_version(),
        build_revision=args.candidate_sha,
    )
    recorder = Recorder(args.out, args.candidate_sha, args.run, args.development)
    exit_code = 0
    try:
        run_oracle(recorder, producer)
        with Neo4jContainer(
            "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
        ) as container:
            os.environ.update(
                NEO4J_URI=container.get_connection_url(),
                NEO4J_USER=container.username,
                NEO4J_PASSWORD=container.password,
            )
            recorder.ledger["container_id"] = container.get_wrapped_container().id
            driver = container.get_driver()
            try:
                with tempfile.TemporaryDirectory(prefix="aip-i4-real-") as work:
                    run_real_import(recorder, driver, producer, Path(work))
                    run_replay(recorder, driver, producer, Path(work) / "replay")
            finally:
                driver.close()
    except Exception:  # noqa: BLE001 - recorded in the ledger, then re-raised as a failed run
        exit_code = 1
        import traceback

        recorder.ledger["failure"] = traceback.format_exc()
    finally:
        for record in recorder.records:
            record["container_id"] = recorder.ledger["container_id"]
        recorder.finish(exit_code, args.development)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
