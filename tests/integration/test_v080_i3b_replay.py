"""v0.8 I3b C6/C7: the frozen live-run package replays to the reference committed before the run.

Inputs are the committed bytes of `0.8.0/i3-evidence/`: the after-wave declarations, the real A-R
(Redpanda) and A-K (Kafka) captures and the real C1-prime capture, with the I1 mappings and the I1
EventCatalog used unchanged (I3 §7). `expected-after.json` was committed in I3a with its digest,
before any capture was taken. Everything goes through the production import and the service.
"""

import hashlib
import subprocess

import pytest

from .binding_picture_support import (
    DATABASE,
    I1,
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

PACKAGE = SPEC / "i3-evidence"
EXPECTED_AFTER = expected(PACKAGE / "expected-after.json")
C1_EXPECTED = expected(SPEC / "i2-vectors/c1-expected.json")


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


def _key(row: dict) -> tuple:
    return (row["broker_id"], row["topic_name"], row.get("consumer_service_id") or "")


def _after_wave(driver) -> list:
    return run_import(
        driver,
        directories=[
            directory("decl-local", PACKAGE / "declarations/sokol111-local"),
            directory("decl-kafka", PACKAGE / "declarations/sokol111-kafka"),
        ],
        kafka_consumer_state=[
            capture(LOCAL, PACKAGE / "captures/a-r"),
            capture(KAFKA, PACKAGE / "captures/a-k"),
        ],
        kafka_service_mappings=[
            mapping(LOCAL, I1 / "mapping/sokol111-local"),
            mapping(KAFKA, I1 / "mapping/sokol111-kafka"),
        ],
        event_catalogs=[catalog()],
    )


def test_the_reference_and_the_package_are_the_committed_bytes() -> None:
    # C7: the reference digest committed in I3a, before the run.
    digest = hashlib.sha256((PACKAGE / "expected-after.json").read_bytes()).hexdigest()
    assert (PACKAGE / "expected-after.sha256").read_text() == f"{digest}  expected-after.json\n"
    # The frozen run files match their manifest.
    subprocess.run(["sha256sum", "-c", "--quiet", "SHA256SUMS"], cwd=PACKAGE, check=True)


def test_the_after_wave_captures_replay_to_expected_after(driver) -> None:
    runs = _after_wave(driver)
    assert all(run.stats.committed for run in runs), [r.configured_source_id for r in runs]
    result = answer(driver, broker_ids=[LOCAL, KAFKA])
    assert codes(result) == EXPECTED_AFTER["limitations"]
    assert sorted(essentials(result), key=_key) == sorted(EXPECTED_AFTER["rows"], key=_key)
    assert {s["broker_id"] for s in result["data"]["capture_sources"]} == {LOCAL, KAFKA}

    # A second import of the same frozen bytes is a no-op: committed, no graph revision advance,
    # the same answer.
    again = _after_wave(driver)
    assert all(run.stats.committed for run in again)
    per_source = [stats for run in again for stats in run.stats.per_source.values()]
    assert per_source and not any(stats.graph_revision_advanced for stats in per_source)
    assert answer(driver, broker_ids=[LOCAL, KAFKA])["data"] == result["data"]


def test_c1_prime_gives_the_nine_rows_of_i2_8_1(driver) -> None:
    runs = run_import(
        driver,
        directories=[directory("decl-local", I1 / "declarations/sokol111-local")],
        kafka_consumer_state=[capture(LOCAL, PACKAGE / "captures/c1-prime")],
        kafka_service_mappings=[mapping(LOCAL, I1 / "mapping/sokol111-local")],
        event_catalogs=[catalog()],
    )
    assert all(run.stats.committed for run in runs)
    result = answer(driver, broker_ids=[LOCAL])
    assert codes(result) == sorted(C1_EXPECTED["limitations"])
    rows = essentials(result)
    assert len(rows) == 9
    assert sorted(rows, key=_key) == sorted(C1_EXPECTED["rows"], key=_key)
