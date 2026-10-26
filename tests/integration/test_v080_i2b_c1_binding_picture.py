"""v0.8 I2b B1, the primary acceptance: C1 gives exactly the nine rows of I2 §8.1.

Inputs are the committed bytes: the I1 Redpanda declarations, the Redpanda mapping, the real C1
capture and the generated EventCatalog. `c1-expected.json` was written by hand from I2 §8.1 before
the projection code. Everything goes through the production import and the service.
"""

import pytest

from .binding_picture_support import (
    DATABASE,
    I1,
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

EXPECTED = expected(SPEC / "i2-vectors/c1-expected.json")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _sort(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (r["broker_id"], r["topic_name"], r["consumer_service_id"]))


def test_c1_gives_exactly_the_nine_rows_of_i2_8_1(driver) -> None:
    runs = run_import(
        driver,
        directories=[directory("decl-local", I1 / "declarations/sokol111-local")],
        kafka_consumer_state=[capture(LOCAL, I1 / "c1")],
        kafka_service_mappings=[mapping(LOCAL, I1 / "mapping/sokol111-local")],
        event_catalogs=[catalog()],
    )
    assert all(run.stats.committed for run in runs)
    result = answer(driver, broker_ids=[LOCAL])
    assert result["outcome"] == "PARTIAL"
    assert codes(result) == sorted(EXPECTED["limitations"])
    rows = essentials(result)
    assert len(rows) == 9
    assert _sort(rows) == _sort(EXPECTED["rows"])
    # The answer order is the documented sort: broker, topic name, consumer.
    assert rows == _sort(rows)
    for row in result["data"]["rows"]:
        assert row["status"] not in {"CONTRADICTED", "OBSERVED_NOT_PROMISED"}
        assert row["attachment_evidence_refs"] and row["mapping_evidence_refs"]
        assert all(ref.startswith("binding-evidence:") for ref in row["attachment_evidence_refs"])
        if row["status"] == "PROMISED_AND_OBSERVED":
            assert row["promise_evidence_refs"] and row["declared_event_types"]
        else:
            assert row["promise_evidence_refs"] == [] and row["declared_event_types"] == []
