"""v0.5.0 I4 slice 2b: real-Neo4j persistence of declared Topic/Subscription topology through the
existing I1 ownership/replay/removal engine (spec §10, §11), end to end from AsyncAPI files."""

from pathlib import Path

import pytest
import yaml

from app.architecture_intelligence.repository import (
    canonical_snapshot_state,
    read_evidence_rows,
    snapshot_fingerprint,
)
from app.graph.importer import import_all_sources
from app.graph.revision_fence import read_revision
from app.graph.schema import ensure_schema
from app.sources.migration_mappings import load_migration_mappings
from app.sources.model import DiagnosticCode, FilesystemSourceConfig, IngestionResult
from app.sources.owner_ids import topic_owned_id

DATABASE = "neo4j"
BROKER = "gcp-pubsub:projects/commerce"
TOPIC_ID = topic_owned_id(
    stable_broker_id=BROKER, normalized_namespace_or_empty="", exact_topic_address="orders"
)


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


def _count(driver, query: str) -> int:
    with driver.session(database=DATABASE) as session:
        return session.run(query).single()["c"]


def _doc(service: str, *, publish=False, subscription: str | None = None, dead_letter=None):
    channel: dict = {"x-aip-destination-kind": "topic"}
    message = {"$ref": "#/components/messages/OrderCreated"}
    if publish:
        channel["publish"] = {"message": message}
    if subscription is not None:
        channel["subscribe"] = {"message": message, "x-aip-subscription-name": subscription}
        if dead_letter is not None:
            channel["subscribe"]["x-aip-subscription-dead-letter"] = dead_letter
    return {
        "asyncapi": "2.6.0",
        "info": {"title": service, "version": "1.0.0"},
        "x-aip-service-id": f"service:{service}",
        "servers": {
            "gcp": {
                "url": "pubsub.googleapis.com",
                "protocol": "googlepubsub",
                "x-aip-broker-id": BROKER,
            }
        },
        "channels": {"orders": channel},
        "components": {
            "messages": {
                "OrderCreated": {
                    "name": "OrderCreated",
                    "x-version": "v1",
                    "payload": {"type": "object", "properties": {"id": {"type": "string"}}},
                }
            }
        },
    }


def _write(root: Path, service: str, document: dict) -> None:
    path = root / service / "asyncapi.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(document, sort_keys=False))


def _import(driver, root: Path, **kwargs):
    stats = import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(id="pubsub-test", root=root),
        **kwargs,
    )
    return stats


def _pubsub_scene(root: Path) -> None:
    _write(root, "orders", _doc("orders", publish=True))
    _write(
        root,
        "billing",
        _doc(
            "billing",
            subscription="billing",
            dead_letter={"target": "orders-dlq", "targetKind": "topic"},
        ),
    )
    _write(root, "shipping", _doc("shipping", subscription="shipping"))


def _snapshot(driver):
    with driver.session(database=DATABASE) as session:
        state = canonical_snapshot_state(session, coverage_qualification_enabled=True)
    return state, snapshot_fingerprint(state)[0]


def test_import_persists_topic_subscriptions_carriers_and_the_four_relations(driver, tmp_path):
    _pubsub_scene(tmp_path)
    stats = _import(driver, tmp_path)
    assert stats.committed is True

    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 1
    assert _count(driver, "MATCH (s:Subscription) RETURN count(s) AS c") == 2
    assert (
        _count(
            driver,
            f"MATCH (:Service {{id: 'service:orders'}})-[:PUBLISHES_TO]->(:Topic {{id: '{TOPIC_ID}'}}) RETURN count(*) AS c",
        )
        == 1
    )
    assert (
        _count(driver, "MATCH (:Subscription)-[:SUBSCRIPTION_OF]->(:Topic) RETURN count(*) AS c")
        == 2
    )
    assert (
        _count(driver, "MATCH (:Service)-[:RECEIVES_FROM]->(:Subscription) RETURN count(*) AS c")
        == 2
    )
    # Message identity is owner-scoped per declaring Service (I1 §9.1), so each of the three
    # documents carries its own Message on the shared Topic.
    assert _count(driver, "MATCH (:Topic)-[:CARRIES]->(:Message) RETURN count(*) AS c") == 3
    # fan-out is only the two distinct Subscription paths; no Service consumes the Topic directly
    assert _count(driver, "MATCH (:Service)-[:RECEIVES_FROM]->(:Topic) RETURN count(*) AS c") == 0
    # internal carriers: one Topic declaration per declaring source + one per Subscription
    assert _count(driver, "MATCH (d:PubSubDeclaration) RETURN count(d) AS c") == 5
    assert _count(driver, "MATCH (c:SubscriptionDeadLetterConfiguration) RETURN count(c) AS c") == 1
    assert (
        _count(driver, "MATCH (c:SubscriptionDeadLetterConfiguration)-[r]-() RETURN count(r) AS c")
        == 0
    )
    assert _count(driver, "MATCH ()-[r:DEAD_LETTERS_TO]->() RETURN count(r) AS c") == 0


def test_unchanged_replay_is_a_no_op(driver, tmp_path):
    _pubsub_scene(tmp_path)
    _import(driver, tmp_path)
    with driver.session(database=DATABASE) as session:
        revision_before = read_revision(session)
    _, snapshot_before = _snapshot(driver)
    _import(driver, tmp_path)
    with driver.session(database=DATABASE) as session:
        assert read_revision(session) == revision_before
    assert _snapshot(driver)[1] == snapshot_before


def test_removing_a_subscribe_operation_expires_only_that_subscription(driver, tmp_path):
    _pubsub_scene(tmp_path)
    _import(driver, tmp_path)
    # subscribe removed (billing now only publishes, so the source stays supported)
    _write(tmp_path, "billing", _doc("billing", publish=True))
    stats = _import(driver, tmp_path)
    assert stats.committed is True

    names = {
        r["n"]
        for r in driver.session(database=DATABASE).run("MATCH (s:Subscription) RETURN s.name AS n")
    }
    assert names == {"shipping"}
    assert _count(driver, "MATCH (c:SubscriptionDeadLetterConfiguration) RETURN count(c) AS c") == 0
    assert (
        _count(
            driver, "MATCH (d:PubSubDeclaration {entity_kind: 'SUBSCRIPTION'}) RETURN count(d) AS c"
        )
        == 1
    )
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 1


def test_shared_topic_survives_until_its_last_owner_withdraws(driver, tmp_path):
    _pubsub_scene(tmp_path)
    _import(driver, tmp_path)
    import shutil

    shutil.rmtree(tmp_path / "orders")
    shutil.rmtree(tmp_path / "billing")
    _import(driver, tmp_path)
    assert _count(driver, "MATCH (t:Topic) RETURN count(t) AS c") == 1  # still owned by shipping

    shutil.rmtree(tmp_path / "shipping")
    _write(tmp_path, "other", {**_doc("other"), "channels": {}})
    _import(driver, tmp_path)
    for label in (
        "Topic",
        "Subscription",
        "PubSubDeclaration",
        "SubscriptionDeadLetterConfiguration",
    ):
        assert _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") == 0


def test_cross_source_subscription_topic_disagreement_commits_nothing(driver, tmp_path):
    """I4 §4.2/§6.2: two sources binding one configured Subscription id to two different Topics.
    Each source is internally consistent; only the cross-source view sees it - REJECTED_CONFLICT for
    both, and the run commits nothing (no precedence)."""
    from app.ingestion.orchestrator import run_filesystem_discovery

    channels = {"a": "orders", "b": "invoices"}
    for service, channel in channels.items():
        document = _doc(service, subscription="shared")
        subscribe = document["channels"].pop("orders")
        del subscribe["subscribe"]["x-aip-subscription-name"]
        document["channels"] = {channel: subscribe}
        document["servers"]["gcp"].pop("x-aip-broker-id")  # identity comes only from config
        _write(tmp_path, service, document)

    config = FilesystemSourceConfig(id="pubsub-test", root=tmp_path)
    discovered = run_filesystem_discovery(config)
    topic_entries, subscription_entries = [], []
    for sid, outcome in discovered.source_outcomes.items():
        document_path = Path(outcome.descriptor_locator).relative_to(tmp_path).as_posix()
        channel = channels[document_path.split("/")[0]]
        topic_id = f"topic:configured-{channel}"
        base = {"sourceInstanceId": sid, "documentPath": document_path}
        topic_entries.append({**base, "pointer": f"/channels/{channel}", "topicId": topic_id})
        subscription_entries.append(
            {
                **base,
                "pointer": f"/channels/{channel}/subscribe",
                "topicId": topic_id,
                "subscriptionName": "shared",
                "subscriptionId": "subscription:configured-shared",
            }
        )
    mappings = tmp_path.parent / f"{tmp_path.name}-mappings.yaml"
    mappings.write_text(
        yaml.safe_dump(
            {
                "apiVersion": "aip.dev/v1",
                "kind": "AipSharedIdentityMappings",
                "metadata": {"id": "pubsub-conflict", "revision": "v1"},
                "topicMappings": topic_entries,
                "subscriptionMappings": subscription_entries,
            }
        )
    )
    index, diagnostics = load_migration_mappings([mappings])
    assert diagnostics == ()

    run = run_filesystem_discovery(config, migration_mappings=index)
    assert run.commit_eligible is False
    assert {o.outcome.result for o in run.source_outcomes.values()} == {
        IngestionResult.REJECTED_CONFLICT
    }
    stats = _import(driver, tmp_path, migration_mappings=index)
    assert stats.committed is False
    assert DiagnosticCode.SUBSCRIPTION_IDENTITY_CONFLICT in {d.code for d in stats.diagnostics}
    for label in ("Topic", "Subscription", "Service"):
        assert _count(driver, f"MATCH (n:{label}) RETURN count(n) AS c") == 0


def test_topic_state_moves_the_snapshot_but_internal_carriers_do_not(driver, tmp_path):
    _write(tmp_path, "orders", _doc("orders", publish=True))
    _import(driver, tmp_path)
    state, with_topic = _snapshot(driver)
    assert [t["id"] for t in state["topics"]] == [TOPIC_ID]
    assert state["version"] == 3

    # mutate only an internal carrier property: the public snapshot must not move
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (d:PubSubDeclaration) SET d.semantic_input_digest = 'mutated'")
    assert _snapshot(driver)[1] == with_topic

    with driver.session(database=DATABASE) as session:
        session.run("MATCH (t:Topic) SET t.name = 'renamed'")
    assert _snapshot(driver)[1] != with_topic


def test_evidence_supports_include_pubsub_relations(driver, tmp_path):
    _pubsub_scene(tmp_path)
    _import(driver, tmp_path)
    with driver.session(database=DATABASE) as session:
        evidence_ids = [r["id"] for r in session.run("MATCH (e:Evidence) RETURN e.id AS id")]
        rows = read_evidence_rows(session, evidence_ids=evidence_ids)
    relation_types = {relation["type"] for relation in rows["relations"]}
    assert {"PUBLISHES_TO", "SUBSCRIPTION_OF", "RECEIVES_FROM", "CARRIES"} <= relation_types


def test_pubsub_constraints_exist(driver):
    with driver.session(database=DATABASE) as session:
        ensure_schema(session)
        names = {r["name"] for r in session.run("SHOW CONSTRAINTS YIELD name RETURN name")}
    assert {
        "topic_id",
        "subscription_id",
        "pubsub_declaration_id",
        "subscription_dead_letter_configuration_id",
    } <= names
