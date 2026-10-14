"""v0.7.0 I3.4a: wiring of the API usage cost benchmark (`benchmarks/api_usage_cost.py`).

Runs small versions of each point type against the integration Neo4j and checks the structure the
measurement relies on: the qualification rows are the bounded union and not `consumers * routes`, a
cursor walk covers every row exactly once, a page never exceeds its limit, an evidence request
resolves its refs, and an invalid window still enumerates its rows. It asserts no timing. The
largest recorded points are not re-run here; the recorded run is `i3-api-usage-cost.json`.
"""

import pytest

from app.architecture_intelligence.contracts import Producer
from benchmarks import api_usage_cost
from benchmarks.api_usage_cost import Point, measure_point

PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.7.0", build_revision="f" * 40
)


@pytest.mark.parametrize(
    "point",
    [
        Point("rows", consumers=12, routes=4, whitelist=5, observed=2, extra=1),
        Point("route-target", consumers=12, routes=4, whitelist=5, observed=2, target="route"),
        Point(
            "invalid-window", consumers=12, routes=4, whitelist=5, observed=2, invalid_window=True
        ),
        # more rows than one page, so the walk really crosses a page boundary
        Point("rows", consumers=60, routes=6, whitelist=45, observed=3, extra=5),
    ],
    ids=["rows", "route-target", "invalid-window", "multi-page"],
)
def test_each_point_type_has_the_expected_structure(driver, tmp_path, point):
    result = measure_point(driver, point, tmp_path, PRODUCER)

    bounds = result["bounds"]
    assert bounds["qualification_rows"] == point.routes * (point.whitelist + point.extra)
    assert bounds["rows_equal_the_bounded_union"] is True
    assert bounds["cartesian_pairs"] == point.consumers * point.routes
    walk = result["walk"]
    assert walk["rows_seen"] == walk["distinct_rows_seen"] == point.rows
    assert walk["refusals"] == 0
    assert walk["max_rows_per_page"] <= api_usage_cost.PAGE_LIMIT
    assert walk["pages"] == -(-point.rows // api_usage_cost.PAGE_LIMIT)
    assert result["first_page"]["window_valid"] is (not point.invalid_window)
    assert result["evidence"]["refs_looked_up"] <= api_usage_cost.MAX_EVIDENCE_REFS
    assert result["evidence"]["resolved"] == result["evidence"]["refs_looked_up"] > 0
    assert result["stable_read_retries"] == 0
    assert all(value >= 0 for value in result["timings"].values())


def test_the_row_universe_is_far_below_the_cartesian_product_at_scale(driver, tmp_path):
    point = Point("rows", consumers=300, routes=20, whitelist=20, observed=2, extra=2)

    result = measure_point(driver, point, tmp_path, PRODUCER)

    bounds = result["bounds"]
    assert bounds["qualification_rows"] == 440
    assert bounds["cartesian_pairs"] == 6000 > 10 * bounds["qualification_rows"]
    assert result["walk"]["pages"] == 3
