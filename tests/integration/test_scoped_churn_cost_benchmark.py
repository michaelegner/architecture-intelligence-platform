"""v0.6.0 I2.6c: wiring of the Pod-churn cost benchmark (`benchmarks/scoped_churn_cost.py`).

Runs one small scale point against the integration Neo4j and checks the structure the measurement
relies on (I1 L28): N Pods of one Workload give N v2 records and one v1 bucket with scoped evidence
on, none with it off, and one Workload assertion covering all N. It asserts no timing.
"""

from app.graph.schema import ensure_schema
from benchmarks.scoped_churn_cost import measure_point

DATABASE = "neo4j"


def test_one_scale_point_has_the_expected_structure(driver, tmp_path):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)

    point = measure_point(driver, 7, tmp_path)

    assert point["pods"] == 7
    off, on = point["off"], point["on"]
    assert (off["v2_records"], off["v1_evidence"], off["scoped_operational_nodes"]) == (0, 1, 0)
    assert (on["v2_records"], on["v1_evidence"]) == (7, 1)
    assert on["assessment"] == {"assertions": 1, "candidates_on_page": 7, "truncated": False}
    assert on["total_nodes"] - off["total_nodes"] == 7 + on["scoped_operational_nodes"]
    assert on["total_relationships"] == off["total_relationships"]  # v2 has no relationships
    for key in (
        "persist_ms_per_post_median",
        "snapshot_fingerprint_ms_median",
        "assess_local_calls_ms_median",
        "transition_report_ms_median",
    ):
        assert on[key] >= 0
