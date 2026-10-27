"""v0.8 I2c B7 (flag off), B8 and schema parity (unit).

B8 pins the canonical digests of the v0.7.1 destination schemas and the OpenAPI snapshot at
`e05b09a` (before I2c): with exactly the two permitted descriptions removed, today's files must
hash to those digests, so no other difference can slip in.
"""

import asyncio
import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from app.architecture_intelligence.binding_picture_contracts import (
    BindingPictureAnswer,
    BindingPictureEvidenceRequest,
)
from app.architecture_intelligence.binding_picture_evidence import (
    resolve_binding_picture_evidence,
)
from app.architecture_intelligence.contracts import SnapshotRef
from app.architecture_intelligence.destination_consumer_contracts import (
    BROKER_ID_DESCRIPTION,
    DESTINATION_ID_DESCRIPTION,
)
from app.architecture_intelligence.schema_export import (
    BINDING_ANSWER_SCHEMA_PATH,
    BINDING_REQUEST_SCHEMA_PATH,
    DESTINATION_ANSWER_SCHEMA_PATH,
    DESTINATION_REQUEST_SCHEMA_PATH,
    render_binding_answer_schema,
    render_binding_request_schema,
)
from app.main import create_app
from app.mcp.server import mcp_server

from .test_v080_i2b_assessment import PRODUCER, SNAPSHOT, build, run

REPO = Path(__file__).resolve().parents[2]
ANSWER_SCHEMA = json.loads(BINDING_ANSWER_SCHEMA_PATH.read_text())
PERMITTED = {DESTINATION_ID_DESCRIPTION, BROKER_ID_DESCRIPTION}
BEFORE_I2C = {
    DESTINATION_REQUEST_SCHEMA_PATH: "f4b3e8a36742a7114f5f55f8e1cf7b7b531d83578207faaf73736bd6479eeb80",
    DESTINATION_ANSWER_SCHEMA_PATH: "f739ddcbb387f2cdd3ec0c6fceb8fb06407abc50b5ddb3fbee0f619812e8e92f",
    REPO
    / "tests/snapshots/openapi.json": "37abf7cd386dcdf76084cfa9ab366584b16067cc421f0dc420d9ccbd91f4d07d",
}


def _without_permitted(node):
    if isinstance(node, dict):
        return {
            k: _without_permitted(v)
            for k, v in node.items()
            if not (k == "description" and v in PERMITTED)
        }
    if isinstance(node, list):
        return [_without_permitted(v) for v in node]
    return node


def _digest(node) -> str:
    return hashlib.sha256(
        json.dumps(node, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.parametrize("path", list(BEFORE_I2C))
def test_b8_only_the_two_descriptions_changed(path) -> None:
    current = json.loads(Path(path).read_text())
    assert _digest(_without_permitted(current)) == BEFORE_I2C[path]
    text = json.dumps(current)
    for description in PERMITTED:
        assert json.dumps(description)[1:-1] in text


def test_the_committed_v08_schemas_equal_the_generated_ones() -> None:
    assert BINDING_REQUEST_SCHEMA_PATH.read_text() == render_binding_request_schema()
    assert BINDING_ANSWER_SCHEMA_PATH.read_text() == render_binding_answer_schema()


def _config(tmp_path, flag: bool) -> Path:
    path = tmp_path / f"config-{flag}.yaml"
    path.write_text(
        "architecture_intelligence:\n  sources:\n    directories: []\n"
        f"  experimental:\n    binding-picture: {str(flag).lower()}\n"
    )
    return path


def _tools(server) -> list[str]:
    return [tool.name for tool in asyncio.run(server.list_tools())]


def test_b7_flag_off_keeps_six_tools_and_no_route(tmp_path) -> None:
    app = create_app(_config(tmp_path, False))
    assert app.state.mcp_server is mcp_server
    assert "get_binding_picture" not in _tools(app.state.mcp_server)
    assert len(_tools(app.state.mcp_server)) == 6
    assert not {p for p in app.openapi()["paths"] if p.startswith("/api/binding-picture")}


def test_b7_flag_on_adds_the_tool_and_both_routes(tmp_path) -> None:
    app = create_app(_config(tmp_path, True))
    assert app.state.mcp_server is not mcp_server
    names = _tools(app.state.mcp_server)
    assert names == sorted(names) and len(names) == 7 and "get_binding_picture" in names
    assert {"/api/binding-picture", "/api/binding-picture/evidence"} <= set(app.openapi()["paths"])


def _valid(answer: dict) -> None:
    assert list(jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(answer)) == []


@pytest.mark.parametrize(
    "state",
    [build(), build(attached=()), build(receives=()), build(topics=(), publishes=(), attached=())],
)
def test_every_query_answer_validates_against_the_frozen_schema(state) -> None:
    _valid(run(state))


def test_refusals_validate_against_the_frozen_schema() -> None:
    _valid(run({}))
    _valid(run(build(), context="ctx-unknown"))


def _evidence(state, **overrides):
    request = {
        "mode": "evidence",
        "snapshot_id": SNAPSHOT.snapshot_id,
        "bounded_context_id": "ctx-c",
        "environment": "local",
        "evidence_refs": ["binding-evidence:" + "0" * 64],
        **overrides,
    }
    answer = resolve_binding_picture_evidence(
        BindingPictureEvidenceRequest.model_validate(request),
        state,
        snapshot=SNAPSHOT,
        producer=PRODUCER,
    ).model_dump(mode="json")
    _valid(answer)
    return answer


def test_a_forged_ref_is_not_resolved_in_an_evaluated_answer() -> None:
    answer = _evidence(build())
    assert answer["mode"] == "evidence" and answer["outcome"] == "NOT_ANSWERED"
    assert [e["status"] for e in answer["data"]["entries"]] == ["NOT_RESOLVED"]
    assert [i["code"] for i in answer["limitations"]] == ["EVIDENCE_REF_NOT_RESOLVED"]


def test_a_non_current_snapshot_is_refused_not_resolved() -> None:
    answer = _evidence(build(), snapshot_id="aip:snapshot:v1:" + "2" * 64)
    assert (answer["mode"], answer["outcome"], answer["data"]) == ("evidence", "NOT_ANSWERED", None)
    assert [i["code"] for i in answer["limitations"]] == ["SNAPSHOT_NOT_AVAILABLE"]


def test_unsorted_refs_are_rejected() -> None:
    with pytest.raises(ValueError):
        BindingPictureEvidenceRequest.model_validate(
            {
                "mode": "evidence",
                "snapshot_id": SNAPSHOT.snapshot_id,
                "bounded_context_id": "ctx-c",
                "environment": "local",
                "evidence_refs": ["binding-evidence:" + "1" * 64, "binding-evidence:" + "0" * 64],
            }
        )


def test_an_old_ref_submitted_with_the_current_snapshot_is_not_resolved() -> None:
    """Refs bind their snapshot: one minted at an earlier snapshot never resolves at a later one."""
    state = build()
    old = run(state)
    refs = sorted({ref for row in old["data"]["rows"] for ref in row["attachment_evidence_refs"]})
    later = SnapshotRef(
        snapshot_id="aip:snapshot:v1:" + "3" * 64, model_revision="sha256:" + "3" * 64
    )
    answer = resolve_binding_picture_evidence(
        BindingPictureEvidenceRequest.model_validate(
            {
                "mode": "evidence",
                "snapshot_id": later.snapshot_id,
                "bounded_context_id": "ctx-c",
                "environment": "local",
                "evidence_refs": refs,
            }
        ),
        state,
        snapshot=later,
        producer=PRODUCER,
    ).model_dump(mode="json")
    assert {e["status"] for e in answer["data"]["entries"]} == {"NOT_RESOLVED"}


def test_the_schema_and_model_both_reject_an_inconsistent_evidence_outcome() -> None:
    answer = _evidence(build())  # NOT_ANSWERED, one NOT_RESOLVED entry
    forged = {**answer, "outcome": "PARTIAL"}
    assert list(jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(forged))
    with pytest.raises(ValueError):
        BindingPictureAnswer.model_validate(forged)
    no_snapshot = {**run(build()), "snapshot": None}
    assert list(jsonschema.Draft202012Validator(ANSWER_SCHEMA).iter_errors(no_snapshot))
