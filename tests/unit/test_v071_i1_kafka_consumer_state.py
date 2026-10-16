"""v0.7.1 I1.2: Kafka consumer-state registration, ids, capture contract, loader and normalizer.
Expected values come from the hand-authored I1.1 vectors (`docs/specifications/0.7.1/i1-vectors/`),
loaded from the files, not re-derived from the production formulas."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.common.encoding import unicode_nfc
from app.kafka_capture.normalize import (
    DescribedGroup,
    DescribedMember,
    normalize_capture,
    secret_findings,
    serialize,
)
from app.settings import SourcesConfig
from app.sources.identity import (
    kafka_attachment_id,
    kafka_consumer_id,
    kafka_consumer_state_source_instance_id,
    kafka_scope_digest,
)
from app.sources.kafka_consumer_state_contract import (
    duplicate_registrations,
    unredacted_secret_paths,
)
from app.sources.kafka_consumer_state_loader import (
    MAX_CAPTURE_BYTES,
    LoadedKafkaCapture,
    RejectedKafkaCapture,
    load_capture,
)
from app.sources.model import KafkaConsumerStateSourceConfig, SourceKind
from app.sources.owner_ids import topic_owned_id

VECTORS = Path(__file__).resolve().parents[2] / "docs/specifications/0.7.1/i1-vectors"
EXAMPLE = VECTORS / "kafka-consumer-state-capture.example.json"
IDS = json.loads((VECTORS / "ids.json").read_text())
REJECTIONS = json.loads((VECTORS / "capture-rejections.json").read_text())["cases"]
BROKER, ENV = IDS["inputs"]["broker_id"], IDS["inputs"]["environment"]
CANARY = "CANARY-KAFKA-SECRET-5d2e"
NEUTRAL = "CANARY-NAME-91ab"


def _config(root: Path, **overrides: object) -> KafkaConsumerStateSourceConfig:
    values: dict[str, object] = {
        "id": IDS["inputs"]["source_id"],
        "root": root,
        "broker_id": BROKER,
        "environment": ENV,
        "consumer_groups": ["payment-service", "order-service"],
    }
    values.update(overrides)
    return KafkaConsumerStateSourceConfig.model_validate(values)


def _example() -> dict:
    return json.loads(EXAMPLE.read_text())


def _write(root: Path, document: object) -> None:
    (root / "kafka-consumer-state.json").write_text(json.dumps(document))


def _payment(document: dict) -> dict:
    return next(g for g in document["groups"] if g["group_id"] == "payment-service")


# ---- ids (vectors K01-K13) -------------------------------------------------------------------


def test_known_answer_ids_match_the_vectors() -> None:
    v = IDS["vectors"]
    groups = IDS["inputs"]["group_scope"]
    assert kafka_scope_digest(groups) == v["K01_scope_digest"]
    assert kafka_scope_digest(list(reversed(groups))) == v["K02_scope_digest_order_independent"]
    source = IDS["inputs"]["source_id"]
    assert (
        kafka_consumer_state_source_instance_id(
            configured_source_id=source, broker_id=BROKER, environment=ENV, consumer_groups=groups
        )
        == v["K03_source_instance"]
    )
    assert (
        kafka_consumer_state_source_instance_id(
            configured_source_id=source,
            broker_id=BROKER,
            environment=ENV,
            consumer_groups=["payment-service"],
        )
        == v["K04_source_instance_other_scope"]
    )
    consumer = kafka_consumer_id(broker_id=BROKER, environment=ENV, group_id="payment-service")
    assert consumer == v["K05_consumer_payment"]
    assert (
        kafka_consumer_id(broker_id=BROKER, environment="staging", group_id="payment-service")
        == v["K06_consumer_other_environment"]
    )
    assert (
        kafka_consumer_id(broker_id="kafka:cluster-b", environment=ENV, group_id="payment-service")
        == v["K07_consumer_other_broker"]
    )
    assert (
        kafka_consumer_id(broker_id=BROKER, environment=ENV, group_id="order-service")
        == v["K08_consumer_order"]
    )
    assert (
        kafka_consumer_id(broker_id=BROKER, environment=ENV, group_id="Payment-Service")
        == v["K11_consumer_groupid_verbatim_case"]
    )
    topic = topic_owned_id(
        stable_broker_id=BROKER,
        normalized_namespace_or_empty="",
        exact_topic_address="orders.created",
    )
    assert topic == v["K09_topic_orders_created"]
    assert (
        kafka_attachment_id(consumer_id=consumer, topic_id=topic)
        == v["K10_attachment_payment_orders"]
    )


def test_topic_names_are_nfc_normalized_before_the_join() -> None:
    v = IDS["vectors"]
    for spelling, key in (
        ("café", "K12_topic_nfc_composed"),
        ("café", "K13_topic_nfc_decomposed_equal"),
    ):
        topic_id = topic_owned_id(
            stable_broker_id=BROKER,
            normalized_namespace_or_empty="",
            exact_topic_address=unicode_nfc(spelling),
        )
        assert topic_id == v[key]


# ---- registration and settings ---------------------------------------------------------------


def test_registration_defaults_and_validation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert config.capture_relative_path == "kafka-consumer-state.json"
    assert config.resolved_scope_id == config.id
    for bad in ([], ["a", "a"], [""]):
        with pytest.raises(ValidationError):
            _config(tmp_path, consumer_groups=bad)
    with pytest.raises(ValidationError):
        _config(tmp_path, broker_id="")
    assert SourceKind.KAFKA_CONSUMER_STATE.value == "kafka_consumer_state"


def test_no_kafka_registration_by_default() -> None:
    assert SourcesConfig().kafka_consumer_state == []


def test_duplicate_registrations_are_all_flagged(tmp_path: Path) -> None:
    a = _config(tmp_path, id="a", consumer_groups=["g1", "g2"])
    b = _config(tmp_path, id="b", consumer_groups=["g2", "g3"])
    c = _config(tmp_path, id="c", consumer_groups=["g9"])
    d = _config(tmp_path, id="d", consumer_groups=["g2"], environment="staging")
    assert duplicate_registrations([a, b, c, d]) == frozenset({"a", "b"})


# ---- loader: acceptance and every rejection vector -------------------------------------------


def test_example_capture_is_accepted(tmp_path: Path) -> None:
    _write(tmp_path, _example())
    loaded = load_capture(_config(tmp_path))
    assert isinstance(loaded, LoadedKafkaCapture)
    assert loaded.source_revision == "kafka:3.7.0+capture:2026-10-16T09:00:00Z"
    assert len(loaded.content_sha256) == 64


def _set(path: tuple, value: object):
    def mutate(doc: dict) -> None:
        node = doc
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value

    return mutate


def _drop_group(doc: dict) -> None:
    doc["groups"] = [g for g in doc["groups"] if g["group_id"] != "payment-service"]


def _ghost_group(doc: dict) -> None:
    doc["groups"].append({"group_id": "ghost", "state": "Empty", "members": []})


def _error_entry(doc: dict) -> None:
    group = _payment(doc)
    group.pop("state")
    group["error"] = "DESCRIBE_FAILED"


def _sasl_key(doc: dict) -> None:
    _payment(doc)["sasl.jaas.config"] = CANARY


def _password_key_in_member(doc: dict) -> None:
    _payment(doc)["members"][0]["password"] = CANARY


def _drop_tool_version(doc: dict) -> None:
    doc.pop("tool_version")


def _duplicate_group(doc: dict) -> None:
    doc["groups"].append(copy.deepcopy(_payment(doc)))


def _repeat_scope(doc: dict) -> None:
    doc["group_scope"] = ["order-service", "order-service", "payment-service"]


MUTATIONS = {
    "R01": [_set(("broker_id",), "kafka:other")],
    "R02": [_set(("environment",), "staging")],
    "R03": [_set(("group_scope",), ["order-service", "payment-service", "extra"]), _ghost_group],
    "R04": [_drop_group],
    "R05": [lambda d: _payment(d).update(state="PreparingRebalance")],
    "R06": [lambda d: _payment(d).update(state="CompletingRebalance")],
    "R07": [lambda d: _payment(d).update(state="Whatever"), lambda d: _payment(d).pop("state")],
    "R08": [_set(("complete",), False), _error_entry],
    "R09": [_sasl_key, _password_key_in_member],
    "R10": [
        _drop_tool_version,
        _set(("captured_at",), "2026-10-16 09:00:00"),
        _set(("complete",), "true"),
    ],
    "R11": [_set(("schema",), "aip-kafka-consumer-state/2")],
    "R13": [_duplicate_group, _repeat_scope],
}
NOT_IN_THIS_SLICE = {"R12": "registrations (tested separately)", "R14": "I1.3", "R15": "I1.3"}


def test_every_rejection_vector_is_covered_or_deferred() -> None:
    assert {case["id"] for case in REJECTIONS} == set(MUTATIONS) | set(NOT_IN_THIS_SLICE)


@pytest.mark.parametrize(
    "case", [c for c in REJECTIONS if c["id"] in MUTATIONS], ids=lambda c: c["id"]
)
def test_rejection_vectors(case: dict, tmp_path: Path) -> None:
    for mutate in MUTATIONS[case["id"]]:
        root = tmp_path / f"{case['id']}-{id(mutate)}"
        root.mkdir()
        document = _example()
        mutate(document)
        _write(root, document)
        result = load_capture(_config(root))
        assert isinstance(result, RejectedKafkaCapture), case["id"]
        assert result.problem.code == case["reason"], case["id"]
        assert CANARY not in repr(result)


def test_rejection_never_echoes_a_rejected_value(tmp_path: Path) -> None:
    document = _example()
    _password_key_in_member(document)
    assert unredacted_secret_paths(document) == ["/groups/1/members/0/<redacted-key>"]
    _write(tmp_path, document)
    result = load_capture(_config(tmp_path))
    assert isinstance(result, RejectedKafkaCapture)
    assert CANARY not in repr(result)


def test_group_named_like_a_secret_is_a_value_not_a_key(tmp_path: Path) -> None:
    document = _example()
    _payment(document)["group_id"] = "token-service"
    document["group_scope"] = ["order-service", "token-service"]
    _write(tmp_path, document)
    result = load_capture(_config(tmp_path, consumer_groups=["order-service", "token-service"]))
    assert isinstance(result, LoadedKafkaCapture)


def test_empty_and_dead_groups_are_accepted_readings(tmp_path: Path) -> None:
    for state in ("Empty", "Dead"):
        document = _example()
        group = _payment(document)
        group["state"] = state
        group["members"] = []
        _write(tmp_path, document)
        assert isinstance(load_capture(_config(tmp_path)), LoadedKafkaCapture)


def test_loader_bounds_and_path_confinement(tmp_path: Path) -> None:
    (tmp_path / "kafka-consumer-state.json").write_bytes(b"x" * (MAX_CAPTURE_BYTES + 1))
    big = load_capture(_config(tmp_path))
    assert isinstance(big, RejectedKafkaCapture) and big.problem.code == "KAFKA_CAPTURE_INVALID"
    (tmp_path / "kafka-consumer-state.json").write_text("[" * 70 + "]" * 70)
    deep = load_capture(_config(tmp_path))
    assert isinstance(deep, RejectedKafkaCapture) and deep.problem.code == "KAFKA_CAPTURE_INVALID"
    for relative in ("../outside.json", "/etc/passwd"):
        escaped = load_capture(_config(tmp_path, capture_relative_path=relative))
        assert isinstance(escaped, RejectedKafkaCapture)
        assert escaped.problem.subject == "/capture_relative_path"
    missing = load_capture(_config(tmp_path, capture_relative_path="nope.json"))
    assert isinstance(missing, RejectedKafkaCapture)


# ---- capture utility normalizer --------------------------------------------------------------


def _described() -> list[DescribedGroup]:
    return [
        DescribedGroup(
            "payment-service",
            "Stable",
            [
                DescribedMember(
                    "server@host1-cccc",
                    "server@host1",
                    "/10.0.0.7",
                    [("orders.created", 2), ("orders.created", 0), ("orders.created", 1)],
                )
            ],
        ),
        DescribedGroup(
            "order-service",
            "Stable",
            [
                DescribedMember(
                    "consumer-order-service-2-bbbb",
                    "consumer-order-service-2",
                    "/10.0.0.6",
                    [("payments.failed", 0), ("payments.failed", 1), ("payments.failed", 2)],
                ),
                DescribedMember(
                    "consumer-order-service-1-aaaa",
                    "consumer-order-service-1",
                    "/10.0.0.6",
                    [
                        ("payments.completed", 0),
                        ("payments.completed", 1),
                        ("payments.completed", 2),
                    ],
                ),
            ],
        ),
    ]


def _normalize(described: list[DescribedGroup], scope=("payment-service", "order-service")) -> dict:
    return normalize_capture(
        broker_id=BROKER,
        environment=ENV,
        captured_at="2026-10-16T09:00:00Z",
        tool_version="aip-kafka-capture/1",
        kafka_version="3.7.0",
        group_scope=scope,
        described=described,
    )


def test_normalizer_reproduces_the_example_capture_byte_for_byte() -> None:
    assert serialize(_normalize(_described())) == EXAMPLE.read_bytes()
    assert serialize(_normalize(list(reversed(_described())))) == EXAMPLE.read_bytes()


def test_normalizer_output_is_accepted_by_the_loader(tmp_path: Path) -> None:
    (tmp_path / "kafka-consumer-state.json").write_bytes(serialize(_normalize(_described())))
    assert isinstance(load_capture(_config(tmp_path)), LoadedKafkaCapture)


def test_normalizer_marks_failures_incomplete_without_echoing_the_error() -> None:
    failed = _described()
    failed[0] = DescribedGroup("payment-service", failed=True)
    document = _normalize(failed)
    assert document["complete"] is False
    assert _payment(document) == {
        "group_id": "payment-service",
        "error": "DESCRIBE_FAILED",
        "members": [],
    }


def test_normalizer_completeness_needs_exact_scope() -> None:
    assert _normalize(_described()[:1])["complete"] is False
    assert _normalize([*_described(), DescribedGroup("ghost", "Empty")])["complete"] is False
    assert _normalize([*_described(), *_described()[:1]])["complete"] is False


def test_normalizer_keeps_transitional_states_visible_and_maps_unknown() -> None:
    described = _described()
    described[0] = DescribedGroup("payment-service", "PreparingRebalance")
    assert _payment(_normalize(described))["state"] == "PreparingRebalance"
    described[0] = DescribedGroup("payment-service", "SomethingNew")
    assert _payment(_normalize(described))["state"] == "Unknown"


def test_normalizer_copies_no_field_outside_the_schema() -> None:
    document = _normalize(_described())
    assert unredacted_secret_paths(document) == []
    assert set(document) == set(_example())


# ---- R09 value-level canary ------------------------------------------------------------------


def _canary_in(field_path: tuple) -> dict:
    document = _example()
    node = document
    for part in field_path[:-1]:
        node = node[part]
    node[field_path[-1]] = f"prefix-{CANARY}-suffix"
    return document


@pytest.mark.parametrize(
    "field_path",
    [
        ("groups", 1, "members", 0, "client_id"),
        ("groups", 1, "members", 0, "member_id"),
        ("groups", 1, "members", 0, "host"),
        ("groups", 1, "members", 0, "assignments", 0, "topic"),
        ("groups", 1, "group_id"),
        ("tool_version",),
    ],
    ids=lambda p: "/".join(str(x) for x in p),
)
def test_canary_value_under_a_non_secret_key_is_rejected_and_not_echoed(
    field_path: tuple, tmp_path: Path
) -> None:
    _write(tmp_path, _canary_in(field_path))
    result = load_capture(_config(tmp_path), forbidden_values=[CANARY])
    assert isinstance(result, RejectedKafkaCapture)
    assert result.problem.code == "KAFKA_CAPTURE_UNREDACTED"
    assert CANARY not in repr(result)
    assert CANARY not in str(result.problem.subject)


def test_value_check_needs_known_values_and_ignores_none(tmp_path: Path) -> None:
    _write(tmp_path, _canary_in(("groups", 1, "members", 0, "client_id")))
    # A secret's value cannot be recognized by shape: without a known value nothing is flagged.
    assert isinstance(load_capture(_config(tmp_path)), LoadedKafkaCapture)
    assert isinstance(load_capture(_config(tmp_path), forbidden_values=[""]), LoadedKafkaCapture)


def test_capture_utility_refuses_a_capture_holding_a_client_secret() -> None:
    leaky = _described()
    leaky[0] = DescribedGroup(
        "payment-service",
        "Stable",
        [DescribedMember(f"m-{CANARY}", "c", "/h", [("orders.created", 0)])],
    )
    document = _normalize(leaky)
    assert secret_findings(document, [CANARY]) == ["/groups/1/members/0/member_id"]
    assert secret_findings(_normalize(_described()), [CANARY]) == []


def test_rejection_paths_never_carry_a_key_name(tmp_path: Path) -> None:
    document = _example()
    _payment(document)[f"password-{CANARY}"] = "x"
    _payment(document)[f"unknown-{CANARY}"] = "x"
    assert unredacted_secret_paths(document) == ["/groups/1/<redacted-key>"]
    _write(tmp_path, document)
    flagged = load_capture(_config(tmp_path))
    assert isinstance(flagged, RejectedKafkaCapture)
    assert flagged.problem.code == "KAFKA_CAPTURE_UNREDACTED"
    assert CANARY not in repr(flagged)

    plain = _example()
    _payment(plain)[f"unknown-{NEUTRAL}"] = "x"
    _write(tmp_path, plain)
    unknown = load_capture(_config(tmp_path))
    assert isinstance(unknown, RejectedKafkaCapture)
    assert unknown.problem.code == "KAFKA_CAPTURE_INVALID"
    assert unknown.problem.subject == "/groups/1"
    assert NEUTRAL not in repr(unknown)
