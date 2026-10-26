"""v0.8 I2b B2/B3: the two-broker fixture gives exactly the I2 §8.2 table, plus its variants.

The fixture under `0.8.0/i2-vectors/two-broker/` is authored (not captured) and its
`expected.json` was written by hand from I2 §8.2 before the projection code. Integration because
capture acceptance, the attribution block, PUBLISHES_TO persistence and the snapshot are real.
"""

import json
import shutil
from pathlib import Path

import pytest

from .binding_picture_support import (
    DATABASE,
    KAFKA,
    LOCAL,
    SPEC,
    answer,
    capture,
    catalog,
    codes,
    directory,
    essentials,
    expected,
    mapping,
    run_import,
)

FIXTURE = SPEC / "i2-vectors/two-broker"
EXPECTED = expected(FIXTURE / "expected.json")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _key(row: dict) -> tuple:
    return (row["broker_id"], row["topic_name"], row.get("consumer_service_id") or "")


def _import(
    driver, *, declarations=None, kafka_capture=True, red_root=None, extra=None, check=True
) -> list:
    roots = declarations or {
        LOCAL: FIXTURE / "declarations/sokol111-local",
        KAFKA: FIXTURE / "declarations/sokol111-kafka",
    }
    captures = [capture(LOCAL, red_root or FIXTURE / "captures/redpanda")]
    if kafka_capture:
        captures.append(capture(KAFKA, FIXTURE / "captures/kafka"))
    sources = {
        "directories": [directory(f"decl-{b.split(':')[1]}", r) for b, r in roots.items()],
        "kafka_consumer_state": captures,
        "kafka_service_mappings": [
            mapping(LOCAL, FIXTURE / "mapping/sokol111-local"),
            mapping(KAFKA, FIXTURE / "mapping/sokol111-kafka"),
        ],
        "event_catalogs": [catalog()],
    }
    for key, values in (extra or {}).items():
        sources[key] = [*sources[key], *values]
    runs = run_import(driver, **sources)
    if check:
        assert all(run.stats.committed for run in runs), [r.configured_source_id for r in runs]
    return runs


def _expected_rows(broker: str | None = None) -> list[dict]:
    return sorted(
        (r for r in EXPECTED["rows"] if broker is None or r["broker_id"] == broker), key=_key
    )


def test_both_brokers_give_exactly_the_8_2_table(driver) -> None:
    _import(driver)
    result = answer(driver, broker_ids=[LOCAL, KAFKA])
    assert codes(result) == EXPECTED["limitations"]
    assert sorted(essentials(result), key=_key) == _expected_rows()
    # One topic name on two brokers is two Topic ids, never merged.
    product = {
        r["broker_id"]: r["topic_id"]
        for r in result["data"]["rows"]
        if r["topic_name"] == "catalog.product.events"
        and r["consumer_service_id"] == "service:ecommerce-image-service"
    }
    assert set(product) == {LOCAL, KAFKA} and product[LOCAL] != product[KAFKA]
    assert {s["broker_id"] for s in result["data"]["capture_sources"]} == {LOCAL, KAFKA}


def test_a_redpanda_only_request_keeps_the_crossing_and_the_delivery_limitation(driver) -> None:
    _import(driver)
    result = answer(driver, broker_ids=[LOCAL])
    assert sorted(essentials(result), key=_key) == _expected_rows(LOCAL)
    assert "CROSS_BROKER_DELIVERY_NOT_ESTABLISHED" in codes(result)
    [pq] = [
        r
        for r in result["data"]["rows"]
        if r["topic_name"] == "catalog.product.events"
        and r["consumer_service_id"] == "service:ecommerce-product-query-service"
    ]
    assert (pq["crossing"], pq["cross_broker_producers"]) == ("OUTBOUND", True)
    assert {b for p in pq["producers"] for b in p["broker_ids"]} == {KAFKA}


def test_a_missing_kafka_capture_gives_the_redpanda_rows_and_a_limitation(driver) -> None:
    _import(driver, kafka_capture=False)
    result = answer(driver, broker_ids=[LOCAL, KAFKA])
    assert "NO_ACCEPTED_CAPTURE" in codes(result)
    assert sorted(essentials(result), key=_key) == _expected_rows(LOCAL)


def _without_product_on_kafka(tmp_path: Path) -> Path:
    root = tmp_path / "decl-kafka"
    shutil.copytree(FIXTURE / "declarations/sokol111-kafka", root)
    for service in ("ecommerce-catalog-service", "ecommerce-image-service"):
        path = root / service / "asyncapi.yaml"
        text = path.read_text()
        start = text.index("  catalog.product.events:\n")
        end = text.find("\n  catalog.", start + 1)
        end = text.index("components:", start) if end == -1 else end + 1
        text = text[:start] + text[end:]
        path.write_text(text.replace("channels:\ncomponents:", "channels: {}\ncomponents:"))
    return root


@pytest.mark.parametrize("kafka_capture", [True, False])
def test_r7_and_r3_before_r7(driver, tmp_path, kafka_capture) -> None:
    roots = {
        LOCAL: FIXTURE / "declarations/sokol111-local",
        KAFKA: _without_product_on_kafka(tmp_path),
    }
    _import(driver, declarations=roots, kafka_capture=kafka_capture)
    result = answer(driver, broker_ids=[LOCAL, KAFKA])
    kafka_rows = [r for r in result["data"]["rows"] if r["broker_id"] == KAFKA]
    image = [
        r
        for r in kafka_rows
        if r["topic_name"] == "catalog.product.events"
        and r["consumer_service_id"] == "service:ecommerce-image-service"
    ]
    if kafka_capture:
        [row] = image
        assert (row["status"], row["reason"]) == ("UNRESOLVED", "TOPIC_NOT_DECLARED")
        assert "topic_id" not in row and "captured_at" not in row
    else:
        assert kafka_rows == []  # R3 before R7: no capture, no assessed row.
        assert "NO_ACCEPTED_CAPTURE" in codes(result)


def test_an_incomplete_capture_is_rejected_and_the_prior_state_is_used(driver, tmp_path) -> None:
    _import(driver)
    before = answer(driver, broker_ids=[LOCAL, KAFKA])
    red = tmp_path / "redpanda"
    red.mkdir()
    document = json.loads((FIXTURE / "captures/redpanda/kafka-consumer-state.json").read_text())
    document["complete"] = False
    document["captured_at"] = "2026-10-27T11:00:00Z"
    (red / "kafka-consumer-state.json").write_text(json.dumps(document))
    runs = _import(driver, red_root=red, check=False)
    [rejected] = [
        r
        for r in runs
        if r.kind == "kafka-consumer-state" and r.configured_source_id.endswith("local")
    ]
    assert not rejected.stats.committed
    after = answer(driver, broker_ids=[LOCAL, KAFKA])
    # The rejected capture is not used: the prior accepted Redpanda capture still answers.
    assert after["data"]["capture_sources"] == before["data"]["capture_sources"]
    assert sorted(essentials(after), key=_key) == _expected_rows()


def test_a_publisher_on_a_broker_of_another_environment_is_not_counted(driver, tmp_path) -> None:
    """Correction 2: the producer set comes only from brokers of the requested environment."""
    other = tmp_path / "decl-other" / "ecommerce-catalog-service"
    other.mkdir(parents=True)
    (other / "asyncapi.yaml").write_text(
        "asyncapi: '2.6.0'\ninfo:\n  title: ecommerce-catalog-service\n  version: \"1.0.0\"\n"
        "x-aip-service-id: service:ecommerce-catalog-service\nservers:\n  kafka:\n"
        "    url: other:9092\n    protocol: kafka\n    x-aip-broker-id: kafka:other\n"
        "channels:\n  tenant.tenant.events:\n    x-aip-destination-kind: topic\n"
        "    publish:\n      operationId: publishTenant\n"
    )
    prod = tmp_path / "capture-other"
    prod.mkdir()
    (prod / "kafka-consumer-state.json").write_text(
        json.dumps(
            {
                "schema": "aip-kafka-consumer-state/1",
                "broker_id": "kafka:other",
                "environment": "prod",
                "captured_at": "2026-10-27T10:00:00Z",
                "tool_version": "authored-fixture/1",
                "kafka_version": "not-established",
                "complete": True,
                "group_scope": ["other-group"],
                "groups": [{"group_id": "other-group", "state": "Empty", "members": []}],
            }
        )
    )
    other_capture = capture(LOCAL, prod, source_id="capture-other").model_copy(
        update={
            "broker_id": "kafka:other",
            "environment": "prod",
            "consumer_groups": ["other-group"],
        }
    )
    _import(
        driver,
        extra={
            "directories": [directory("decl-other", tmp_path / "decl-other")],
            "kafka_consumer_state": [other_capture],
        },
    )
    result = answer(driver, broker_ids=[LOCAL, KAFKA])
    assert sorted(essentials(result), key=_key) == _expected_rows()


def test_an_undeclared_catalog_service_stays_unresolved(driver, tmp_path) -> None:
    """Correction 1: without a declared Category Query Service, the catalog entry resolves to no
    Service, its attachments are R6 and no Service is minted."""
    local = tmp_path / "decl-local"
    shutil.copytree(FIXTURE / "declarations/sokol111-local", local)
    shutil.rmtree(local / "ecommerce-category-query-service")
    _import(driver, declarations={LOCAL: local, KAFKA: FIXTURE / "declarations/sokol111-kafka"})
    result = answer(driver, broker_ids=[LOCAL])
    rows = [
        r for r in result["data"]["rows"] if r.get("group_id") == "ecommerce-category-query-service"
    ]
    assert rows and all(
        (r["status"], r["reason"], r["crossing"])
        == ("UNRESOLVED", "SERVICE_NOT_DECLARED", "UNRESOLVED")
        and "consumer_service_id" not in r
        for r in rows
    )
    with driver.session(database=DATABASE) as session:
        names = {r["id"] for r in session.run("MATCH (s:Service) RETURN s.id AS id")}
    assert "service:ecommerce-category-query-service" not in names
