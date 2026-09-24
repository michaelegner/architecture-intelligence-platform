"""v0.5.0 I4 slice 5: deterministic broker-semantic qualification (spec §13.3/§13.4).

Three fixtures under `tests/fixtures/pubsub/` - Azure Service Bus, Google Cloud Pub/Sub, and the
Kafka consumer-group negative boundary - each run end to end against real Neo4j through the
unmodified production path: `run_filesystem_discovery` + `import_discovery_run` for the AsyncAPI declarations, `adapt` +
`persist_observation_batch` for the authored spans, and `ArchitectureIntelligenceService` (plus REST
and negotiated MCP) for the public answers. Every expectation lives in the fixture's hand-authored
`expected.yaml`, written by name from `i4-decision-evidence.md` §2 rather than from production ids
(see each fixture's `PROVENANCE.md`).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

import httpx
import jsonschema
import pytest
import yaml
from mcp.server import MCPServer

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from app.architecture_intelligence.contracts import Producer, Qualification
from app.architecture_intelligence.request import (
    ArchitectureDriftRequest,
    EvidenceRequest,
    ServiceDependenciesRequest,
)
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_discovery_run
from app.graph.revision_fence import read_revision
from app.ingestion.orchestrator import run_filesystem_discovery
from app.mcp.app import build_mcp_app, mcp_session_manager_lifespan
from app.mcp.tools import register_tools
from app.sources.model import FilesystemSourceConfig
from app.telemetry.adapter import adapt
from app.telemetry.aggregator import persist_observation_batch
from app.telemetry.model import RuntimeSpan
from app.telemetry.pubsub_resolver import fetch_subscription_candidates, fetch_topic_candidates
from app.telemetry.queue_resolver import fetch_queue_candidates
from app.telemetry.service_resolver import fetch_candidates
from evaluation.architecture_answers.reference import identities
from tests.integration.test_api_architecture_intelligence_equivalence import _client
from tests.support.negotiated_mcp_client import (
    call_negotiated,
    negotiated_headers,
    negotiated_tools_list_body,
)

DATABASE = "neo4j"
FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "pubsub"
FIXTURES = ("azure-service-bus", "google-pubsub", "kafka")
WINDOW_START = "2026-09-23T00:00:00.000000Z"
WINDOW_END = "2026-09-24T00:00:00.000000Z"
_ALLOWED_ORIGIN = "http://localhost"
_ALLOWED_HOST = "localhost"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)
_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "architecture_intelligence" / "v0.5"
SCHEMAS = {
    "dependencies": json.loads((_SCHEMA_DIR / "architecture-answer.schema.json").read_text()),
    "drift": json.loads((_SCHEMA_DIR / "drift-answer.schema.json").read_text()),
    "evidence": json.loads((_SCHEMA_DIR / "evidence-answer.schema.json").read_text()),
}

# The relation kinds whose presence/absence is the broker-semantic question (spec §6).
_IN_SCOPE_RELATIONS = (
    "SENDS",
    "RECEIVES_FROM",
    "PUBLISHES_TO",
    "SUBSCRIPTION_OF",
    "CARRIES",
    "DEAD_LETTERS_TO",
)
_FACTS_QUERY = (
    f"MATCH (a)-[r:{'|'.join(_IN_SCOPE_RELATIONS)}]->(b) "
    "RETURN type(r) AS type, labels(a)[0] + ':' + a.name AS source, "
    "labels(b)[0] + ':' + b.name AS target, "
    "any(eid IN coalesce(r.evidence_ids, []) WHERE exists { "
    "MATCH (:Evidence {id: eid, evidence_type: 'OBSERVED'}) }) AS observed"
)
_DEAD_LETTER_QUERY = (
    "MATCH (c:SubscriptionDeadLetterConfiguration) "
    "OPTIONAL MATCH (s:Subscription {id: c.subscription_id}) "
    "RETURN s.name AS subscription, c.target_token AS target, c.target_kind_token AS kind"
)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def _expected(fixture: str) -> dict:
    return _load_yaml(FIXTURES_ROOT / fixture / "expected.yaml")


def _wipe(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")


def _spans(fixture_dir: Path) -> tuple[str, list[RuntimeSpan]]:
    document = _load_yaml(fixture_dir / "spans.yaml")
    time = datetime.fromisoformat(document["time"])
    spans = [
        RuntimeSpan(
            trace_id=span["trace"].ljust(32, "0"),
            span_id=span["trace"].ljust(16, "0"),
            parent_span_id=None,
            span_name=span["attributes"]["messaging.destination.name"],
            span_kind="PRODUCER" if span["operation"] == "send" else "CONSUMER",
            service_name=span["service"],
            service_instance_id=span["instance"],
            environment=document["environment"],
            start_time=time,
            end_time=time,
            attributes={"messaging.operation.type": span["operation"], **span["attributes"]},
        )
        for span in document["spans"]
    ]
    return document["environment"], spans


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request_payload(service: str, environment: str) -> dict:
    return {
        "service_id": f"service:{service}",
        "observation_context": {
            "environment": environment,
            "window_start": WINDOW_START,
            "window_end": WINDOW_END,
        },
    }


def _answer_refs(answer_json: dict) -> list[str]:
    refs = set(answer_json["evidence_refs"])
    for claim in answer_json["claims"]:
        refs.update(claim["evidence_refs"])
        refs.update(claim["resolution_evidence_refs"])
    return sorted(refs)


def _qualify_fixture(
    driver, fixture_dir: Path, fixture: str, *, reverse_spans: bool = False
) -> dict:
    """One clean, complete qualification run of a fixture: wipe, import, ingest, read. Returns
    everything observable - nothing filtered - so byte comparison covers the full output."""
    _wipe(driver)
    # `import_all_sources` is exactly this pair; calling it unwrapped keeps each source's own
    # adapter diagnostics attributable to that source.
    run_result = run_filesystem_discovery(
        FilesystemSourceConfig(
            id=f"i4-qualification-{fixture}",
            root=fixture_dir / "declarations",
            stable_target_identity=f"urn:aip:logical-root:i4-qualification-{fixture}",
        )
    )
    stats = import_discovery_run(driver, database=DATABASE, run_result=run_result)
    assert stats.committed is True
    sources = {
        Path(run_outcome.descriptor_locator).parent.name: {
            "result": run_outcome.outcome.result.value,
            "diagnostics": sorted(
                [diagnostic.code.value, diagnostic.source_pointer]
                for diagnostic in run_outcome.outcome.diagnostics
            ),
        }
        for run_outcome in run_result.source_outcomes.values()
    }

    environment, spans = _spans(fixture_dir)
    if reverse_spans:
        spans = list(reversed(spans))
    with driver.session(database=DATABASE) as session:
        batch = adapt(
            spans,
            service_candidates=fetch_candidates(session),
            operation_candidates=[],
            queue_candidates=fetch_queue_candidates(session),
            service_aliases={},
            queue_aliases={},
            topic_candidates=fetch_topic_candidates(session),
            subscription_candidates=fetch_subscription_candidates(session),
        )
    persist_observation_batch(driver, DATABASE, batch)

    with driver.session(database=DATABASE) as session:
        rows = [record.data() for record in session.run(_FACTS_QUERY)]
        entities = {
            label: sorted(
                r["name"] for r in session.run(f"MATCH (n:{label}) RETURN n.name AS name")
            )
            for label in ("Queue", "Topic", "Subscription")
        }
        dead_letters = sorted(
            [r["subscription"], r["target"], r["kind"]] for r in session.run(_DEAD_LETTER_QUERY)
        )

    service = _service(driver)
    answers = {}
    for slug in sorted(sources):
        payload = _request_payload(slug, environment)
        dependencies = service.get_service_dependencies(
            ServiceDependenciesRequest.model_validate(payload)
        ).model_dump(mode="json")
        drift = service.get_architecture_drift(
            ArchitectureDriftRequest.model_validate(payload)
        ).model_dump(mode="json")
        refs = _answer_refs(dependencies)
        evidence = (
            service.get_evidence(
                EvidenceRequest.model_validate(
                    {"evidence_refs": refs, "snapshot_id": dependencies["snapshot"]["snapshot_id"]}
                )
            ).model_dump(mode="json")
            if refs
            else None
        )
        answers[slug] = {"dependencies": dependencies, "drift": drift, "evidence": evidence}

    return {
        "sources": sources,
        "facts": sorted([r["type"], r["source"], r["target"]] for r in rows),
        "observed": sorted([r["type"], r["source"], r["target"]] for r in rows if r["observed"]),
        "entities": entities,
        "dead_letter_carriers": dead_letters,
        "unresolved_spans": len(batch.unresolved),
        "answers": answers,
    }


def _claim_shape(claim: dict) -> list:
    object_ref, delivery = claim["object"], claim["delivery"]
    return [
        f"{object_ref['type'].title()}:{object_ref['name']}",
        f"{delivery['via']['type'].title()}:{delivery['via']['name']}",
        delivery["subscription"]["name"] if delivery["subscription"] else None,
        claim["destination_resolution"],
        claim["qualification"],
    ]


# --- §13.3 per-fixture expected/forbidden facts ---------------------------------------------


@pytest.mark.parametrize("fixture", FIXTURES)
def test_fixture_matches_its_hand_authored_expectations(driver, fixture):
    expected = _expected(fixture)
    result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)

    assert result["sources"] == {
        slug: {"result": source["result"], "diagnostics": sorted(source["diagnostics"])}
        for slug, source in expected["sources"].items()
    }
    # exact in-scope fact multiset: anything unexpected (a minted DLQ target, RECEIVES_FROM a Topic,
    # a consumer-group Subscription, DEAD_LETTERS_TO) fails here
    assert result["facts"] == sorted(expected["facts"])
    assert result["observed"] == sorted(expected["observed"])
    assert result["entities"] == expected["entities"]
    assert result["dead_letter_carriers"] == sorted(expected["dead_letter_carriers"])
    assert result["unresolved_spans"] == expected["unresolved_spans"]

    for slug, answer in result["answers"].items():
        dependencies, drift = answer["dependencies"], answer["drift"]
        jsonschema.validate(instance=dependencies, schema=SCHEMAS["dependencies"])
        jsonschema.validate(instance=drift, schema=SCHEMAS["drift"])
        expected_answer = expected["answers"].get(slug, {"claims": [], "limitations": []})
        assert sorted(_claim_shape(c) for c in dependencies["claims"]) == sorted(
            expected_answer["claims"]
        ), slug
        assert sorted(lim["code"] for lim in dependencies["limitations"]) == sorted(
            expected_answer["limitations"]
        ), slug
        # drift is exactly the drift-qualified subset of the dependency claims (§12.5)
        assert drift["claims"] == [
            c
            for c in dependencies["claims"]
            if c["qualification"]
            in (Qualification.OBSERVED_ONLY.value, Qualification.NOT_OBSERVED_IN_WINDOW.value)
        ]
        if answer["evidence"] is not None:
            jsonschema.validate(instance=answer["evidence"], schema=SCHEMAS["evidence"])
            assert answer["evidence"]["data"]["missing_evidence_refs"] == []


@pytest.mark.parametrize("fixture", ["azure-service-bus"])
def test_queue_claims_keep_their_pre_i4_claim_ids(driver, fixture):
    """§14: Queue claim ids are unchanged by I4 - recomputed from the evaluator-owned reference
    five-field formula, never from production id code."""
    result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
    queue_claims = [
        c
        for c in result["answers"]["orders"]["dependencies"]["claims"]
        if c["delivery"]["via"]["type"] == "QUEUE"
    ]
    assert len(queue_claims) == 2  # competing consumers: one claim per logical Service, no fan-out
    for claim in queue_claims:
        assert claim["delivery"]["subscription"] is None
        assert claim["claim_id"] == identities.claim_id(
            subject_id="service:orders",
            predicate="DIRECT_DEPENDENCY",
            object_id=f"service:{claim['object']['name']}",
            delivery_kind="ASYNC_MESSAGE",
            delivery_via_id=claim["delivery"]["via"]["id"],
        )


# --- §13.4 public-surface parity and zero writes --------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", FIXTURES)
async def test_service_rest_and_mcp_agree_with_zero_graph_writes(driver, fixture):
    result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
    environment, _spans_unused = _spans(FIXTURES_ROOT / fixture)
    publisher = next(iter(_expected(fixture)["answers"]))
    direct = result["answers"][publisher]
    evidence_payload = {
        "evidence_refs": _answer_refs(direct["dependencies"]),
        "snapshot_id": direct["dependencies"]["snapshot"]["snapshot_id"],
    }
    service = _service(driver)
    with driver.session(database=DATABASE) as session:
        before = (
            read_revision(session),
            session.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        )

    client = _client(driver, service=service)
    params = {"environment": environment, "from": WINDOW_START, "to": WINDOW_END}
    rest = {
        "dependencies": client.get(
            f"/api/services/service:{publisher}/dependencies", params=params
        ),
        "drift": client.get(f"/api/services/service:{publisher}/drift", params=params),
        "evidence": client.post("/api/evidence/resolve", json=evidence_payload),
    }
    for name, response in rest.items():
        assert response.status_code == 200, name
        assert response.json() == direct[name], name

    server = MCPServer(name="test", version="0.5.0")
    register_tools(server, get_service=lambda: service)
    app = build_mcp_app(
        allowed_origins=[_ALLOWED_ORIGIN], allowed_hosts=[_ALLOWED_HOST], server=server
    )
    request = _request_payload(publisher, environment)
    async with mcp_session_manager_lifespan(server):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=_ALLOWED_ORIGIN) as http:
            listed = await http.post(
                "/mcp",
                headers=negotiated_headers(origin=_ALLOWED_ORIGIN),
                json=negotiated_tools_list_body(),
            )
            tools = listed.json()["result"]["tools"]
            mcp = {
                name: await call_negotiated(
                    http, origin=_ALLOWED_ORIGIN, name=tool, arguments={"request": arguments}
                )
                for name, tool, arguments in (
                    ("dependencies", "get_service_dependencies", request),
                    ("drift", "get_architecture_drift", request),
                    ("evidence", "get_evidence", evidence_payload),
                )
            }
    assert sorted(tool["name"] for tool in tools) == [
        "get_architecture_drift",
        "get_evidence",
        "get_service_dependencies",
    ]
    for name, response in mcp.items():
        assert response["isError"] is False, name
        assert response["structuredContent"] == direct[name], name

    with driver.session(database=DATABASE) as session:
        after = (
            read_revision(session),
            session.run("MATCH (n) RETURN count(n) AS c").single()["c"],
            session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"],
        )
    assert after == before


# --- §13.4 two clean runs, byte-identical -----------------------------------------------------


def _full_run(driver, roots: dict[str, Path], *, reverse_spans: bool = False) -> bytes:
    return canonical_json_bytes(
        {
            fixture: _qualify_fixture(driver, roots[fixture], fixture, reverse_spans=reverse_spans)
            for fixture in FIXTURES
        }
    )


def test_two_clean_full_qualification_runs_are_byte_identical(driver):
    roots = {fixture: FIXTURES_ROOT / fixture for fixture in FIXTURES}
    first = _full_run(driver, roots)
    second = _full_run(driver, roots)

    assert first == second
    # recorded for the slice-6 completion record; visible with `pytest -s`
    print(f"i4 qualification output sha256: {hashlib.sha256(first).hexdigest()}")


def test_qualification_is_independent_of_span_order(driver):
    roots = {fixture: FIXTURES_ROOT / fixture for fixture in FIXTURES}

    assert _full_run(driver, roots, reverse_spans=True) == _full_run(driver, roots)


def _without_snapshot_refs(value):
    if isinstance(value, dict):
        return {k: _without_snapshot_refs(v) for k, v in value.items() if k != "snapshot"}
    if isinstance(value, list):
        return [_without_snapshot_refs(v) for v in value]
    return value


def test_relocated_checkout_changes_only_the_snapshot_identity(driver, tmp_path):
    """Pre-existing, not I4: declared `Evidence.source_file` is the absolute document path and is
    part of the snapshot fingerprint, so a different checkout location is not "identical state"
    (§13.4) and yields a different `snapshot_id`. Every Pub/Sub fact, claim, claim id, evidence id,
    evidence record and diagnostic must still be identical."""
    for fixture in FIXTURES:
        shutil.copytree(FIXTURES_ROOT / fixture, tmp_path / fixture)
        here = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
        there = _qualify_fixture(driver, tmp_path / fixture, fixture)

        assert _without_snapshot_refs(there) == _without_snapshot_refs(here)
