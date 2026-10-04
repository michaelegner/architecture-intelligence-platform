"""Opt-in capture around existing oracle checks; never normalizes semantic payloads."""

from __future__ import annotations

import asyncio
import hashlib
import os
import platform
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.schema import ensure_schema
from app.version import package_version
from evaluation.i4.__main__ import REGISTER, ROOT, verify_candidate

_CAPTURE_MODULES = {"test_locality_oracle", "test_locality_surface_parity", "test_v060_i4_bridges"}


def pytest_addoption(parser):
    parser.addoption("--i4-candidate-sha", required=True)
    parser.addoption("--i4-run", choices=("A", "B"), required=True)
    parser.addoption("--i4-out", type=Path, required=True)
    parser.addoption(
        "--i4-development",
        action="store_true",
        help="record local checks, never eligible for qualification",
    )


def _digests():
    roots = [
        ROOT / "docs/specifications/0.6.0",
        ROOT / "schemas/architecture_intelligence",
        ROOT / "tests/fixtures",
        ROOT / "evaluation/scenarios",
        ROOT / "evaluation/architecture_answers/scenarios",
        ROOT / "examples/release-golden-path",
        ROOT / "examples/quarkus-super-heroes-demo",
        ROOT / "docs/real-world-validation/v0.5.0/quarkus-super-heroes/runtime",
    ]
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


class Capture:
    def __init__(self, config):
        self.sha = config.getoption("--i4-candidate-sha")
        self.version = package_version()
        development = config.getoption("--i4-development")
        verify_candidate(self.sha, development=development)
        if development:
            os.environ.setdefault("I4_CANDIDATE_SHA", self.sha)
            os.environ.setdefault("AIP_BUILD_REVISION", self.sha)
        assert os.environ.get("I4_CANDIDATE_SHA") == self.sha
        assert os.environ.get("AIP_BUILD_REVISION") == self.sha
        self.out = config.getoption("--i4-out")
        self.current = ""
        self.case = ""
        self.comparing = False
        self.indices = {}
        self.latest = {}
        self.ingestion_configs = {}
        self.records = []
        self.tests = []
        self.resets = []
        self.container = None
        self.input_directory = None
        self.ledger = {
            "schema": "i4-ledger/1",
            "run": config.getoption("--i4-run"),
            "candidate_sha": self.sha,
            "head": self.sha,
            "producer_version": self.version,
            "qualification_eligible": not development,
            "process_id": os.getpid(),
            "container_id": None,
            "runtime": {"python": platform.python_version(), "platform": platform.platform()},
            "input_pins": _digests(),
            "command": config.invocation_params.args,
            "configuration": {
                "I4_CANDIDATE_SHA": self.sha,
                "AIP_BUILD_REVISION": self.sha,
            },
        }
        self.register = {}
        for line in REGISTER.read_text().splitlines():
            if line.startswith("| S20-"):
                key = line.split("|")[1].strip()
                for case in re.findall(r"`([LXPQB]\d\d[ab]?)`", line):
                    self.register.setdefault(case, []).append(key)

    def write(self, payload, *, surface, comparison_key, request):
        raw = canonical_json_bytes(payload)
        key = f"{comparison_key}/{surface}"
        relative = "bytes/" + hashlib.sha256(key.encode()).hexdigest() + ".json"
        target = self.out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), f"duplicate capture key: {key}"
        target.write_bytes(raw)
        generated_pins = {}
        if self.input_directory is not None:
            for path in sorted(self.input_directory.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    content = path.read_bytes()
                    digest = hashlib.sha256(content).hexdigest()
                    reference = f"inputs/{digest}"
                    artifact = self.out / reference
                    artifact.parent.mkdir(parents=True, exist_ok=True)
                    if not artifact.exists():
                        artifact.write_bytes(content)
                    generated_pins[str(path.relative_to(self.input_directory))] = {
                        "sha256": digest,
                        "bytes_ref": reference,
                    }
        data = payload.get("data") or {}
        dispositions = sorted(
            {c["disposition"] for c in data.get("candidates", [])}
            | {l["code"] for l in payload.get("limitations", [])}
        )
        self.records.append(
            {
                "key": key,
                "comparison_key": comparison_key,
                "case_id": self.case,
                "register_keys": self.register.get(self.case, []),
                "test_id": self.current,
                "state": ("C1" if comparison_key.endswith("/1") else "C2")
                if self.case.startswith("B01")
                else comparison_key.rsplit("/", 1)[-1],
                "surface": surface,
                "candidate_sha": self.sha,
                "head": self.sha,
                "producer_build_revision": (payload.get("producer") or {}).get("build_revision"),
                "request": request,
                "canonical_digest": hashlib.sha256(raw).hexdigest(),
                "bytes_ref": relative,
                "oracle_match": None,
                "oracle_check": self.current,
                "original_disposition": dispositions,
                "classification": None,
                "skipped": False,
                "generated_input_pins": generated_pins,
            }
        )

    def capture_answer(self, service, request, answer):
        assert answer.producer.build_revision == self.sha
        assert answer.producer.version == self.version
        payload = answer.model_dump(mode="json")
        request = request.model_dump(mode="json")
        index = self.indices.get(self.current, 0) + 1
        self.indices[self.current] = index
        key = f"{self.current}/{index}"
        self.latest[canonical_json_bytes(request)] = key
        service_config = {
            "coverage_qualification_enabled": service._coverage_qualification_enabled,
            "configured_kubernetes_sources": service._configured_kubernetes_sources,
            "service_aliases": service._service_aliases,
        }
        self.write(payload, surface="service", comparison_key=key, request=request)
        from tests.integration.test_locality_surface_parity import _mcp, _rest

        self.comparing = True
        try:
            rest = _rest(service, request)
            assert rest.status_code == 200
            self.write(rest.json(), surface="rest", comparison_key=key, request=request)
            # Also works when the original oracle test itself runs in an asyncio loop.
            with ThreadPoolExecutor(max_workers=1) as pool:
                mcp = pool.submit(lambda: asyncio.run(_mcp(service, request))).result()
            assert mcp["isError"] is False
            self.write(mcp["structuredContent"], surface="mcp", comparison_key=key, request=request)
            assert (
                canonical_json_bytes(payload)
                == canonical_json_bytes(rest.json())
                == canonical_json_bytes(mcp["structuredContent"])
            )
            for record in self.records:
                if record["comparison_key"] == key:
                    record["service_configuration"] = service_config
        finally:
            self.comparing = False


def pytest_configure(config):
    config._i4_capture = Capture(config)


def pytest_runtest_setup(item):
    capture = item.config._i4_capture
    capture.current = item.nodeid
    parameter = getattr(item, "callspec", None)
    case_id = parameter.params.get("case_id") if parameter else None
    match = re.search(r"(?:test_)([pb]\d\d)", item.name, re.IGNORECASE)
    capture.case = (match[1].upper() if match else case_id) or item.name


@pytest.fixture(autouse=True)
def i4_capture(request, monkeypatch):
    capture = request.config._i4_capture
    module = request.module.__name__.rsplit(".", 1)[-1]
    independent = (
        module == "test_mcp_independent_client_golden_path" and "locality" in request.node.name
    )
    legacy_answers = (
        module == "test_evaluation_architecture_answers"
        and request.node.name == "test_every_bundled_scenario_passes_with_identical_two_pass_output"
    )
    if module not in _CAPTURE_MODULES and not independent and not legacy_answers:
        return
    capture.input_directory = (
        request.getfixturevalue("tmp_path") if "tmp_path" in request.fixturenames else None
    )
    from tests.integration import test_locality_oracle, test_locality_rehearsal_replay
    from tests.integration.locality_oracle import world

    for target in (test_locality_oracle, test_locality_rehearsal_replay):
        monkeypatch.setattr(
            target,
            "PRODUCER",
            target.PRODUCER.model_copy(
                update={"build_revision": capture.sha, "version": capture.version}
            ),
        )
    container = request.getfixturevalue("neo4j_container").get_wrapped_container()
    capture.ledger["container_id"] = container.id
    capture.ledger["neo4j_image"] = container.attrs["Config"]["Image"]
    driver = request.getfixturevalue("driver")
    if capture.container is None:
        capture.container = container.id
        with driver.session(database=world.DATABASE) as session:
            # First capture suite must start from an explicit clean state too.
            session.run("MATCH (n) DETACH DELETE n").consume()
            assert session.run("MATCH (n) RETURN count(n) AS c").single()["c"] == 0
            ensure_schema(session)
        capture.resets.append(
            {"test_id": request.node.nodeid, "nodes_before_schema": 0, "schema_reapplied": True}
        )

    def clean(graph):
        with graph.session(database=world.DATABASE) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()
            count = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            assert count == 0
            ensure_schema(session)
        capture.resets.append(
            {"test_id": request.node.nodeid, "nodes_before_schema": count, "schema_reapplied": True}
        )

    monkeypatch.setattr(world, "clean", clean)
    from app.telemetry import ingest

    for target in (world, ingest):
        original_persist = target.persist_observation_batch

        def persist(*args, _original=original_persist, **kwargs):
            scoped = kwargs.get("scoped")
            if scoped is not None:
                config = scoped.model_dump(mode="json", by_alias=True)
                configurations = capture.ingestion_configs.setdefault(capture.current, [])
                if config not in configurations:
                    configurations.append(config)
            return _original(*args, **kwargs)

        monkeypatch.setattr(target, "persist_observation_batch", persist)
    if legacy_answers:
        from evaluation.architecture_answers import runner

        original_pass = runner._run_pass
        original_suite = request.module.run_suite

        def suite(graph, scenarios):
            return original_suite(graph, scenarios, candidate_sha=capture.sha)

        def run_pass(graph, *, scenario, producer):
            assert producer.build_revision == capture.sha
            answer = original_pass(graph, scenario=scenario, producer=producer)
            index = capture.indices.get(capture.current, 0) + 1
            capture.indices[capture.current] = index
            capture.case = f"legacy-answer:{scenario.id}"
            capture.write(
                answer.model_dump(mode="json"),
                surface="legacy-service",
                comparison_key=f"{capture.current}/{index}",
                request=runner.build_request_payload(scenario.request),
            )
            return answer

        monkeypatch.setattr(request.module, "run_suite", suite)
        monkeypatch.setattr(runner, "_run_pass", run_pass)
        return
    if module == "test_v060_i4_bridges" and request.node.name.startswith(
        "test_legacy_relation_evaluator"
    ):
        from dataclasses import asdict

        from evaluation import runner

        original_projector = runner.load_relation_facts

        def projected(session, **kwargs):
            facts = original_projector(session, **kwargs)
            index = capture.indices.get(capture.current, 0) + 1
            capture.indices[capture.current] = index
            capture.case = f"legacy-relation:{request.node.callspec.params['scenario_path'].name}"
            capture.write(
                {"data": {"facts": [asdict(fact) for fact in sorted(facts)]}},
                surface="legacy-relations",
                comparison_key=f"{capture.current}/{index}",
                request={"environment": kwargs["environment"]},
            )
            return facts

        monkeypatch.setattr(runner, "load_relation_facts", projected)
        return
    if capture.case.startswith("Q"):
        from tests.integration import test_locality_surface_parity as parity

        original_rest, original_mcp = parity._rest, parity._mcp

        def rejected_rest(service, query):
            response = original_rest(service, query)
            capture.write(
                {"status_code": response.status_code, "body": response.json()},
                surface="rest",
                comparison_key=f"{capture.current}/1",
                request=query,
            )
            return response

        async def rejected_mcp(service, query):
            result = await original_mcp(service, query)
            capture.write(
                result, surface="mcp", comparison_key=f"{capture.current}/1", request=query
            )
            return result

        monkeypatch.setattr(parity, "_rest", rejected_rest)
        monkeypatch.setattr(parity, "_mcp", rejected_mcp)
    for name in ("get_service_dependencies_by_locality", "resolve_scoped_locality_evidence"):
        original = getattr(ArchitectureIntelligenceService, name)

        def wrapped(service, query, _original=original):
            answer = _original(service, query)
            if not capture.comparing:
                capture.capture_answer(service, query, answer)
            return answer

        monkeypatch.setattr(ArchitectureIntelligenceService, name, wrapped)

    if independent:
        from app.architecture_intelligence.locality_contracts import (
            ServiceDependenciesByLocalityRequest,
        )
        from tests.integration import (
            independent_mcp_client,
            test_mcp_independent_client_golden_path,
        )

        original_call = independent_mcp_client.call_tool

        def call(client, *, name, arguments, request_id=1):
            result = original_call(client, name=name, arguments=arguments, request_id=request_id)
            if name == "get_service_dependencies_by_locality":
                parsed = ServiceDependenciesByLocalityRequest.model_validate(
                    arguments["request"]
                ).root.model_dump(mode="json")
                key = capture.latest[canonical_json_bytes(parsed)]
                capture.write(
                    result["structuredContent"],
                    surface="mcp-independent-client",
                    comparison_key=key,
                    request=parsed,
                )
            return result

        monkeypatch.setattr(independent_mcp_client, "call_tool", call)
        monkeypatch.setattr(test_mcp_independent_client_golden_path, "call_tool", call)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    capture = item.config._i4_capture
    if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
        capture.tests.append(
            {
                "nodeid": item.nodeid,
                "outcome": report.outcome,
                "detail": str(report.longrepr) if report.outcome != "passed" else None,
            }
        )
        for record in capture.records:
            if record["test_id"] == item.nodeid:
                record["oracle_match"] = report.passed
                record["classification"] = "I4_CORRECT" if report.passed else "I4_SEMANTIC_DEFECT"
                if report.passed:
                    dispositions = record["original_disposition"]
                    if "UNSUPPORTED_REQUEST" in dispositions:
                        record["classification"] = "I4_UNSUPPORTED_EXPECTED"
                    elif "UNRESOLVED" in dispositions:
                        record["classification"] = "I4_UNRESOLVED_EXPECTED"
                    elif "INSUFFICIENT_EVIDENCE" in dispositions:
                        record["classification"] = "I4_INSUFFICIENT_EVIDENCE_EXPECTED"
                record["skipped"] = report.skipped
                pins = record["generated_input_pins"]
                record["input_digest"] = hashlib.sha256(
                    canonical_json_bytes(
                        {"frozen": capture.ledger["input_pins"], "generated": pins}
                    )
                ).hexdigest()
                record["oracle_digest"] = hashlib.sha256(
                    canonical_json_bytes(
                        {k: v for k, v in capture.ledger["input_pins"].items() if "vectors/" in k}
                    )
                ).hexdigest()
                record["schema_digest"] = hashlib.sha256(
                    canonical_json_bytes(
                        {
                            k: v
                            for k, v in capture.ledger["input_pins"].items()
                            if k.startswith("schemas/")
                        }
                    )
                ).hexdigest()
                record["config_digest"] = hashlib.sha256(
                    canonical_json_bytes(
                        {
                            "worker": capture.ledger["configuration"],
                            "scoped_ingestion": capture.ingestion_configs.get(item.nodeid, []),
                            "service": record.get("service_configuration", {}),
                        }
                    )
                ).hexdigest()
                record["scoped_ingestion_configuration"] = capture.ingestion_configs.get(
                    item.nodeid, []
                )
                record["run"] = capture.ledger["run"]
                record["process_id"] = capture.ledger["process_id"]
                record["container_id"] = capture.ledger["container_id"]
    elif report.when == "teardown" and report.failed:
        capture.tests.append(
            {"nodeid": item.nodeid, "outcome": "failed", "detail": str(report.longrepr)}
        )


def pytest_sessionfinish(session, exitstatus):
    capture = session.config._i4_capture
    try:
        verify_candidate(capture.sha, development=not capture.ledger["qualification_eligible"])
    except (ValueError, AssertionError):
        capture.ledger["qualification_eligible"] = False
        capture.ledger["identity_failure"] = (
            "checkout identity or cleanliness changed during execution"
        )
    capture.ledger.update(
        exit_code=int(exitstatus),
        records=capture.records,
        tests=capture.tests,
        resets=capture.resets,
    )
    capture.out.mkdir(parents=True, exist_ok=True)
    # Legacy evaluator requests contain datetime objects. Canonical serialization handles
    # these exactly as it handles the response artifacts; ledger metadata is not a payload mask.
    (capture.out / "ledger.json").write_bytes(canonical_json_bytes(capture.ledger) + b"\n")
