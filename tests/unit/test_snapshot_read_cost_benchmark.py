"""v0.4.1 I3.1 - spec `docs/specifications/0.4.1/i3-hardening-qualification-and-release.md` §17
items 1-8: deterministic fixture-plan generation, deterministic canonical ids/timestamps,
JSON-schema acceptance/refusal, canonicalization-for-determinism, structural-count mismatch
refusal, target-answer semantic mismatch refusal, and dirty-worktree/unknown-candidate release
refusal - all pure/no-Neo4j. §17 items 9-10 (real disposable-Neo4j lifecycle and smoke execution)
are covered by `tests/integration/test_snapshot_read_cost_benchmark.py`."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from benchmarks.snapshot_read_cost import (
    _BUCKET_START,
    UNKNOWN_CANDIDATE_SHA,
    ActualCounts,
    FixturePlan,
    InvalidCandidateSha,
    _unrelated_fact,
    build_fixture_plan,
    canonicalize_for_determinism,
    canonicalize_target_answer,
    qualifies_for_release,
    resolve_candidate_sha,
    verify_structural_counts,
    verify_target_answer_invariance,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "benchmarks" / "snapshot_read_cost.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text())


def _valid_scale_point(index: int = 0) -> dict:
    return {
        "scale_index": index,
        "planned_unrelated_fact_count": 5,
        "actual_node_counts": {
            "service": 6,
            "operation": 6,
            "queue": 0,
            "message": 0,
            "schema": 0,
            "evidence": 6,
        },
        "actual_relation_count": 6,
        "target_claim_count": 1,
        "target_evidence_reference_count": 1,
        "revision_fence_value": 7,
        "snapshot_fingerprint_seconds": {
            "raw_seconds": [0.01, 0.011, 0.012],
            "minimum_seconds": 0.01,
            "median_seconds": 0.011,
        },
        "dependency_call_seconds": {
            "raw_seconds": [0.02, 0.021, 0.022],
            "minimum_seconds": 0.02,
            "median_seconds": 0.021,
        },
        "snapshot_id_consistent": True,
        "model_revision_consistent": True,
        "structural_validation": "PASS",
        "structural_validation_detail": "structural counts match the deterministic plan",
        "semantic_validation": "PASS",
    }


def _valid_result() -> dict:
    return {
        "schema_version": "aip-benchmark/v1",
        "benchmark_name": "snapshot_read_cost",
        "benchmark_implementation_version": 1,
        "candidate_sha": "a" * 40,
        "dirty_worktree": False,
        "started_at": "2026-09-10T00:00:00.000000Z",
        "completed_at": "2026-09-10T00:00:05.000000Z",
        "profile": "smoke",
        "database_lifecycle": "clean_rebuild_per_scale_point",
        "seed_method": "production_import_and_telemetry_aggregation",
        "warmup_count": 1,
        "sample_count": 3,
        "request": {
            "tool": "get_service_dependencies",
            "service_id": "service:order-service",
            "observation_context": {
                "environment": "benchmark",
                "window_start": "2026-01-01T00:00:00.000000Z",
                "window_end": "2026-01-02T00:00:00.000000Z",
            },
        },
        "runtime_metadata": {
            "os": "Linux",
            "os_release": "5.15",
            "architecture": "x86_64",
            "cpu_model": "generic",
            "logical_cpu_count": 8,
            "memory_total_bytes": 1024,
            "python_version": "3.13.0",
            "neo4j_version": "5",
        },
        "semantic_validation_detail": "target answer identical at every scale point",
        "scale_points": [_valid_scale_point(0), _valid_scale_point(1)],
    }


class TestFixturePlanDeterminism:
    def test_same_profile_and_index_produce_an_identical_plan(self):
        assert build_fixture_plan("smoke", 0) == build_fixture_plan("smoke", 0)

    def test_different_scale_indices_produce_different_unrelated_fact_counts(self):
        first = build_fixture_plan("smoke", 0)
        second = build_fixture_plan("smoke", 1)
        assert first.unrelated_fact_count != second.unrelated_fact_count

    def test_unknown_profile_is_rejected(self):
        with pytest.raises(ValueError, match="unknown profile"):
            build_fixture_plan("bogus", 0)

    def test_out_of_range_scale_index_is_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            build_fixture_plan("smoke", 99)


class TestDeterministicIdsAndTimestamps:
    def test_same_index_produces_identical_entities_and_fact(self):
        entities_a, fact_a = _unrelated_fact(3)
        entities_b, fact_b = _unrelated_fact(3)
        assert entities_a == entities_b
        assert fact_a == fact_b

    def test_different_indices_produce_disjoint_canonical_ids(self):
        entities_a, fact_a = _unrelated_fact(1)
        entities_b, fact_b = _unrelated_fact(2)
        assert {e.id for e in entities_a}.isdisjoint({e.id for e in entities_b})
        assert fact_a.evidence.id != fact_b.evidence.id

    def test_fact_timestamp_is_fixed_not_wall_clock(self):
        _, fact = _unrelated_fact(0)
        assert fact.timestamp == _BUCKET_START
        assert fact.evidence.first_seen == _BUCKET_START


class TestSchemaAcceptance:
    def test_a_complete_valid_result_validates(self):
        jsonschema.validate(instance=_valid_result(), schema=SCHEMA)


class TestSchemaRefusal:
    def test_missing_required_field_is_rejected(self):
        result = _valid_result()
        del result["candidate_sha"]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_unknown_top_level_field_is_rejected(self):
        result = _valid_result()
        result["unexpected_extra_field"] = "nope"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_malformed_sha_is_rejected(self):
        result = _valid_result()
        result["candidate_sha"] = "not-a-sha"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_negative_node_count_is_rejected(self):
        result = _valid_result()
        result["scale_points"][0]["actual_node_counts"]["service"] = -1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_non_positive_duration_is_rejected(self):
        result = _valid_result()
        result["scale_points"][0]["snapshot_fingerprint_seconds"]["minimum_seconds"] = 0
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_fewer_than_three_samples_is_rejected(self):
        result = _valid_result()
        result["sample_count"] = 1
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_unknown_profile_value_is_rejected(self):
        result = _valid_result()
        result["profile"] = "bogus"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)


class TestCanonicalizationForDeterminism:
    def test_strips_only_the_documented_variable_fields(self):
        result_a = _valid_result()
        result_b = copy.deepcopy(result_a)
        result_b["started_at"] = "2099-01-01T00:00:00.000000Z"
        result_b["completed_at"] = "2099-01-01T00:00:10.000000Z"
        result_b["runtime_metadata"]["cpu_model"] = "a completely different cpu"
        result_b["scale_points"][0]["snapshot_fingerprint_seconds"]["raw_seconds"] = [9.0, 9.1, 9.2]
        result_b["scale_points"][0]["dependency_call_seconds"]["minimum_seconds"] = 99.0

        assert canonicalize_for_determinism(result_a) == canonicalize_for_determinism(result_b)

    def test_a_genuine_structural_difference_survives_canonicalization(self):
        result_a = _valid_result()
        result_b = copy.deepcopy(result_a)
        result_b["scale_points"][0]["target_claim_count"] = 999

        assert canonicalize_for_determinism(result_a) != canonicalize_for_determinism(result_b)


class TestStructuralCountVerification:
    def test_matching_delta_passes(self):
        before = ActualCounts(1, 1, 0, 0, 0, 1, 1)
        after = ActualCounts(6, 6, 0, 0, 0, 6, 6)
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(before, after, plan)
        assert result.passed

    def test_mismatched_evidence_delta_fails(self):
        before = ActualCounts(1, 1, 0, 0, 0, 1, 1)
        after = ActualCounts(6, 6, 0, 0, 0, 5, 6)  # evidence short by one
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(before, after, plan)
        assert not result.passed

    def test_mismatched_relation_delta_fails(self):
        before = ActualCounts(1, 1, 0, 0, 0, 1, 1)
        after = ActualCounts(6, 6, 0, 0, 0, 6, 5)  # relation short by one
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(before, after, plan)
        assert not result.passed


class TestCanonicalizeTargetAnswer:
    def _structured_content(self) -> dict:
        return {
            "tool": "get_service_dependencies",
            "outcome": "ANSWERED",
            "snapshot": {
                "snapshot_id": "aip:snapshot:v1:" + "a" * 64,
                "model_revision": "sha256:" + "a" * 64,
            },
            "observation_context": {
                "environment": "benchmark",
                "window_start": "2026-01-01T00:00:00.000000Z",
                "window_end": "2026-01-02T00:00:00.000000Z",
            },
            "data": {"service": {"id": "service:order-service"}, "dependency_claim_ids": ["x"]},
            "claims": [
                {
                    "claim_id": "aip:claim:v1:x",
                    "subject": {"id": "service:order-service"},
                    "object": {"id": "service:product-service"},
                    "predicate": "DIRECT_DEPENDENCY",
                    "destination_resolution": "RESOLVED_SERVICE",
                    "delivery": {"kind": "SYNC_HTTP"},
                    "qualification": "CONFIRMED",
                    "coverage": None,
                    "evidence_refs": ["b", "a"],
                    "resolution_evidence_refs": [],
                }
            ],
            "limitations": [],
            "evidence_refs": ["a", "b"],
        }

    def test_strips_snapshot_identity(self):
        canonical = canonicalize_target_answer(self._structured_content())
        assert "snapshot" not in canonical

    def test_sorts_per_claim_evidence_refs(self):
        canonical = canonicalize_target_answer(self._structured_content())
        assert canonical["claims"][0]["evidence_refs"] == ["a", "b"]

    def test_growing_unrelated_scale_data_leaves_the_canonical_answer_unchanged(self):
        """The exact property the benchmark's own invariance check relies on: two structured
        contents whose only difference is snapshot/build metadata canonicalize identically."""
        first = self._structured_content()
        second = copy.deepcopy(first)
        second["snapshot"]["snapshot_id"] = "aip:snapshot:v1:" + "b" * 64
        second["snapshot"]["model_revision"] = "sha256:" + "b" * 64

        assert canonicalize_target_answer(first) == canonicalize_target_answer(second)


class TestTargetAnswerInvariance:
    def test_identical_canonical_answers_pass(self):
        answer = {"outcome": "ANSWERED"}
        result = verify_target_answer_invariance([answer, dict(answer)])
        assert result.passed

    def test_diverging_answers_fail(self):
        first = {"outcome": "ANSWERED"}
        second = {"outcome": "PARTIAL"}
        result = verify_target_answer_invariance([first, second])
        assert not result.passed

    def test_empty_list_fails(self):
        result = verify_target_answer_invariance([])
        assert not result.passed


class TestCandidateIdentity:
    def test_explicit_well_formed_sha_is_accepted(self):
        sha = "c" * 40
        assert resolve_candidate_sha(sha) == sha

    def test_malformed_explicit_sha_is_rejected(self):
        with pytest.raises(InvalidCandidateSha):
            resolve_candidate_sha("not-a-sha")


class TestReleaseQualificationRefusal:
    def test_a_well_formed_clean_candidate_qualifies(self):
        result = _valid_result()
        assert qualifies_for_release(result).passed

    def test_unknown_candidate_sha_is_refused(self):
        result = _valid_result()
        result["candidate_sha"] = UNKNOWN_CANDIDATE_SHA
        assert not qualifies_for_release(result).passed

    def test_malformed_candidate_sha_is_refused(self):
        result = _valid_result()
        result["candidate_sha"] = "not-a-sha"
        assert not qualifies_for_release(result).passed

    def test_dirty_worktree_is_refused(self):
        result = _valid_result()
        result["dirty_worktree"] = True
        assert not qualifies_for_release(result).passed
