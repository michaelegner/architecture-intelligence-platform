"""v0.6.1 I3a §6.1: Broker negatives through the real pipeline on real Neo4j.

Each case imports authored declarations with `import_all_sources` (the production path) and asserts
the persisted graph and the public answer. The deterministic adapter-level versions of the same
rules already live in `tests/unit/test_asyncapi_adapter_broker.py` and
`tests/unit/test_manifest_adapter_broker.py`; these cases confirm them at the pipeline level instead
of duplicating them. A Broker is evidenced only by an explicit stable `x-aip-broker-id` on the
selected server of an admitted channel; anything ambiguous, missing or mapping-only yields none, and
two independently evidenced Brokers for one Service are valid (no false conflict).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from app.architecture_intelligence.broker_contracts import BrokerClaim
from app.architecture_intelligence.contracts import ArchitectureAnswer
from app.architecture_intelligence.request import ServiceDependenciesRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_all_sources
from app.ingestion.orchestrator import run_filesystem_discovery
from app.sources.migration_mappings import load_migration_mappings
from app.sources.model import DiagnosticCode, FilesystemSourceConfig
from evaluation.architecture_answers.reference import identities
from tests.integration.test_broker_architecture_intelligence import (
    CONTEXT,
    DATABASE,
    PRODUCER,
)
from tests.integration.test_pubsub_persistence import _doc, _import, _write
from tests.support.answer_schemas import validate_dependencies

GOOD = "kafka:good"
OTHER = "kafka:other"
A, B = "kafka:conflict-a", "kafka:conflict-b"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _server(broker_id: str | None) -> dict:
    server: dict = {"url": "broker.example", "protocol": "kafka"}
    if broker_id is not None:
        server["x-aip-broker-id"] = broker_id
    return server


def _document(service: str, servers: dict, channels: dict[str, list[str] | None]) -> dict:
    """An AsyncAPI document whose topic channels each publish and select the named servers."""
    document = _doc(service, publish=True)
    template = document["channels"]["orders"]
    template.pop("servers", None)
    document["servers"] = servers
    document["channels"] = {}
    for name, selected in channels.items():
        channel = json.loads(json.dumps(template))
        if selected is not None:
            channel["servers"] = selected
        document["channels"][name] = channel
    return document


def _graph(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        return {
            "brokers": sorted(
                r["stable"]
                for r in session.run("MATCH (b:Broker) RETURN b.stable_broker_id AS stable")
            ),
            "topics": sorted(r["n"] for r in session.run("MATCH (t:Topic) RETURN t.name AS n")),
            "uses": session.run("MATCH ()-[r:USES_BROKER]->() RETURN count(r) AS c").single()["c"],
        }


def _answer(driver, service: str):
    return ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=PRODUCER
    ).get_service_dependencies(
        ServiceDependenciesRequest.model_validate(
            {"service_id": f"service:{service}", "observation_context": CONTEXT}
        )
    )


def _claim_brokers(answer) -> list[str]:
    return sorted(c.object.name for c in answer.claims if isinstance(c, BrokerClaim))


def _import_ok(driver, root: Path):
    stats = _import(driver, root)
    assert stats.committed is True, stats.diagnostics
    return stats


def test_a_channel_without_broker_identity_yields_no_broker_for_it(driver, tmp_path):
    document = _document(
        "svc", {"good": _server(GOOD), "anon": _server(None)}, {"ok": ["good"], "no-id": ["anon"]}
    )
    _write(tmp_path, "svc", document)
    _import_ok(driver, tmp_path)

    # only the identified channel is admitted: its Topic and its Broker exist, the other none
    assert _graph(driver) == {"brokers": [GOOD], "topics": ["ok"], "uses": 1}
    answer = _answer(driver, "svc")
    assert answer.schema_version == "0.6" and _claim_brokers(answer) == [GOOD]
    validate_dependencies(json.loads(answer.model_dump_json()))


def test_conflicting_explicit_ids_for_one_construct_yield_no_broker_for_it(driver, tmp_path):
    document = _document(
        "svc",
        {"good": _server(GOOD), "a": _server(A), "b": _server(B)},
        {"ok": ["good"], "conflict": ["a", "b"]},
    )
    _write(tmp_path, "svc", document)
    stats = _import_ok(driver, tmp_path)

    # no precedence: neither conflicting id becomes a Broker, and the construct has no Topic either
    assert _graph(driver) == {"brokers": [GOOD], "topics": ["ok"], "uses": 1}
    assert DiagnosticCode.AMBIGUOUS in {d.code for d in _source_diagnostics(driver, tmp_path)}
    assert stats.committed is True
    answer = _answer(driver, "svc")
    assert answer.schema_version == "0.6" and _claim_brokers(answer) == [GOOD]


def test_ambiguous_multi_server_selection_yields_no_broker_for_it(driver, tmp_path):
    document = _document(
        "svc",
        {"good": _server(GOOD), "partial": _server(OTHER), "anon": _server(None)},
        {"ok": ["good"], "ambiguous": ["partial", "anon"]},
    )
    _write(tmp_path, "svc", document)
    _import_ok(driver, tmp_path)

    # only some selected servers carry an id: ambiguous, so neither OTHER nor a Topic exists for it
    assert _graph(driver) == {"brokers": [GOOD], "topics": ["ok"], "uses": 1}
    answer = _answer(driver, "svc")
    assert answer.schema_version == "0.6" and _claim_brokers(answer) == [GOOD]


def _topic_mapping_index(tmp_path: Path, channel: str, topic_id: str):
    """A `topicMappings` document for `channel` of the single authored source (two-pass: discover to
    learn the source instance id, then write the mapping keyed by it)."""
    discovered = run_filesystem_discovery(FilesystemSourceConfig(id="pubsub-test", root=tmp_path))
    entries = [
        {
            "sourceInstanceId": source_instance_id,
            "documentPath": Path(outcome.descriptor_locator).relative_to(tmp_path).as_posix(),
            "pointer": f"/channels/{channel}",
            "topicId": topic_id,
        }
        for source_instance_id, outcome in discovered.source_outcomes.items()
    ]
    mappings = tmp_path.parent / f"{tmp_path.name}-mappings.yaml"
    mappings.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "AipSharedIdentityMappings",
                "metadata": {"id": "broker-negative", "revision": "v1"},
                "topicMappings": entries,
            }
        )
    )
    index, diagnostics = load_migration_mappings([mappings])
    assert diagnostics == ()
    return index


def test_a_destination_mapping_never_papers_over_conflicting_broker_identity(driver, tmp_path):
    """Spec §4.2: a Queue/Topic mapping must not hide an ambiguous broker identity. The construct
    selects two servers with conflicting explicit ids; a `topicMappings` entry for it changes
    nothing - no Topic, no Broker, no `USES_BROKER` for that construct."""
    document = _document(
        "svc",
        {"good": _server(GOOD), "a": _server(A), "b": _server(B)},
        {"ok": ["good"], "conflict": ["a", "b"]},
    )
    _write(tmp_path, "svc", document)
    index = _topic_mapping_index(tmp_path, "conflict", "topic:configured-conflict")

    stats = _import(driver, tmp_path, migration_mappings=index)
    assert stats.committed is True, stats.diagnostics
    assert _graph(driver) == {"brokers": [GOOD], "topics": ["ok"], "uses": 1}
    answer = _answer(driver, "svc")
    assert answer.schema_version == "0.6" and _claim_brokers(answer) == [GOOD]


def test_a_destination_mapping_without_stable_broker_identity_yields_no_broker(driver, tmp_path):
    document = _document("svc", {"anon": _server(None)}, {"mapped": ["anon"]})
    _write(tmp_path, "svc", document)
    index = _topic_mapping_index(tmp_path, "mapped", "topic:configured-mapped")

    stats = _import(driver, tmp_path, migration_mappings=index)
    assert stats.committed is True, stats.diagnostics
    # the mapping supplies the Topic's identity but never a Broker's
    assert _graph(driver) == {"brokers": [], "topics": ["mapped"], "uses": 0}
    answer = _answer(driver, "svc")
    assert isinstance(answer, ArchitectureAnswer) and answer.schema_version == "0.5"
    assert not any(c.predicate.value == "USES_BROKER" for c in answer.claims)


def test_an_unresolved_manifest_service_commits_nothing_and_writes_no_broker(driver, tmp_path):
    path = tmp_path / "ghost" / "architecture.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        yaml.safe_dump(
            {
                "service": "ghost",
                "x-aip-service-id": "service:ghost",
                "brokers": [{"brokerId": GOOD}],
            }
        )
    )
    stats = import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(id="pubsub-test", root=tmp_path),
    )
    assert stats.committed is False
    assert DiagnosticCode.MANIFEST_CALL_SOURCE_UNRESOLVED in {d.code for d in stats.diagnostics}
    with driver.session(database=DATABASE) as session:
        count = session.run("MATCH (n) WHERE NOT n:AipInternalState RETURN count(n) AS c").single()[
            "c"
        ]
    assert count == 0


def test_two_independently_evidenced_brokers_for_one_service_are_valid(driver, tmp_path):
    document = _document(
        "svc", {"one": _server(GOOD), "two": _server(OTHER)}, {"first": ["one"], "second": ["two"]}
    )
    _write(tmp_path, "svc", document)
    _import_ok(driver, tmp_path)

    assert _graph(driver) == {
        "brokers": sorted([GOOD, OTHER]),
        "topics": ["first", "second"],
        "uses": 2,
    }
    # no false conflict: no ambiguity/conflict diagnostic, and the answer keeps both claims
    codes = {d.code for d in _source_diagnostics(driver, tmp_path)}
    assert DiagnosticCode.AMBIGUOUS not in codes
    answer = _answer(driver, "svc")
    assert answer.schema_version == "0.6"
    assert _claim_brokers(answer) == sorted([GOOD, OTHER])
    assert {c.claim_id for c in answer.claims if isinstance(c, BrokerClaim)} == {
        identities.broker_claim_id(service_id="service:svc", broker_id=identities.broker_id(stable))
        for stable in (GOOD, OTHER)
    }


def _source_diagnostics(driver, root: Path):
    """The adapter diagnostics of a fresh discovery of `root` (the same inputs just imported)."""
    run = run_filesystem_discovery(FilesystemSourceConfig(id="pubsub-test", root=root))
    return [d for o in run.source_outcomes.values() for d in o.outcome.diagnostics]
