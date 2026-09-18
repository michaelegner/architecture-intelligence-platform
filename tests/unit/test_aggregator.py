from datetime import UTC, datetime

from app.provenance.model import ObservedEvidence, RuntimeIdentityObservation
from app.telemetry.aggregator import merge_evidence, merge_runtime_identity_observation

BUCKET_START = datetime(2026, 8, 26, tzinfo=UTC)
BUCKET_END = datetime(2026, 8, 27, tzinfo=UTC)


def _evidence(**overrides) -> ObservedEvidence:
    defaults = {
        "id": "evidence:otel:production:2026-08-26:abc123",
        "environment": "production",
        "bucket_start": BUCKET_START,
        "bucket_end": BUCKET_END,
        "first_seen": datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        "last_seen": datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        "observation_count": 1,
        "sample_trace_ids": ["a" * 32],
        "service_version": "1.0.0",
    }
    defaults.update(overrides)
    return ObservedEvidence(**defaults)


def test_no_existing_evidence_returns_seed_unchanged():
    seed = _evidence()
    result = merge_evidence(None, seed)
    assert result == seed


def test_widens_first_seen_backward():
    existing = _evidence(first_seen=datetime(2026, 8, 26, 8, 0, tzinfo=UTC))
    seed = _evidence(first_seen=datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
    result = merge_evidence(existing, seed)
    assert result.first_seen == datetime(2026, 8, 26, 8, 0, tzinfo=UTC)


def test_widens_last_seen_forward():
    existing = _evidence(last_seen=datetime(2026, 8, 26, 12, 0, tzinfo=UTC))
    seed = _evidence(last_seen=datetime(2026, 8, 26, 18, 0, tzinfo=UTC))
    result = merge_evidence(existing, seed)
    assert result.last_seen == datetime(2026, 8, 26, 18, 0, tzinfo=UTC)


def test_first_seen_and_last_seen_do_not_narrow():
    # existing already has a wider window than the new seed - must not shrink it.
    existing = _evidence(
        first_seen=datetime(2026, 8, 26, 6, 0, tzinfo=UTC),
        last_seen=datetime(2026, 8, 26, 20, 0, tzinfo=UTC),
    )
    seed = _evidence(
        first_seen=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        last_seen=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
    )
    result = merge_evidence(existing, seed)
    assert result.first_seen == datetime(2026, 8, 26, 6, 0, tzinfo=UTC)
    assert result.last_seen == datetime(2026, 8, 26, 20, 0, tzinfo=UTC)


def test_observation_count_sums():
    existing = _evidence(observation_count=4)
    seed = _evidence(observation_count=1)
    result = merge_evidence(existing, seed)
    assert result.observation_count == 5


def test_sample_trace_ids_deduplicate():
    existing = _evidence(sample_trace_ids=["a" * 32])
    seed = _evidence(sample_trace_ids=["a" * 32])
    result = merge_evidence(existing, seed)
    assert result.sample_trace_ids == ["a" * 32]


def test_sample_trace_ids_accumulate_up_to_five():
    existing = _evidence(sample_trace_ids=["1" * 32, "2" * 32, "3" * 32])
    seed = _evidence(sample_trace_ids=["4" * 32])
    result = merge_evidence(existing, seed)
    assert result.sample_trace_ids == ["1" * 32, "2" * 32, "3" * 32, "4" * 32]


def test_sample_trace_ids_capped_at_five():
    existing = _evidence(sample_trace_ids=[str(i) * 32 for i in range(5)])
    seed = _evidence(sample_trace_ids=["9" * 32])
    result = merge_evidence(existing, seed)
    assert len(result.sample_trace_ids) == 5
    assert "9" * 32 not in result.sample_trace_ids


def test_bucket_bounds_and_metadata_come_from_the_seed():
    existing = _evidence(observation_count=1)
    seed = _evidence(
        bucket_start=BUCKET_START,
        bucket_end=BUCKET_END,
        environment="production",
        service_version="2.0.0",
    )
    result = merge_evidence(existing, seed)
    assert result.bucket_start == BUCKET_START
    assert result.bucket_end == BUCKET_END
    assert result.environment == "production"
    assert result.service_version == "2.0.0"
    assert result.source_type == "OPENTELEMETRY"
    assert result.evidence_type == "OBSERVED"


# --- correlation_mode strength ordering (11H-C) --------------------------------------------------


def test_merge_keeps_the_stronger_mode_when_existing_is_stronger():
    existing = _evidence(correlation_mode="CLIENT_SERVER")
    seed = _evidence(correlation_mode="CLIENT_ONLY")
    result = merge_evidence(existing, seed)
    assert result.correlation_mode == "CLIENT_SERVER"


def test_merge_keeps_the_stronger_mode_when_seed_is_stronger():
    existing = _evidence(correlation_mode="MESSAGING_SEND")
    seed = _evidence(correlation_mode="CLIENT_SERVER")
    result = merge_evidence(existing, seed)
    assert result.correlation_mode == "CLIENT_SERVER"


def test_merge_prefers_a_real_mode_over_none_from_either_side():
    existing = _evidence(correlation_mode=None)
    seed = _evidence(correlation_mode="SERVER_ONLY")
    assert merge_evidence(existing, seed).correlation_mode == "SERVER_ONLY"

    existing = _evidence(correlation_mode="SERVER_ONLY")
    seed = _evidence(correlation_mode=None)
    assert merge_evidence(existing, seed).correlation_mode == "SERVER_ONLY"


# --- merge_runtime_identity_observation (I3 §9.4/§23 slice 2) -------------------------------------


def _observation(**overrides) -> RuntimeIdentityObservation:
    defaults = {
        "id": "runtime-identity:otel:production:2026-08-26:abc123",
        "service_name": "OrderService",
        "service_namespace": "commerce",
        "environment": "production",
        "k8s_pod_uid": "pod-uid-1",
        "first_seen": datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        "last_seen": datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
        "observation_count": 1,
    }
    defaults.update(overrides)
    return RuntimeIdentityObservation(**defaults)


def test_no_existing_runtime_identity_observation_returns_seed_unchanged():
    seed = _observation()
    assert merge_runtime_identity_observation(None, seed) == seed


def test_runtime_identity_observation_widens_first_and_last_seen():
    existing = _observation(
        first_seen=datetime(2026, 8, 26, 6, 0, tzinfo=UTC),
        last_seen=datetime(2026, 8, 26, 12, 0, tzinfo=UTC),
    )
    seed = _observation(
        first_seen=datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
        last_seen=datetime(2026, 8, 26, 18, 0, tzinfo=UTC),
    )
    result = merge_runtime_identity_observation(existing, seed)
    assert result.first_seen == datetime(2026, 8, 26, 6, 0, tzinfo=UTC)
    assert result.last_seen == datetime(2026, 8, 26, 18, 0, tzinfo=UTC)


def test_runtime_identity_observation_count_sums():
    existing = _observation(observation_count=4)
    seed = _observation(observation_count=1)
    assert merge_runtime_identity_observation(existing, seed).observation_count == 5


def test_runtime_identity_observation_a_missing_value_never_erases_a_known_value():
    existing = _observation(k8s_pod_name="order-service-abcde")
    seed = _observation(k8s_pod_name=None)
    result = merge_runtime_identity_observation(existing, seed)
    assert result.k8s_pod_name == "order-service-abcde"
    assert result.conflicting_consistency_attributes == []


def test_runtime_identity_observation_adopts_a_new_value_when_existing_was_missing():
    existing = _observation(k8s_pod_name=None)
    seed = _observation(k8s_pod_name="order-service-abcde")
    result = merge_runtime_identity_observation(existing, seed)
    assert result.k8s_pod_name == "order-service-abcde"
    assert result.conflicting_consistency_attributes == []


def test_runtime_identity_observation_agreeing_values_are_not_flagged():
    existing = _observation(service_version="1.0.0")
    seed = _observation(service_version="1.0.0")
    result = merge_runtime_identity_observation(existing, seed)
    assert result.service_version == "1.0.0"
    assert result.conflicting_consistency_attributes == []


def test_runtime_identity_observation_disagreeing_values_null_the_field_and_flag_it():
    existing = _observation(k8s_pod_name="old-pod-name")
    seed = _observation(k8s_pod_name="new-pod-name")
    result = merge_runtime_identity_observation(existing, seed)
    assert result.k8s_pod_name is None
    assert result.conflicting_consistency_attributes == ["k8s_pod_name"]


def test_runtime_identity_observation_multiple_conflicting_fields_are_all_flagged():
    existing = _observation(k8s_pod_name="old-pod-name", service_version="1.0.0")
    seed = _observation(k8s_pod_name="new-pod-name", service_version="2.0.0")
    result = merge_runtime_identity_observation(existing, seed)
    assert result.k8s_pod_name is None
    assert result.service_version is None
    assert result.conflicting_consistency_attributes == ["k8s_pod_name", "service_version"]


def test_runtime_identity_observation_a_flagged_attribute_stays_flagged_once_a_conflict_is_seen():
    # Three merges in sequence: x, then y (conflict, flagged+nulled), then x again - a later value
    # that happens to agree with an earlier one must not silently clear a conflict already seen.
    first = _observation(k8s_pod_name="x")
    second = merge_runtime_identity_observation(first, _observation(k8s_pod_name="y"))
    assert second.conflicting_consistency_attributes == ["k8s_pod_name"]
    assert second.k8s_pod_name is None

    third = merge_runtime_identity_observation(second, _observation(k8s_pod_name="x"))
    assert third.conflicting_consistency_attributes == ["k8s_pod_name"]


def test_runtime_identity_observation_conflicts_accumulate_across_merges():
    first = _observation(k8s_pod_name="old-pod-name")
    second = merge_runtime_identity_observation(first, _observation(k8s_pod_name="new-pod-name"))
    assert second.conflicting_consistency_attributes == ["k8s_pod_name"]

    third = merge_runtime_identity_observation(
        second, _observation(service_version="1.0.0", k8s_pod_name=None)
    )
    fourth = merge_runtime_identity_observation(third, _observation(service_version="2.0.0"))
    assert fourth.conflicting_consistency_attributes == ["k8s_pod_name", "service_version"]
