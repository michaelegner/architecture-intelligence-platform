"""v0.6.1 I3a §6.1: deterministic Broker-semantic qualification of the Azure Service Bus, Google
Cloud Pub/Sub and Kafka fixtures.

Each fixture's declarations (`tests/fixtures/pubsub/<name>/declarations`, untouched: the I5 pin
freezes that tree) run end to end against real Neo4j through the same production path as the I4
qualification (`_qualify_fixture`). The Broker expectations are the hand-authored sibling files in
`tests/fixtures/broker-qualification/<name>/expected.yaml`; canonical Broker and claim ids come from
the evaluator-owned independent reference (`evaluation.architecture_answers.reference.identities`),
never from production id code. The I4 facts/entities/sources are re-asserted so the Broker adds no
Queue, Topic, Subscription or Message semantics beyond what each fixture already establishes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from evaluation.architecture_answers.reference import identities
from tests.integration.test_i4_pubsub_qualification import (
    DATABASE,
    FIXTURES,
    FIXTURES_ROOT,
    _expected,
    _qualify_fixture,
)
from tests.support.answer_schemas import validate_dependencies, validate_evidence

BROKER_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "broker-qualification"

_BROKER_STATE_QUERY = (
    "MATCH (b:Broker) RETURN b.id AS id, b.stable_broker_id AS stable ORDER BY b.id"
)
# §4.4: the Broker adds no destination topology - its only relations are incoming USES_BROKER, and
# no Message may exist that no destination CARRIES.
_BROKER_RELATIONS_QUERY = (
    "MATCH (b:Broker)-[r]-(other) "
    "RETURN type(r) AS type, startNode(r) = b AS outgoing, labels(other)[0] AS other"
)
_ORPHAN_MESSAGES_QUERY = "MATCH (m:Message) WHERE NOT ()-[:CARRIES]->(m) RETURN count(m) AS orphans"
_USES_BROKER_QUERY = (
    "MATCH (s:Service)-[r:USES_BROKER]->(b:Broker) "
    "RETURN s.id AS service, b.id AS broker, b.stable_broker_id AS stable ORDER BY s.id, b.id"
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _broker_expected(fixture: str) -> dict:
    return yaml.safe_load((BROKER_FIXTURES / fixture / "expected.yaml").read_text())


def _graph_state(driver) -> dict:
    with driver.session(database=DATABASE) as session:
        return {
            "brokers": [record.data() for record in session.run(_BROKER_STATE_QUERY)],
            "uses_broker": [record.data() for record in session.run(_USES_BROKER_QUERY)],
            "broker_relations": sorted(
                {
                    (r["type"], r["outgoing"], r["other"])
                    for r in session.run(_BROKER_RELATIONS_QUERY)
                }
            ),
            "orphan_messages": session.run(_ORPHAN_MESSAGES_QUERY).single()["orphans"],
        }


def _broker_claims(dependencies: dict) -> list[dict]:
    return [c for c in dependencies["claims"] if c["predicate"] == "USES_BROKER"]


def _broker_section(result: dict, state: dict) -> dict:
    """Everything Broker-related a run produced, for byte comparison across runs."""
    return {
        "graph": state,
        "answers": {
            slug: {
                "schema_version": answer["dependencies"]["schema_version"],
                "claims": _broker_claims(answer["dependencies"]),
                "broker_claim_ids": (answer["dependencies"]["data"] or {}).get(
                    "broker_claim_ids", []
                ),
                "drift_schema_version": answer["drift"]["schema_version"],
                "evidence_supports": sorted(
                    (record["id"], fact["relation_type"], fact["source_id"], fact["target_id"])
                    for record in (answer["evidence"] or {"data": {"records": []}})["data"][
                        "records"
                    ]
                    for fact in record["supports"]
                    if fact["relation_type"] == "USES_BROKER"
                ),
            }
            for slug, answer in sorted(result["answers"].items())
        },
    }


@pytest.mark.parametrize("fixture", FIXTURES)
def test_fixture_asserts_exactly_the_expected_brokers_and_uses_broker_facts(driver, fixture):
    expected = _broker_expected(fixture)
    assert expected["declarations"] == f"tests/fixtures/pubsub/{fixture}/declarations"
    base = _expected(fixture)

    result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
    state = _graph_state(driver)

    # the Broker entity: exactly the declared stable ids, with their independently derived ids
    assert {b["id"]: b["stable"] for b in state["brokers"]} == {
        identities.broker_id(stable): stable for stable in expected["brokers"]
    }
    # the Service -> Broker facts: exactly the expected multiset
    assert sorted((u["service"], u["stable"]) for u in state["uses_broker"]) == sorted(
        (f"service:{slug}", stable) for slug, stable in expected["uses_broker"]
    )

    # the Broker adds no topology: only incoming USES_BROKER from Services, and no orphan Message
    assert state["broker_relations"] == [("USES_BROKER", False, "Service")]
    assert state["orphan_messages"] == 0

    # no additional Queue/Topic/Subscription/Message semantics: the I4 expectations still hold
    assert result["facts"] == sorted(base["facts"])
    assert result["observed"] == sorted(base["observed"])
    assert result["entities"] == base["entities"]
    assert result["dead_letter_carriers"] == sorted(base["dead_letter_carriers"])
    assert result["sources"] == {
        slug: {"result": source["result"], "diagnostics": sorted(source["diagnostics"])}
        for slug, source in base["sources"].items()
    }


@pytest.mark.parametrize("fixture", FIXTURES)
def test_public_answers_carry_the_broker_claims_with_resolvable_evidence(driver, fixture):
    expected = _broker_expected(fixture)
    result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)

    by_service: dict[str, list[str]] = {}
    for slug, stable in expected["uses_broker"]:
        by_service.setdefault(slug, []).append(stable)

    for slug, answer in result["answers"].items():
        dependencies, drift, evidence = answer["dependencies"], answer["drift"], answer["evidence"]
        stables = by_service.get(slug, [])
        claims = _broker_claims(dependencies)
        if not stables:
            assert dependencies["schema_version"] == "0.5" and claims == []
            continue

        # a Broker-aware answer is the v0.6 shape; drift never carries a Broker claim
        assert dependencies["schema_version"] == "0.6", slug
        assert drift["schema_version"] == "0.5"
        assert not any(c["predicate"] == "USES_BROKER" for c in drift["claims"])
        validate_dependencies(dependencies)

        expected_claims = sorted(
            (
                identities.broker_claim_id(
                    service_id=f"service:{slug}", broker_id=identities.broker_id(stable)
                ),
                identities.broker_id(stable),
                stable,
            )
            for stable in stables
        )
        assert (
            sorted((c["claim_id"], c["object"]["id"], c["object"]["name"]) for c in claims)
            == expected_claims
        ), slug
        assert dependencies["data"]["broker_claim_ids"] == [c["claim_id"] for c in claims]
        for claim in claims:
            assert claim["object"]["type"] == "BROKER"
            assert claim["subject"]["id"] == f"service:{slug}"

        # every claim ref resolves at the same snapshot to the exact USES_BROKER fact
        assert evidence is not None and evidence["schema_version"] == "0.6"
        assert evidence["data"]["missing_evidence_refs"] == []
        assert evidence["snapshot"]["snapshot_id"] == dependencies["snapshot"]["snapshot_id"]
        validate_evidence(evidence)
        records = {record["id"]: record for record in evidence["data"]["records"]}
        for claim in claims:
            for ref in claim["evidence_refs"]:
                facts = [
                    (f["source_id"], f["target_id"], f["broker"]["name"], f["broker"]["type"])
                    for f in records[ref]["supports"]
                    if f["relation_type"] == "USES_BROKER"
                ]
                assert (
                    claim["subject"]["id"],
                    claim["object"]["id"],
                    claim["object"]["name"],
                    "BROKER",
                ) in facts, (slug, ref)


@pytest.mark.parametrize("fixture", FIXTURES)
def test_repeated_runs_are_byte_identical_for_the_broker_section(driver, fixture):
    first_result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
    first = canonical_json_bytes(_broker_section(first_result, _graph_state(driver)))
    second_result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture)
    second = canonical_json_bytes(_broker_section(second_result, _graph_state(driver)))
    reversed_result = _qualify_fixture(driver, FIXTURES_ROOT / fixture, fixture, reverse_spans=True)
    reordered = canonical_json_bytes(_broker_section(reversed_result, _graph_state(driver)))

    assert first == second == reordered
    # the full answers are byte-identical too (the I4 guarantee still holds with Broker claims)
    assert canonical_json_bytes(first_result["answers"]) == canonical_json_bytes(
        second_result["answers"]
    )
