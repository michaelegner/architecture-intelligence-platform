"""v0.4.1 I3.1 - spec `docs/specifications/0.4.1/i3-hardening-qualification-and-release.md` §17
items 1-8: deterministic fixture-plan generation, deterministic canonical ids/timestamps,
JSON-schema acceptance/refusal, canonicalization-for-determinism, structural-count mismatch
refusal (both the target-baseline and unrelated-delta halves), target-answer semantic mismatch
refusal, and candidate-identity/consistency release refusal - all pure/no-Neo4j. §17 items 9-10
(real disposable-Neo4j lifecycle and smoke execution) are covered by
`tests/integration/test_snapshot_read_cost_benchmark.py`.

Also covers the four PR #119 review findings: an explicit --candidate-sha must match the actual
checkout (or the measured producer.build_revision), every scale point's snapshot/model-revision/
producer.build_revision consistency is release-blocking via one centralized predicate, and
structural validation checks the target subgraph against a frozen baseline (not just a
self-consistent delta) plus a benchmark-relevant relation type, not only the aggregate total."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import jsonschema
import pytest

from benchmarks.snapshot_read_cost import (
    _BUCKET_START,
    _EXPECTED_TARGET_COUNTS,
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
    scale_points_are_valid,
    verify_structural_counts,
    verify_target_answer_invariance,
    verify_target_baseline,
)

SCHEMA_PATH = (
    Path(__file__).resolve().parent.parent.parent / "benchmarks" / "snapshot_read_cost.schema.json"
)
SCHEMA = json.loads(SCHEMA_PATH.read_text())

_CANDIDATE_SHA = "a" * 40


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
        "actual_relation_counts": {"total": 6, "calls": 6},
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
        "producer_build_revision": _CANDIDATE_SHA,
        "producer_build_revision_consistent": True,
        "structural_validation": "PASS",
        "structural_validation_detail": "structural counts match the deterministic plan",
        "semantic_validation": "PASS",
    }


def _valid_result() -> dict:
    return {
        "schema_version": "aip-benchmark/v1",
        "benchmark_name": "snapshot_read_cost",
        "benchmark_implementation_version": 1,
        "candidate_sha": _CANDIDATE_SHA,
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
            "neo4j_version": "Neo4j/5.26.0",
            "aip_package_version": "0.4.0",
            "container_runtime_version": "docker/25.0.0",
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

    def test_malformed_producer_build_revision_is_rejected(self):
        result = _valid_result()
        result["scale_points"][0]["producer_build_revision"] = "not-a-sha"
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=result, schema=SCHEMA)

    def test_missing_runtime_metadata_field_is_rejected(self):
        result = _valid_result()
        del result["runtime_metadata"]["aip_package_version"]
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


class TestTargetBaselineVerification:
    def test_the_frozen_baseline_itself_passes(self):
        assert verify_target_baseline(_EXPECTED_TARGET_COUNTS).passed

    def test_a_drifted_baseline_fails(self):
        drifted = ActualCounts(
            **{
                **vars(_EXPECTED_TARGET_COUNTS),
                "service_count": _EXPECTED_TARGET_COUNTS.service_count + 1,
            }
        )
        result = verify_target_baseline(drifted)
        assert not result.passed
        assert "frozen expectation" in result.detail


class TestStructuralCountVerification:
    def test_matching_delta_from_the_frozen_baseline_passes(self):
        after = ActualCounts(
            service_count=_EXPECTED_TARGET_COUNTS.service_count + 5,
            operation_count=_EXPECTED_TARGET_COUNTS.operation_count + 5,
            queue_count=_EXPECTED_TARGET_COUNTS.queue_count,
            message_count=_EXPECTED_TARGET_COUNTS.message_count,
            schema_count=_EXPECTED_TARGET_COUNTS.schema_count,
            evidence_count=_EXPECTED_TARGET_COUNTS.evidence_count + 5,
            relation_count=_EXPECTED_TARGET_COUNTS.relation_count + 5,
            calls_relation_count=_EXPECTED_TARGET_COUNTS.calls_relation_count + 5,
        )
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(_EXPECTED_TARGET_COUNTS, after, plan)
        assert result.passed

    def test_a_drifted_target_baseline_fails_even_when_the_unrelated_delta_is_self_consistent(self):
        """The exact PR #119 review scenario: examples/ (or `seed_target_subgraph`) drifts, but the
        unrelated-fact delta on top of that drifted baseline is still internally consistent - this
        must still fail, not silently pass because the delta alone looks right."""
        drifted_before = ActualCounts(
            **{**vars(_EXPECTED_TARGET_COUNTS), "calls_relation_count": 2}  # one CALLS too many
        )
        after = ActualCounts(
            service_count=drifted_before.service_count + 5,
            operation_count=drifted_before.operation_count + 5,
            queue_count=drifted_before.queue_count,
            message_count=drifted_before.message_count,
            schema_count=drifted_before.schema_count,
            evidence_count=drifted_before.evidence_count + 5,
            relation_count=drifted_before.relation_count + 5,
            calls_relation_count=drifted_before.calls_relation_count + 5,
        )
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(drifted_before, after, plan)
        assert not result.passed

    def test_mismatched_evidence_delta_fails(self):
        after = ActualCounts(
            service_count=_EXPECTED_TARGET_COUNTS.service_count + 5,
            operation_count=_EXPECTED_TARGET_COUNTS.operation_count + 5,
            queue_count=_EXPECTED_TARGET_COUNTS.queue_count,
            message_count=_EXPECTED_TARGET_COUNTS.message_count,
            schema_count=_EXPECTED_TARGET_COUNTS.schema_count,
            evidence_count=_EXPECTED_TARGET_COUNTS.evidence_count + 4,  # short by one
            relation_count=_EXPECTED_TARGET_COUNTS.relation_count + 5,
            calls_relation_count=_EXPECTED_TARGET_COUNTS.calls_relation_count + 5,
        )
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(_EXPECTED_TARGET_COUNTS, after, plan)
        assert not result.passed

    def test_mismatched_calls_relation_delta_fails_even_when_total_relation_count_matches(self):
        """The exact PR #119 review scenario: total relation count grows by the right amount, but
        the CALLS-specific count doesn't - one fewer CALLS offset by one extra relation of some
        other type must still be caught."""
        after = ActualCounts(
            service_count=_EXPECTED_TARGET_COUNTS.service_count + 5,
            operation_count=_EXPECTED_TARGET_COUNTS.operation_count + 5,
            queue_count=_EXPECTED_TARGET_COUNTS.queue_count,
            message_count=_EXPECTED_TARGET_COUNTS.message_count,
            schema_count=_EXPECTED_TARGET_COUNTS.schema_count,
            evidence_count=_EXPECTED_TARGET_COUNTS.evidence_count + 5,
            relation_count=_EXPECTED_TARGET_COUNTS.relation_count + 5,  # total matches...
            calls_relation_count=_EXPECTED_TARGET_COUNTS.calls_relation_count + 4,  # ...calls don't
        )
        plan = FixturePlan(profile="smoke", scale_index=0, unrelated_fact_count=5)
        result = verify_structural_counts(_EXPECTED_TARGET_COUNTS, after, plan)
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
    def test_explicit_sha_matching_the_actual_checkout_is_accepted(self):
        sha = "c" * 40
        assert resolve_candidate_sha(sha, actual_sha_fn=lambda: sha) == sha

    def test_malformed_explicit_sha_is_rejected(self):
        with pytest.raises(InvalidCandidateSha):
            resolve_candidate_sha("not-a-sha", actual_sha_fn=lambda: "c" * 40)

    def test_explicit_sha_not_matching_the_actual_checkout_is_rejected(self):
        """PR #119 review finding: code from commit A run with --candidate-sha <commit B> must be
        refused, not silently attributed to B."""
        with pytest.raises(InvalidCandidateSha, match="does not match"):
            resolve_candidate_sha("c" * 40, actual_sha_fn=lambda: "d" * 40)

    def test_explicit_sha_is_accepted_when_the_actual_checkout_cannot_be_determined(self):
        # e.g. no git binary/.git dir available - can't verify, so trust the caller's pin, matching
        # app.mcp.wiring._resolve_build_revision's own graceful-degradation precedent.
        sha = "c" * 40
        assert resolve_candidate_sha(sha, actual_sha_fn=lambda: None) == sha

    def test_no_explicit_sha_falls_back_to_the_actual_checkout(self):
        sha = "e" * 40
        assert resolve_candidate_sha(None, actual_sha_fn=lambda: sha) == sha

    def test_no_explicit_sha_and_no_actual_checkout_is_unknown(self):
        assert resolve_candidate_sha(None, actual_sha_fn=lambda: None) == UNKNOWN_CANDIDATE_SHA


class TestScalePointsAreValid:
    def test_a_fully_valid_result_passes(self):
        assert scale_points_are_valid(_valid_result()).passed

    def test_structural_failure_is_release_blocking(self):
        result = _valid_result()
        result["scale_points"][0]["structural_validation"] = "FAIL"
        assert not scale_points_are_valid(result).passed

    def test_semantic_failure_is_release_blocking(self):
        result = _valid_result()
        result["scale_points"][0]["semantic_validation"] = "FAIL"
        assert not scale_points_are_valid(result).passed

    def test_unstable_snapshot_id_is_release_blocking(self):
        """PR #119 review finding: a run with changing snapshot ids must not exit 0/qualify."""
        result = _valid_result()
        result["scale_points"][0]["snapshot_id_consistent"] = False
        assert not scale_points_are_valid(result).passed

    def test_unstable_model_revision_is_release_blocking(self):
        result = _valid_result()
        result["scale_points"][0]["model_revision_consistent"] = False
        assert not scale_points_are_valid(result).passed

    def test_unstable_producer_build_revision_is_release_blocking(self):
        result = _valid_result()
        result["scale_points"][0]["producer_build_revision_consistent"] = False
        assert not scale_points_are_valid(result).passed


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

    def test_unstable_snapshot_id_is_refused(self):
        result = _valid_result()
        result["scale_points"][0]["snapshot_id_consistent"] = False
        assert not qualifies_for_release(result).passed

    def test_measured_producer_build_revision_disagreeing_with_candidate_sha_is_refused(self):
        """PR #119 review finding: a result attributed to a commit that did not actually produce
        it must be refused."""
        result = _valid_result()
        result["scale_points"][0]["producer_build_revision"] = "b" * 40
        assert not qualifies_for_release(result).passed

    def test_measured_producer_build_revision_agreeing_with_candidate_sha_qualifies(self):
        result = _valid_result()
        assert all(
            point["producer_build_revision"] == result["candidate_sha"]
            for point in result["scale_points"]
        )
        assert qualifies_for_release(result).passed
