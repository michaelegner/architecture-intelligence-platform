"""v0.6.0 I3.4a: wiring of the locality cost benchmark (`benchmarks/locality_cost.py`).

Runs small versions of each point type against the integration Neo4j and checks the structure the
measurement relies on: counts per point, the cursor walk covering every candidate exactly once on
one snapshot, each cap where it applies, `k` from `S`, and `k * S` admitted pairs when every source
covers every candidate. It asserts no timing.
"""

import pytest

from benchmarks.locality_cost import Point, measure_point


@pytest.mark.parametrize(
    ("point", "first_page", "walk_pages"),
    [
        (
            Point("churn", workloads=2, pods=6),
            {"localities": 2, "memberships": 2, "cap_reached": [], "i2_truncated": False},
            1,
        ),
        (
            Point("workload-cap", workloads=51, pods=51),
            {"localities": 50, "memberships": 50, "cap_reached": ["WORKLOADS"]},
            2,
        ),
        (
            Point("membership-cap", workloads=1, pods=1, operations=201),
            {"localities": 1, "memberships": 200, "cap_reached": ["MEMBERSHIPS"]},
            2,
        ),
        (
            Point("fan-out", workloads=1, pods=3, sources=5),
            {"considered_capture_sources": 5, "candidate_page_size": 400, "admitted_pairs": 3},
            1,
        ),
        (
            # Every source captures the same Pods: each candidate has S pairs (PR #407 review).
            Point("covering-fan-out", workloads=1, pods=2, sources=3, covering=True),
            {"admitted_pairs": 6, "evaluated_v2_candidates": 2, "localities": 1},
            1,
        ),
    ],
    ids=["churn", "workload-cap", "membership-cap", "fan-out", "covering-fan-out"],
)
def test_each_point_type_has_the_expected_structure(
    driver, tmp_path, point, first_page, walk_pages
):
    result = measure_point(driver, point, tmp_path)

    assert {key: result["first_page"][key] for key in first_page} == first_page
    walk = result["walk"]
    candidates = point.pods * point.operations
    assert walk["pages"] == walk_pages and walk["refusals"] == 0
    assert walk["candidates_seen"] == walk["distinct_candidates_seen"] == candidates
    assert result["stable_read_retries"] == 0
    assert all(value >= 0 for value in result["timings"].values())
