"""Focused verification of the real frozen replacement measurement and rate denominators."""

from app.architecture_intelligence.contracts import Producer
from app.version import package_version
from benchmarks.i4_replacement import measure_replacements


def test_replacement_retains_evidence_and_counts_actual_unresolved_candidates(driver, tmp_path):
    points = measure_replacements(
        driver,
        tmp_path,
        Producer(
            name="architecture-intelligence-platform",
            version=package_version(),
            build_revision="a" * 40,
        ),
    )
    assert [p["case_id"] for p in points] == ["B01a", "B01b"]
    for point in points:
        before, after = point["states"]
        assert point["oracle_match"] is True
        assert before["retained_graph"]["v2_records"] == 2
        assert after["retained_graph"]["v2_records"] == 3
        assert before["walk"]["unresolved_rate"] == {
            "unresolved_candidates": 0,
            "evaluated_candidates": 2,
        }
        assert after["walk"]["unresolved_rate"] == {
            "unresolved_candidates": 1,
            "evaluated_candidates": 3,
        }
        assert after["walk"]["capture_selection"] == {
            "applicable_candidates": 2,
            "evaluated_candidates": 3,
        }
        assert after["walk"]["candidates_seen"] == after["walk"]["distinct_candidates_seen"]
        assert before["capture"]["generated_inputs"] != after["capture"]["generated_inputs"]
