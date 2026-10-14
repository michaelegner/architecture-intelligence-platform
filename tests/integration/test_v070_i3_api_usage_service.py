"""v0.7.0 I3.2: `ArchitectureIntelligenceService.get_api_consumer_usage` against a real Neo4j - an
APISIX configuration source, the bundled OpenAPI examples and a measurement source in one real import
(the I2.4 fixture). The oracle's snapshot ids are synthetic, so this checks what the unit tier cannot:
that the answer is projected from the real, fingerprinted snapshot state - same snapshot id, rows equal
to the stored I2 `qualification_rows`, stale and cursor-bound refusals."""

from typing import Any

from app.architecture_intelligence.api_usage_contracts import (
    ApiConsumerUsageAnswer,
    ApiConsumerUsageData,
    ApiConsumerUsageQueryRequest,
)
from app.architecture_intelligence.contracts import Outcome, Producer
from app.architecture_intelligence.repository import snapshot_fingerprint
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from tests.integration.test_v070_i2_qualification import (
    DATABASE,
    ENV,
    GW,
    _gateway,
    _gateway_default,
    _route,
    _run,
    _spec_cases_measurement,
)

PRODUCER = Producer(name="architecture-intelligence-platform", version="0.7.0", build_revision="t")


def _service(driver) -> ArchitectureIntelligenceService:
    return ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)


def _request(state: dict, route: str, **extra: Any) -> ApiConsumerUsageQueryRequest:
    window = state["api_usage_v1"]["windows"][0]
    route_row = next(
        r for r in state["gateway_configuration_v1"]["routes"] if r["route_id"] == route
    )
    return ApiConsumerUsageQueryRequest.model_validate(
        {
            "mode": "query",
            "target": {"kind": "GATEWAY_ROUTE", "id": route_row["id"]},
            "gateway_instance_id": GW,
            "environment": ENV,
            "window_start": window["window_start"],
            "window_end": window["window_end"],
            **extra,
        }
    )


def _real_import(driver, tmp_path) -> dict:
    return _run(
        driver,
        gateways=[_gateway_default(tmp_path)],
        measurements=[_spec_cases_measurement(tmp_path)],
    )


def test_the_answer_is_projected_from_the_fingerprinted_snapshot(driver, tmp_path) -> None:
    state = _real_import(driver, tmp_path)
    answer = _service(driver).get_api_consumer_usage(_request(state, "orders-route"))
    ApiConsumerUsageAnswer.model_validate(answer.model_dump(mode="json"))
    snapshot_id, model_revision = snapshot_fingerprint(state)
    assert answer.snapshot is not None
    assert (answer.snapshot.snapshot_id, answer.snapshot.model_revision) == (
        snapshot_id,
        model_revision,
    )
    assert isinstance(answer.data, ApiConsumerUsageData)
    stored = {
        (r["consumer_id"], r["route"]): r
        for r in state["api_usage_v1"]["qualification_rows"]
        if r["route"] == "orders-route"
    }
    assert len(answer.data.rows) == len(stored) == 3
    for row in answer.data.rows:
        source = stored[(row.consumer.id, row.gateway_route.source_route_id)]
        assert row.consumer.source_name == source["consumer"]
        assert row.configured_access.status.value == source["configured_status"]
        assert row.usage.status.value == source["usage_status"]
        assert row.usage.coverage.value == source["coverage"]
        assert row.usage.upstream_request_count == source.get("upstream_request_count")
        assert row.usage.rejected_attempt_count == source.get("rejected_attempt_count")
        assert [c.value for c in row.limitations] == source["limitations"]
        assert row.usage.interaction_id == source.get("interaction_id")
    assert answer.outcome is Outcome.ANSWERED


def test_a_stale_snapshot_is_refused_and_a_foreign_import_invalidates_a_cursor(
    driver, tmp_path
) -> None:
    state = _real_import(driver, tmp_path)
    service = _service(driver)
    snapshot_id = snapshot_fingerprint(state)[0]

    stale = service.get_api_consumer_usage(
        _request(state, "orders-route", snapshot_id="aip:snapshot:v1:" + "0" * 64)
    )
    assert stale.data is None and stale.limitations[0].code.value == "SNAPSHOT_NOT_AVAILABLE"
    assert stale.snapshot is not None and stale.snapshot.snapshot_id == snapshot_id

    first = service.get_api_consumer_usage(_request(state, "orders-route", limit=1))
    assert isinstance(first.data, ApiConsumerUsageData) and first.data.page.next_cursor
    kwargs = {"cursor": first.data.page.next_cursor, "snapshot_id": snapshot_id}
    second = service.get_api_consumer_usage(_request(state, "orders-route", limit=1, **kwargs))
    assert isinstance(second.data, ApiConsumerUsageData)
    assert second.data.rows[0] != first.data.rows[0]

    # an unrelated gateway source changes the whole-graph snapshot: the old cursor is refused
    other = _gateway(tmp_path, routes=[_route("x-route", ["alice"])], gateway="gw-prod-9")
    _run(
        driver,
        gateways=[_gateway_default(tmp_path), other],
        measurements=[_spec_cases_measurement(tmp_path)],
    )
    refused = service.get_api_consumer_usage(_request(state, "orders-route", limit=1, **kwargs))
    assert refused.data is None and refused.limitations[0].code.value == "SNAPSHOT_NOT_AVAILABLE"
    assert refused.snapshot is not None and refused.snapshot.snapshot_id != snapshot_id
