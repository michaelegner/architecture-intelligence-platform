"""v0.7.1 I2.2: Kafka Service-mapping registration, ids, artifact contract, loader, discoverer and
adapter. Expected values come from the hand-authored I2.1 vectors
(`docs/specifications/0.7.1/i2-vectors/`), loaded from the files, not re-derived from the production
formulas."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.ingestion.kafka_service_mapping_adapter import KafkaServiceMappingSourceAdapter
from app.ingestion.kafka_service_mapping_discoverer import KafkaServiceMappingSourceDiscoverer
from app.ingestion.orchestrator import run_kafka_service_mapping_discovery
from app.settings import SourcesConfig
from app.sources.identity import (
    kafka_consumer_id,
    kafka_service_mapping_entry_id,
    kafka_service_mapping_evidence_id,
    kafka_service_mapping_source_instance_id,
    kafka_service_mapping_source_revision,
)
from app.sources.kafka_service_mapping_contract import MAX_ENTRIES, duplicate_registrations
from app.sources.kafka_service_mapping_loader import (
    MAX_ARTIFACT_BYTES,
    LoadedMappingArtifact,
    RejectedMappingArtifact,
    load_mapping_artifact,
)
from app.sources.model import (
    DiagnosticCode,
    IngestionResult,
    KafkaServiceMappingSourceConfig,
    SourceKind,
)

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.1/i2-vectors"
EXAMPLE = json.loads((VECTORS / "kafka-service-mapping.example.json").read_text())
IDS = json.loads((VECTORS / "ids.json").read_text())
I1_IDS = json.loads((VECTORS.parent / "i1-vectors/ids.json").read_text())
REJECTIONS = {
    c["id"]: c for c in json.loads((VECTORS / "mapping-rejections.json").read_text())["cases"]
}
BROKER, ENV = IDS["inputs"]["broker_id"], IDS["inputs"]["environment"]
CANARY = "CANARY-KSM-VALUE-3c1f"
CANARY_KEY = "CANARY-KSM-KEY-8e02"


def _config(root: Path, **overrides: object) -> KafkaServiceMappingSourceConfig:
    values: dict[str, object] = {
        "id": "map-a",
        "root": root,
        "broker_id": BROKER,
        "environment": ENV,
    }
    values.update(overrides)
    return KafkaServiceMappingSourceConfig.model_validate(values)


def _write(root: Path, document: object) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "kafka-service-mapping.json"
    path.write_text(document if isinstance(document, str) else json.dumps(document))
    return path


def _load(tmp_path: Path, document: object, **overrides: object):
    _write(tmp_path, document)
    return load_mapping_artifact(_config(tmp_path, **overrides))


def _code(result) -> str:
    assert isinstance(result, RejectedMappingArtifact)
    return result.problem.code


def _outcome(run):
    [source] = run.source_outcomes.values()
    return source.outcome


# ---- registration and ids (M01-M09) -----------------------------------------------------------


def test_known_answer_ids_match_the_vectors() -> None:
    v = IDS["vectors"]
    map_a = kafka_service_mapping_source_instance_id(
        configured_source_id="map-a", broker_id=BROKER, environment=ENV
    )
    assert map_a == v["M01_source_instance_map_a"]
    assert (
        kafka_service_mapping_source_instance_id(
            configured_source_id="map-b", broker_id=BROKER, environment=ENV
        )
        == v["M02_source_instance_map_b"]
    )
    assert (
        kafka_service_mapping_source_instance_id(
            configured_source_id="map-a", broker_id=BROKER, environment="staging"
        )
        == v["M03_source_instance_other_environment"]
    )
    assert (
        kafka_service_mapping_entry_id(source_instance_id=map_a, group_id="payment-service")
        == v["M04_entry_map_a_payment"]
    )
    assert (
        kafka_service_mapping_entry_id(source_instance_id=map_a, group_id="order-service")
        == v["M05_entry_map_a_order"]
    )
    assert kafka_service_mapping_evidence_id(map_a) == v["M06_evidence_map_a"]
    join_key = kafka_consumer_id(broker_id=BROKER, environment=ENV, group_id="payment-service")
    assert join_key == v["M07_join_key_payment_equals_i1_k05"]
    assert join_key == I1_IDS["vectors"]["K05_consumer_payment"]
    assert (
        kafka_consumer_id(broker_id=BROKER, environment=ENV, group_id="Payment-Service")
        == v["M08_join_key_case_is_exact"]
    )
    assert (
        kafka_service_mapping_source_revision(hashlib.sha256(b"example").hexdigest())
        == v["M09_source_revision_example"]
    )


def test_registration_defaults_and_no_mapping_source_by_default(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert config.artifact_relative_path == "kafka-service-mapping.json"
    assert SourceKind.KAFKA_SERVICE_MAPPING.value == "kafka_service_mapping"
    assert SourcesConfig().kafka_service_mappings == []


def test_only_a_shared_id_is_a_duplicate_registration(tmp_path: Path) -> None:
    a, b = _config(tmp_path), _config(tmp_path, id="map-b")
    assert duplicate_registrations([a, b]) == frozenset()  # separate authorities (I2 §3)
    assert duplicate_registrations([a, b, _config(tmp_path, environment="staging")]) == {"map-a"}


# ---- artifact acceptance --------------------------------------------------------------------


def test_example_artifact_is_accepted_with_its_content_revision(tmp_path: Path) -> None:
    path = _write(tmp_path, EXAMPLE)
    result = load_mapping_artifact(_config(tmp_path))
    assert isinstance(result, LoadedMappingArtifact)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.content_sha256 == digest
    assert result.source_revision == f"artifact-sha256:{digest}"
    assert [m.group_id for m in result.artifact.mappings] == ["order-service", "payment-service"]


def test_values_are_kept_exactly_and_namespace_is_optional(tmp_path: Path) -> None:
    document = copy.deepcopy(EXAMPLE)
    document["mappings"] = [
        {"group_id": "Payment-Service", "service_name": " Orders ", "service_namespace": "shop"},
        {"group_id": "payment-service", "service_name": "payment-service"},
    ]
    result = _load(tmp_path, document)
    assert isinstance(result, LoadedMappingArtifact)
    first, second = result.artifact.mappings
    assert (first.group_id, first.service_name, first.service_namespace) == (
        "Payment-Service", " Orders ", "shop",
    )  # fmt: skip
    assert second.service_namespace is None


def test_an_empty_mapping_list_is_a_valid_source(tmp_path: Path) -> None:
    assert isinstance(_load(tmp_path, {**EXAMPLE, "mappings": []}), LoadedMappingArtifact)


# ---- rejections (Q01-Q09) -------------------------------------------------------------------


def _mutated(**changes: object) -> dict:
    document = copy.deepcopy(EXAMPLE)
    document.update(changes)
    return document


def _entries(*extra: dict) -> list[dict]:
    return [*copy.deepcopy(EXAMPLE["mappings"]), *extra]


DOCUMENT_CASES = [
    ("Q01", _mutated(schema="aip-kafka-consumer-service-mapping/2")),
    ("Q02", _mutated(broker_id="kafka:cluster-b")),
    ("Q03", _mutated(environment="staging")),
    ("Q04", _mutated(mappings=_entries({"group_id": "payment-service", "service_name": "x"}))),
    ("Q05", _mutated(**{CANARY_KEY: CANARY})),
    ("Q05", _mutated(mappings=_entries({"group_id": "g", "service_name": "s", "host": CANARY}))),
    ("Q05", _mutated(mappings=_entries({"group_id": "g", "service_name": "s", CANARY_KEY: "x"}))),
    ("Q06", {k: v for k, v in EXAMPLE.items() if k != "broker_id"}),
    ("Q06", _mutated(mappings=_entries({"group_id": "g"}))),
    ("Q06", _mutated(mappings=_entries({"group_id": "", "service_name": "s"}))),
    ("Q06", _mutated(mappings=_entries({"group_id": "g", "service_name": 7}))),
    (
        "Q06",
        _mutated(
            mappings=_entries({"group_id": "g", "service_name": CANARY, "service_namespace": ""})
        ),
    ),
    (
        "Q06",
        _mutated(
            mappings=_entries({"group_id": "g", "service_name": CANARY, "service_namespace": None})
        ),
    ),
    ("Q06", _mutated(mappings={"group_id": "g"})),
    ("Q07", "{not json"),
]


@pytest.mark.parametrize(("case_id", "document"), DOCUMENT_CASES)
def test_rejection_vectors(case_id: str, document: object, tmp_path: Path) -> None:
    result = _load(tmp_path, document)
    assert isinstance(result, RejectedMappingArtifact)
    assert result.problem.code == REJECTIONS[case_id]["code"]
    rendered = json.dumps([result.problem.code, result.problem.subject])
    assert CANARY not in rendered and CANARY_KEY not in rendered


def test_q07_missing_file_and_paths_outside_the_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    expected = REJECTIONS["Q07"]["code"]
    assert _code(load_mapping_artifact(_config(root))) == expected  # missing
    _write(tmp_path, EXAMPLE)  # a valid artifact just outside the root
    for relative in ("../kafka-service-mapping.json", str(tmp_path / "kafka-service-mapping.json")):
        result = load_mapping_artifact(_config(root, artifact_relative_path=relative))
        assert _code(result) == expected
    (root / "link.json").symlink_to(tmp_path / "kafka-service-mapping.json")
    assert (
        _code(load_mapping_artifact(_config(root, artifact_relative_path="link.json"))) == expected
    )


def test_q08_each_limit_fails_for_its_own_reason_and_the_limits_are_inclusive(
    tmp_path: Path,
) -> None:
    expected = REJECTIONS["Q08"]["code"]

    def entries(count: int) -> dict:
        return _mutated(mappings=[{"group_id": f"g{i}", "service_name": "s"} for i in range(count)])

    over = json.dumps(entries(MAX_ENTRIES + 1))
    assert len(over.encode()) < MAX_ARTIFACT_BYTES  # fails on the entry count, not on size
    assert _code(_load(tmp_path / "a", over)) == expected
    assert isinstance(_load(tmp_path / "b", entries(MAX_ENTRIES)), LoadedMappingArtifact)

    exact = json.dumps(EXAMPLE)
    exact += " " * (MAX_ARTIFACT_BYTES - len(exact.encode()))
    assert len(exact.encode()) == MAX_ARTIFACT_BYTES
    assert isinstance(_load(tmp_path / "c", exact), LoadedMappingArtifact)
    assert _code(_load(tmp_path / "d", exact + " ")) == expected

    def nested(depth: int) -> dict:  # root object + extra key + (depth - 2) list levels
        value: object = "x"
        for _ in range(depth - 2):
            value = [value]
        return _mutated(extra=value)

    assert _code(_load(tmp_path / "e", nested(65))) == expected
    # At the bound the nesting is fine, so the unknown key is what rejects it.
    assert _code(_load(tmp_path / "f", nested(64))) == REJECTIONS["Q05"]["code"]
    # Far deeper than the parser's recursion limit: still a limit, not "invalid".
    assert _code(_load(tmp_path / "g", "[" * 100_000 + "]" * 100_000)) == expected


@pytest.mark.parametrize(
    ("case_id", "document", "result"),
    [
        (case_id, document, REJECTIONS[case_id]["result"])
        for case_id, document in DOCUMENT_CASES
        if case_id in {"Q01", "Q02", "Q04", "Q05", "Q07"}
    ],
)
def test_discovery_reports_the_frozen_result_and_fixed_text(
    case_id: str, document: object, result: str, tmp_path: Path
) -> None:
    _write(tmp_path, document)
    run = run_kafka_service_mapping_discovery(_config(tmp_path))
    outcome = _outcome(run)
    assert outcome.result is IngestionResult(result)
    assert not run.commit_eligible
    assert outcome.model.kafka_service_mapping_entries == []
    rendered = json.dumps([[d.code, d.message, d.source_pointer] for d in outcome.diagnostics])
    assert CANARY not in rendered and CANARY_KEY not in rendered


def test_q09_duplicate_registration_is_rejected_as_a_conflict(tmp_path: Path) -> None:
    _write(tmp_path, EXAMPLE)
    run = run_kafka_service_mapping_discovery(_config(tmp_path), duplicate_registration=True)
    outcome = _outcome(run)
    assert outcome.result is IngestionResult(REJECTIONS["Q09"]["result"])
    assert [d.code for d in outcome.diagnostics] == [DiagnosticCode.KSM_DUPLICATE_SOURCE]
    assert not run.commit_eligible


def test_every_rejection_vector_is_exercised() -> None:
    covered = {case_id for case_id, _ in DOCUMENT_CASES} | {"Q07", "Q08", "Q09"}
    assert covered == set(REJECTIONS)


# ---- adapter --------------------------------------------------------------------------------


def test_adapter_maps_the_example_to_entries_and_one_evidence_carrier(tmp_path: Path) -> None:
    path = _write(tmp_path, EXAMPLE)
    run = run_kafka_service_mapping_discovery(_config(tmp_path))
    outcome = _outcome(run)
    assert outcome.result is IngestionResult.ACCEPTED
    assert run.commit_eligible
    v = IDS["vectors"]
    model = run.merged_model
    entries = {e.id: e for e in model.kafka_service_mapping_entries}
    assert set(entries) == {v["M04_entry_map_a_payment"], v["M05_entry_map_a_order"]}
    payment = entries[v["M04_entry_map_a_payment"]]
    assert payment.consumer_id == v["M07_join_key_payment_equals_i1_k05"]
    assert (payment.service_name, payment.service_namespace) == ("payment-service", None)
    assert payment.source_instance_id == v["M01_source_instance_map_a"]
    assert all(e.evidence_ids == [v["M06_evidence_map_a"]] for e in entries.values())
    [evidence] = model.kafka_service_mapping_evidence
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert (evidence.id, evidence.configured_source_id, evidence.artifact_sha256) == (
        v["M06_evidence_map_a"], "map-a", digest,
    )  # fmt: skip
    assert evidence.source_revision == f"artifact-sha256:{digest}"
    # A mapping never creates a consumer group, a Service or any public entity (I2 §6).
    assert model.kafka_consumer_groups == []
    assert (model.services, model.topics, model.subscriptions) == ([], [], [])


def test_the_adapter_supports_by_schema_string_not_by_filename(tmp_path: Path) -> None:
    _write(tmp_path, EXAMPLE)
    [loaded] = KafkaServiceMappingSourceDiscoverer(_config(tmp_path)).discover().loaded_sources
    adapter = KafkaServiceMappingSourceAdapter()
    assert adapter.supports(loaded)
    other_schema = copy.deepcopy(loaded.document)
    other_schema["artifact"]["schema"] = "aip-kafka-consumer-service-mapping/2"
    assert not adapter.supports(loaded.model_copy(update={"document": other_schema}))
