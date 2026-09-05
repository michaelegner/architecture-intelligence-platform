from datetime import UTC, datetime

from app.architecture_intelligence.contracts import EvidenceRelationType, SupportedFact
from app.architecture_intelligence.evidence_projection import (
    project_evidence,
    sanitize_source_locator,
)

_TIMESTAMP = datetime(2026, 8, 26, tzinfo=UTC)


def _declared_row(evidence_id: str, *, source_file: str | None) -> dict:
    return {
        "id": evidence_id,
        "evidence_type": "DECLARED",
        "source_type": "OPENAPI",
        "source_file": source_file,
        "source_revision": "abc123",
    }


def _observed_row(evidence_id: str) -> dict:
    return {
        "id": evidence_id,
        "evidence_type": "OBSERVED",
        "source_type": "OPENTELEMETRY",
        "source_file": "opentelemetry",
        "source_revision": None,
        "environment": "demo",
        "bucket_start": _TIMESTAMP,
        "bucket_end": _TIMESTAMP,
        "first_seen": _TIMESTAMP,
        "last_seen": _TIMESTAMP,
        "observation_count": 3,
        "service_version": "1.0.0",
        "correlation_mode": "OTEL_TRACE",
    }


class TestSanitizeSourceLocator:
    def test_none_stays_none(self) -> None:
        assert sanitize_source_locator(None) is None

    def test_opentelemetry_literal_passes_through(self) -> None:
        assert sanitize_source_locator("opentelemetry") == "opentelemetry"

    def test_safe_relative_posix_path_passes_through(self) -> None:
        assert sanitize_source_locator("order-service/openapi.yaml") == "order-service/openapi.yaml"

    def test_absolute_path_is_rejected(self) -> None:
        assert sanitize_source_locator("/etc/order-service/openapi.yaml") is None

    def test_parent_segment_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service/../secret/openapi.yaml") is None

    def test_current_dir_segment_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service/./openapi.yaml") is None

    def test_empty_segment_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service//openapi.yaml") is None

    def test_backslash_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service\\openapi.yaml") is None

    def test_query_string_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service/openapi.yaml?token=secret") is None

    def test_fragment_is_rejected(self) -> None:
        assert sanitize_source_locator("order-service/openapi.yaml#fragment") is None


class TestProjectEvidence:
    def test_all_requested_ids_resolve(self) -> None:
        rows = {
            "evidence": {
                "evidence:declared:a": _declared_row(
                    "evidence:declared:a", source_file="order-service/openapi.yaml"
                ),
            },
            "relations": [],
        }

        result = project_evidence(rows, requested_ids=["evidence:declared:a"])

        assert result.missing_evidence_refs == []
        assert [record.id for record in result.records] == ["evidence:declared:a"]
        record = result.records[0]
        assert record.evidence_type.value == "DECLARED"
        assert record.observation is None
        assert record.source_locator == "order-service/openapi.yaml"
        assert record.source_revision == "abc123"

    def test_observed_record_carries_bounded_observation_metadata(self) -> None:
        rows = {
            "evidence": {"evidence:observed:a": _observed_row("evidence:observed:a")},
            "relations": [],
        }

        result = project_evidence(rows, requested_ids=["evidence:observed:a"])

        record = result.records[0]
        assert record.evidence_type.value == "OBSERVED"
        assert record.observation is not None
        assert record.observation.environment == "demo"
        assert record.observation.observation_count == 3
        assert record.source_locator == "opentelemetry"

    def test_missing_id_is_reported_and_excluded_from_records(self) -> None:
        rows = {"evidence": {}, "relations": []}

        result = project_evidence(rows, requested_ids=["evidence:declared:missing"])

        assert result.records == []
        assert result.missing_evidence_refs == ["evidence:declared:missing"]

    def test_mixed_resolved_and_missing_partition_requested_ids(self) -> None:
        rows = {
            "evidence": {
                "evidence:declared:a": _declared_row("evidence:declared:a", source_file=None),
            },
            "relations": [],
        }

        result = project_evidence(
            rows, requested_ids=["evidence:declared:a", "evidence:declared:missing"]
        )

        assert [record.id for record in result.records] == ["evidence:declared:a"]
        assert result.missing_evidence_refs == ["evidence:declared:missing"]

    def test_supports_are_grouped_sorted_and_deduplicated(self) -> None:
        rows = {
            "evidence": {
                "evidence:declared:a": _declared_row("evidence:declared:a", source_file=None),
            },
            "relations": [
                {
                    "type": "SENDS",
                    "source_id": "service:order-service",
                    "target_id": "queue:payment-q",
                    "evidence_ids": ["evidence:declared:a"],
                },
                {
                    "type": "CALLS",
                    "source_id": "service:order-service",
                    "target_id": "operation:service:product-service:GET:/products/{id}",
                    "evidence_ids": ["evidence:declared:a", "evidence:declared:a"],
                },
                {
                    "type": "CALLS",
                    "source_id": "service:order-service",
                    "target_id": "operation:service:product-service:GET:/products/{id}",
                    "evidence_ids": ["evidence:declared:a"],
                },
                {
                    "type": "PROVIDES",
                    "source_id": "service:product-service",
                    "target_id": "operation:service:product-service:GET:/products/{id}",
                    "evidence_ids": ["evidence:declared:other"],
                },
            ],
        }

        result = project_evidence(rows, requested_ids=["evidence:declared:a"])

        record = result.records[0]
        assert record.supports == [
            SupportedFact(
                relation_type=EvidenceRelationType.CALLS,
                source_id="service:order-service",
                target_id="operation:service:product-service:GET:/products/{id}",
            ),
            SupportedFact(
                relation_type=EvidenceRelationType.SENDS,
                source_id="service:order-service",
                target_id="queue:payment-q",
            ),
        ]
