"""v0.7.0 I3.4a: the API usage answer on two clean complete states (I3 spec §13 "cross-surface
deterministic results").

The same sources are imported into an empty database, asked about (query, a cursor continuation and
the evidence mode) through the service, REST and negotiated MCP, the database is emptied, the same
sources are imported again, and every answer, snapshot id included, must be identical. This is I3's
statement of repeatability on the working branch; I4 repeats it on the exact final candidate.
"""

import pytest

from app.architecture_intelligence.service import ArchitectureIntelligenceService

from .test_api_usage_surface_parity import (
    _PRODUCER,
    _all_surfaces,
    _context,
    _refs,
)
from .test_v070_i2_qualification import (
    DATABASE,
    _gateway_default,
    _run,
    _spec_cases_measurement,
)


def _wipe(driver) -> None:
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()


async def _ask(driver, tmp_path) -> list[dict]:
    state = _run(
        driver,
        gateways=[_gateway_default(tmp_path)],
        measurements=[_spec_cases_measurement(tmp_path)],
    )
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=_PRODUCER)
    context = _context(state)
    first = await _all_surfaces(service, {"mode": "query", **context, "limit": 2})
    snapshot_id = first["snapshot"]["snapshot_id"]
    second = await _all_surfaces(
        service,
        {
            "mode": "query",
            **context,
            "limit": 2,
            "cursor": first["data"]["page"]["next_cursor"],
            "snapshot_id": snapshot_id,
        },
    )
    whole = await _all_surfaces(service, {"mode": "query", **context})
    evidence = await _all_surfaces(
        service,
        {"mode": "evidence", "snapshot_id": snapshot_id, "evidence_refs": _refs(whole), **context},
    )
    return [first, second, whole, evidence]


@pytest.mark.asyncio
async def test_two_clean_states_give_identical_answers_on_every_surface(driver, tmp_path):
    runs = []
    for name in ("first", "second"):
        _wipe(driver)
        (tmp_path / name).mkdir()
        runs.append(await _ask(driver, tmp_path / name))
    first_state, second_state = runs

    assert first_state[0]["data"]["page"]["next_cursor"], "the continuation page really exists"
    assert first_state[3]["outcome"] == "ANSWERED"
    assert first_state == second_state
    assert first_state[0]["snapshot"]["snapshot_id"] == second_state[0]["snapshot"]["snapshot_id"]
