"""v0.7.1 I3.2: the `get_destination_consumers` evidence mode (I3 spec §4), over hand-built snapshot
states. Every ref a query answer emits resolves to its closed payload at the same snapshot and
context; a forged, cross-context or cross-snapshot ref does not; nothing outside the closed payloads
(credentials, member/client/host text, raw files, other properties) can appear."""

import json

import jsonschema
import pytest
from pydantic import ValidationError

from app.architecture_intelligence.contracts import SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    DestinationConsumersAnswer,
    DestinationConsumersEvidenceRequest,
)
from app.architecture_intelligence.destination_consumer_evidence import (
    resolve_destination_consumer_evidence,
)
from app.architecture_intelligence.destination_consumer_projection import (
    project_destination_consumers,
)
from tests.unit.test_v071_i3_destination_consumers import (
    ANSWER_SCHEMA,
    BROKER,
    CAPTURE_PROD,
    ENV,
    EVIDENCE_PROD,
    OTHER_SNAPSHOT,
    OTHER_TOPIC,
    PRODUCER,
    SNAPSHOT,
    T_PROD,
    TOPIC,
    _answer,
    _attachment,
    _attribution,
    _consumer,
    _entry,
    _group,
    _request,
    _state,
    _with_brokers,
)

MAP_SOURCE = "urn:aip:source:kafka-service-mapping:" + "6" * 64
MAP_EVIDENCE = "kafka-service-mapping-evidence:owned:" + "e" * 64


def _block() -> dict:
    """A RESOLVED group with one resolving and one not-declared entry, as I2 writes it."""
    resolving, limited = _entry(1), _entry(1, "2")
    attribution = _attribution(
        1,
        "RESOLVED",
        entries=[resolving, limited],
        service_id="service:stock",
        limitations=[(limited, "SERVICE_NOT_DECLARED")],
    )
    return {
        "rule": {"id": "kafka-consumer-attribution", "version": "1"},
        "mapping_sources": [
            {
                "id": MAP_EVIDENCE,
                "source_instance_id": MAP_SOURCE,
                "configured_source_id": "map-a",
                "broker_id": BROKER,
                "environment": ENV,
                "artifact_sha256": "7" * 64,
                "source_revision": "artifact-sha256:" + "7" * 64,
            }
        ],
        "mapping_entries": [
            {
                "id": resolving,
                "group_id": "group-1",
                "service_name": "stock",
                "evidence_ids": [MAP_EVIDENCE],
            },
            {
                "id": limited,
                "group_id": "group-1",
                "service_name": "runtime-only",
                "service_namespace": "shop",
                "evidence_ids": [MAP_EVIDENCE],
            },
        ],
        "groups": [
            {
                "id": _consumer(1),
                "group_id": "group-1",
                "outcome": "RESOLVED",
                "service_id": "service:stock",
                "entries": [
                    {
                        "id": resolving,
                        "evidence_ids": [MAP_EVIDENCE],
                        "service_id": "service:stock",
                    },
                    {
                        "id": limited,
                        "evidence_ids": [MAP_EVIDENCE],
                        "reason": "SERVICE_NOT_DECLARED",
                    },
                ],
                "limitations": [{"entry_id": limited, "reason": "SERVICE_NOT_DECLARED"}],
            }
        ],
        "attributions": [attribution],
    }


def _world() -> dict:
    capture = _state(attachments=[_attachment(1)], groups=[_group(1)], block=_block())
    capture["kafka_consumer_state_v1"]["evidence"][0]["capture_content_sha256"] = "5" * 64
    return capture


def _resolve(state: dict, refs: list[str], *, snapshot=SNAPSHOT, **context) -> dict:
    request = DestinationConsumersEvidenceRequest.model_validate(
        {
            "mode": "evidence",
            "snapshot_id": context.pop("snapshot_id", snapshot.snapshot_id),
            "destination_id": context.pop("destination_id", TOPIC),
            "broker_id": BROKER,
            "environment": context.pop("environment", ENV),
            "evidence_refs": sorted(refs),
        }
    )
    answer = resolve_destination_consumer_evidence(
        request, _with_brokers(state), snapshot=snapshot, producer=PRODUCER
    )
    wire = json.loads(answer.model_dump_json())
    jsonschema.validate(wire, ANSWER_SCHEMA)
    return wire


def _query_refs(state: dict) -> tuple[str, list[str]]:
    [row] = _answer(state)["data"]["rows"]
    return row["attachment_evidence_refs"][0], row["mapping_evidence_refs"]


def test_every_emitted_ref_resolves_to_its_closed_payload() -> None:
    state = _world()
    attachment_ref, mapping_refs = _query_refs(state)
    answer = _resolve(state, [attachment_ref, *mapping_refs])
    assert (answer["mode"], answer["outcome"], answer["limitations"]) == (
        "evidence",
        "ANSWERED",
        [],
    )
    by_kind: dict[str, list[dict]] = {}
    for entry in answer["data"]["entries"]:
        assert entry["status"] == "RESOLVED"
        by_kind.setdefault(entry["kind"], []).append(entry["evidence"])
    assert by_kind["KAFKA_ATTACHMENT"] == [
        {
            "kind": "KAFKA_ATTACHMENT",
            "consumer_id": _consumer(1),
            "group_id": "group-1",
            "topic_id": TOPIC,
            "captured_at": T_PROD,
            "capture_source_instance_id": CAPTURE_PROD,
            "capture_source_revision": f"kafka:not-established+capture:{T_PROD}",
            "capture_content_sha256": "5" * 64,
        }
    ]
    assert sorted(by_kind["KAFKA_SERVICE_MAPPING"], key=lambda e: e["service_name"]) == [
        {
            "kind": "KAFKA_SERVICE_MAPPING",
            "consumer_id": _consumer(1),
            "group_id": "group-1",
            "service_name": "runtime-only",
            "service_namespace": "shop",
            "reason": "SERVICE_NOT_DECLARED",
            "mapping_source_instance_id": MAP_SOURCE,
            "mapping_source_revision": "artifact-sha256:" + "7" * 64,
            "artifact_sha256": "7" * 64,
        },
        {
            "kind": "KAFKA_SERVICE_MAPPING",
            "consumer_id": _consumer(1),
            "group_id": "group-1",
            "service_name": "stock",
            "service_id": "service:stock",
            "mapping_source_instance_id": MAP_SOURCE,
            "mapping_source_revision": "artifact-sha256:" + "7" * 64,
            "artifact_sha256": "7" * 64,
        },
    ]
    # Internal carrier ids are never public handles.
    text = json.dumps(answer)
    assert _attachment(1)["id"] not in text and _entry(1) not in text and EVIDENCE_PROD not in text


def test_forged_cross_context_and_cross_snapshot_refs_are_not_resolved() -> None:
    state = _world()
    attachment_ref, _ = _query_refs(state)
    forged = "destination-evidence:" + "0" * 64
    mixed = _resolve(state, [attachment_ref, forged])
    assert mixed["outcome"] == "PARTIAL"
    assert [item["code"] for item in mixed["limitations"]] == ["EVIDENCE_REF_NOT_RESOLVED"]
    statuses = {entry["ref"]: entry["status"] for entry in mixed["data"]["entries"]}
    assert statuses == {attachment_ref: "RESOLVED", forged: "NOT_RESOLVED"}
    assert set(mixed["data"]["entries"][0]) <= {"ref", "status", "kind", "evidence"}

    # The same ref under another (answerable) context of the same snapshot.
    other_topic = _resolve(state, [attachment_ref], destination_id=OTHER_TOPIC)
    assert other_topic["outcome"] == "NOT_ANSWERED"
    assert other_topic["data"]["entries"][0]["status"] == "NOT_RESOLVED"

    # Issued at an older snapshot, presented at the current one.
    older = SnapshotRef(snapshot_id=OTHER_SNAPSHOT, model_revision="sha256:" + "2" * 64)
    old = project_destination_consumers(
        _request(), _with_brokers(state), snapshot=older, producer=PRODUCER
    ).data
    assert old is not None
    stale_ref = old.rows[0].attachment_evidence_refs[0]
    assert _resolve(state, [stale_ref])["data"]["entries"][0]["status"] == "NOT_RESOLVED"


@pytest.mark.parametrize(
    ("context", "code"),
    [
        ({"snapshot_id": OTHER_SNAPSHOT}, "SNAPSHOT_NOT_AVAILABLE"),
        ({"destination_id": "topic:owned:" + "0" * 64}, "UNKNOWN_DESTINATION"),
        ({"environment": "dev"}, "NO_ACCEPTED_CAPTURE"),
    ],
)
def test_evidence_refusals(context: dict, code: str) -> None:
    answer = _resolve(_world(), ["destination-evidence:" + "1" * 64], **context)
    assert (answer["mode"], answer["outcome"], answer["data"]) == ("evidence", "NOT_ANSWERED", None)
    assert [item["code"] for item in answer["limitations"]] == [code]


def _evidence_wire() -> dict:
    state = _world()
    attachment_ref, _ = _query_refs(state)
    return _resolve(state, [attachment_ref])


def _answered_with_unresolved_code(wire: dict) -> None:
    wire["limitations"] = [{"code": "EVIDENCE_REF_NOT_RESOLVED", "message": "m"}]


def _cursor_refusal_in_evidence(wire: dict) -> None:
    wire.update(outcome="NOT_ANSWERED", data=None)
    wire["limitations"] = [{"code": "CURSOR_QUERY_MISMATCH", "message": "m"}]


def _query_code_in_evidence(wire: dict) -> None:
    wire["limitations"] = [{"code": "CAPTURE_SCOPE_LIMITED", "message": "m"}]
    wire["outcome"] = "PARTIAL"


def _resolved_without_payload(wire: dict) -> None:
    del wire["data"]["entries"][0]["evidence"]


def _member_text_in_payload(wire: dict) -> None:
    wire["data"]["entries"][0]["evidence"]["host"] = "/10.0.0.7"


def _query_payload_in_evidence_mode(wire: dict) -> None:
    wire["data"] = {"request_context": wire["data"]["request_context"], "rows": []}


def _payload_of_the_other_kind(wire: dict) -> None:
    wire["data"]["entries"][0]["kind"] = "KAFKA_SERVICE_MAPPING"


def _unresolved_entry_without_code(wire: dict) -> None:
    entry = wire["data"]["entries"][0]
    wire["data"]["entries"][0] = {"ref": entry["ref"], "status": "NOT_RESOLVED"}
    wire["outcome"] = "NOT_ANSWERED"


def _partial_with_every_ref_resolved(wire: dict) -> None:
    wire["outcome"] = "PARTIAL"
    wire["limitations"] = [{"code": "EVIDENCE_REF_NOT_RESOLVED", "message": "m"}]


def _answered_with_nothing_resolved(wire: dict) -> None:
    entry = wire["data"]["entries"][0]
    wire["data"]["entries"][0] = {"ref": entry["ref"], "status": "NOT_RESOLVED"}
    wire["limitations"] = [{"code": "EVIDENCE_REF_NOT_RESOLVED", "message": "m"}]


@pytest.mark.parametrize(
    "mutate",
    [
        _payload_of_the_other_kind,
        _unresolved_entry_without_code,
        _partial_with_every_ref_resolved,
        _answered_with_nothing_resolved,
        _answered_with_unresolved_code,
        _cursor_refusal_in_evidence,
        _query_code_in_evidence,
        _resolved_without_payload,
        _member_text_in_payload,
        _query_payload_in_evidence_mode,
    ],
)
def test_the_published_schema_and_the_model_reject_broken_evidence_answers(mutate) -> None:
    wire = _evidence_wire()
    mutate(wire)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wire, ANSWER_SCHEMA)
    with pytest.raises(ValidationError):
        DestinationConsumersAnswer.model_validate(wire)
