"""v0.6.0 I3.1b - the draft public locality contract (schema 0.6) for
`get_service_dependencies_by_locality` (I3 decision record D1-D16,
docs/specifications/0.6.0/i3-decision-record.md).

This module defines only the data contract: the two request modes, the `LocalityAnswer` envelope
and its payloads. It contains no service logic, no Neo4j access and no projection. It is separate
from the closed 0.5 `ArchitectureAnswer` (D2): it reuses `Producer`, `SnapshotRef`, `Outcome` and
`EvidenceRecord`, never the 0.5 tool, claim or limitation enums. Like `contracts.py`, the public
enums mirror the internal I2 values by value, not by import, so internal churn cannot silently
change the published schema (`tests/unit/test_locality_contracts.py` pins the parity).
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable, Sequence
from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator
from pydantic.config import JsonDict

from app.architecture_intelligence.contracts import (
    ENVIRONMENT_PATTERN,
    SNAPSHOT_ID_PATTERN,
    EvidenceRecord,
    Outcome,
    Producer,
    SnapshotRef,
)

_SHA256_HEX = r"[0-9a-f]{64}"
# I1 v2 contract §2 (`app.canonical.ids.SCOPED_CALL_V2_ID_PREFIX`).
V2_EVIDENCE_ID_PATTERN = rf"^evidence:otel:calls-scoped:v2:{_SHA256_HEX}$"
# I2 D9/D14 (`app.architecture_intelligence.local_assessment.ASSERTION_PREFIX`/`ASSESSMENT_PREFIX`).
_ASSERTION_ID_PATTERN = rf"^aip:local-assertion:v1:{_SHA256_HEX}$"
_ASSESSMENT_ID_PATTERN = rf"^aip:local-assessment:v1:{_SHA256_HEX}$"
_DAY_PATTERN = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
# D3: a date-time bound is well-formed but unsupported (I2 phase 1), so the request accepts it.
_DAY_OR_DATETIME_PATTERN = (
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"
    r"(T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2}))?$"
)
# Canonical ids, names and opaque tokens: non-empty, no whitespace or control characters.
_OPAQUE_ID_PATTERN = r"^[^\s\x00-\x1f\x7f]+$"
_DIMENSION_PATTERN = r"^[a-z][a-z0-9_.-]*$"
_CURSOR_PATTERN = r"^[A-Za-z0-9_-]+$"
_LOCALITY_REASON_PATTERN = r"^LOCALITY_[A-Z0-9_]+$"

LocalitySchemaVersion = Literal["0.6"]
LOCALITY_SCHEMA_VERSION: LocalitySchemaVersion = get_args(LocalitySchemaVersion)[0]
LocalityToolName = Literal["get_service_dependencies_by_locality"]
LOCALITY_TOOL_NAME: LocalityToolName = get_args(LocalityToolName)[0]
LocalityMode = Literal["query", "evidence"]

# D4 bounds. Initial values, not measured safe limits or SLOs.
PAIR_BOUND = 2000
CAPTURE_SOURCE_BOUND = 2000
MAX_CANDIDATE_PAGE = 500
MAX_LOCALITIES_PER_PAGE = 50
MAX_MEMBERSHIPS_PER_PAGE = 200
MAX_CALLER_LOCALITIES = 50
COMPARE_SIZE = 2
MAX_EVIDENCE_REFS = 20
CURSOR_FORMAT_VERSION = 1
_MAX_CURSOR_LENGTH = 2048

SUPPORTED_RELATION = "CALLS"
DEFAULT_DIMENSIONS: tuple[str, ...] = ("cluster", "namespace", "workload")
LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE = "LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"
TARGET_RUNTIME_SCOPE_UNKNOWN = "UNKNOWN"


# --- Enums (by value; D9, D10, I2 D4/D13/D14) ---------------------------------------------------


class LocalityLimitationCode(StrEnum):
    """D9: the closed 0.6 envelope codes, separate from the 0.5 `LimitationCode`."""

    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"
    SNAPSHOT_NOT_AVAILABLE = "SNAPSHOT_NOT_AVAILABLE"
    CURSOR_QUERY_MISMATCH = "CURSOR_QUERY_MISMATCH"
    RESULT_LIMIT_EXCEEDED = "RESULT_LIMIT_EXCEEDED"
    INVENTORY_INCOMPLETE = "INVENTORY_INCOMPLETE"
    COMPARISON_INCOMPLETE = "COMPARISON_INCOMPLETE"
    SELECTION_NOT_ESTABLISHED = "SELECTION_NOT_ESTABLISHED"
    PROVIDER_OWNER_UNRESOLVED = "PROVIDER_OWNER_UNRESOLVED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


# D9: a refusal evaluated nothing, so its answer carries `data: null` and exactly this one code.
REFUSAL_CODES = frozenset(
    {
        LocalityLimitationCode.UNSUPPORTED_REQUEST,
        LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE,
        LocalityLimitationCode.CURSOR_QUERY_MISMATCH,
        LocalityLimitationCode.RESULT_LIMIT_EXCEEDED,
    }
)
UNSUPPORTED_REQUEST_REASONS = frozenset(
    {
        "LOCALITY_UNSUPPORTED_DIMENSION",
        "LOCALITY_UNSUPPORTED_RELATION",
        "LOCALITY_UNSUPPORTED_TEMPORAL_RESOLUTION",
    }
)


class LocalDisposition(StrEnum):
    """I1 §10 / I2 dispositions, carried unchanged inside the payload (never envelope outcomes)."""

    APPLICABLE = "APPLICABLE"
    INAPPLICABLE = "INAPPLICABLE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNRESOLVED = "UNRESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICT = "CONFLICT"
    UNSUPPORTED = "UNSUPPORTED"


class AdmissionBasis(StrEnum):
    """I2 D13.7."""

    EXPLICIT = "EXPLICIT"
    POD_UID = "POD_UID"
    CLUSTER_NAMESPACE = "CLUSTER_NAMESPACE"


class CandidateLimitationCode(StrEnum):
    """The internal I2 limitation codes (D4, D13.4, D14.1), carried unchanged."""

    NO_SELECTABLE_COVERING_SOURCE = "NO_SELECTABLE_COVERING_SOURCE"
    REQUEST_ENVIRONMENT_MISMATCH = "REQUEST_ENVIRONMENT_MISMATCH"
    WORKLOAD_UID_UNAVAILABLE = "WORKLOAD_UID_UNAVAILABLE"


class CapturedWorkloadKind(StrEnum):
    """I2 D14.1: the captured Kubernetes kind exactly."""

    DEPLOYMENT = "Deployment"
    STATEFULSET = "StatefulSet"
    DAEMONSET = "DaemonSet"


class LocalQualification(StrEnum):
    """I2 D14.4: every assertion has v2, so only these two are reachable."""

    CONFIRMED = "CONFIRMED"
    OBSERVED_ONLY = "OBSERVED_ONLY"


class SelectionMode(StrEnum):
    EXPLICIT_SOURCE = "EXPLICIT_SOURCE"
    IMPLICIT_COVERING_SOURCES = "IMPLICIT_COVERING_SOURCES"


class Completeness(StrEnum):
    """Relative to the evaluated inventory only (I3 §7, §9); never "the system was observed"."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"


class ComparisonCompleteness(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NOT_ESTABLISHED = "NOT_ESTABLISHED"


class PresentationCap(StrEnum):
    WORKLOADS = "WORKLOADS"
    MEMBERSHIPS = "MEMBERSHIPS"


class ScopeEvaluation(StrEnum):
    """D10: a selected identity's status, derived only from the evaluated inventory."""

    POSITIVE = "POSITIVE"
    EVALUATED_NO_POSITIVE = "EVALUATED_NO_POSITIVE"
    UNKNOWN = "UNKNOWN"


class ProviderOwnerReason(StrEnum):
    """D8: zero or several evidenced `PROVIDES` owners."""

    PROVIDER_OWNER_MISSING = "PROVIDER_OWNER_MISSING"
    PROVIDER_OWNER_AMBIGUOUS = "PROVIDER_OWNER_AMBIGUOUS"


class EvidenceRefStatus(StrEnum):
    RESOLVED = "RESOLVED"
    NOT_FOUND = "NOT_FOUND"


class EvidenceRefKind(StrEnum):
    """D11: what a resolved ref is."""

    SCOPED_V2 = "SCOPED_V2"
    POD_CAPTURE = "POD_CAPTURE"
    OWNER_CAPTURE = "OWNER_CAPTURE"


# --- Shared helpers -----------------------------------------------------------------------------

_UNIQUE: JsonDict = {"uniqueItems": True}


def _check_sorted_unique[T](values: Sequence[T], key: Any, what: str) -> None:
    keys = [key(value) for value in values]
    if keys != sorted(keys) or len(keys) != len(set(keys)):
        raise ValueError(f"{what} must be sorted and duplicate-free")


def _check_sorted_unique_strings(values: Sequence[str], what: str) -> None:
    _check_sorted_unique(values, lambda value: value, what)


def _closed(**extra: Any) -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid", **extra)


def _parse_day(value: str) -> date | None:
    """A `YYYY-MM-DD` that is a real calendar day, else None (a date-time is not a day)."""
    if len(value) != 10:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# --- Identities ---------------------------------------------------------------------------------


class WorkloadIdentity(BaseModel):
    """D3: an exact captured caller Workload. The captured UID is required; `name` is never part of
    the identity."""

    model_config = _closed()

    cluster_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    namespace: str = Field(pattern=_OPAQUE_ID_PATTERN)
    kind: CapturedWorkloadKind
    uid: str = Field(pattern=_OPAQUE_ID_PATTERN)


def workload_identity_key(identity: WorkloadIdentity) -> tuple[str, str, str, str]:
    return (identity.cluster_uid, identity.namespace, identity.kind.value, identity.uid)


class SourceSelector(BaseModel):
    model_config = _closed()

    source_instance_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    revision: str = Field(pattern=_OPAQUE_ID_PATTERN)


def source_key(source: SourceSelector | PairSourceRef | EvaluatedSource) -> tuple[str, str]:
    return (source.source_instance_id, source.revision)


class CapturedWorkloadRef(BaseModel):
    """The I2 `CapturedWorkload` as resolved by one pair or candidate. `uid` is null only when the
    capture carried none (`WORKLOAD_UID_UNAVAILABLE`, I2 D14.1)."""

    model_config = _closed()

    workload_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    name: str = Field(pattern=_OPAQUE_ID_PATTERN)
    cluster_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    namespace: str = Field(pattern=_OPAQUE_ID_PATTERN)
    kind: CapturedWorkloadKind
    uid: str | None = Field(pattern=_OPAQUE_ID_PATTERN)

    def identity(self) -> WorkloadIdentity | None:
        if self.uid is None:
            return None
        return WorkloadIdentity(
            cluster_uid=self.cluster_uid, namespace=self.namespace, kind=self.kind, uid=self.uid
        )


# --- Cursor (D5) --------------------------------------------------------------------------------


class LocalityCursor(BaseModel):
    """The decoded D5 cursor. It is opaque to clients; this model only checks its structure."""

    model_config = _closed()

    v: Literal[1]
    after_id: str = Field(pattern=V2_EVIDENCE_ID_PATTERN)
    query_digest: str = Field(pattern=rf"^{_SHA256_HEX}$")
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)
    schema_version: LocalitySchemaVersion


def encode_cursor(cursor: LocalityCursor) -> str:
    """Unpadded base64url of the canonical JSON (sorted keys, no whitespace)."""
    payload = json.dumps(cursor.model_dump(), sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> LocalityCursor:
    """Raises `ValueError` for anything that is not a well-formed D5 cursor."""
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        payload = json.loads(raw.decode())
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("cursor is not a well-formed locality cursor") from error
    # A non-object payload fails here too (pydantic's ValidationError is a ValueError).
    cursor = LocalityCursor.model_validate(payload)
    if encode_cursor(cursor) != value:
        raise ValueError("cursor is not in canonical form")
    return cursor


def _check_cursor(value: str | None) -> str | None:
    if value is not None:
        decode_cursor(value)
    return value


# --- Requests (D3, D11) -------------------------------------------------------------------------


class LocalityQueryRequest(BaseModel):
    """`mode: "query"` (D3). Well-formed but unsupported values (a date-time bound, a non-`CALLS`
    relation, an unknown dimension) are accepted here and refused by the service (D9)."""

    model_config = _closed()

    mode: Literal["query"]
    subject_service_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=ENVIRONMENT_PATTERN)
    first_day: str = Field(pattern=_DAY_OR_DATETIME_PATTERN)
    last_day: str = Field(pattern=_DAY_OR_DATETIME_PATTERN)
    relation_type: str = Field(default=SUPPORTED_RELATION, pattern=_OPAQUE_ID_PATTERN)
    dimensions: list[Annotated[str, Field(pattern=_DIMENSION_PATTERN)]] = Field(
        default_factory=lambda: list(DEFAULT_DIMENSIONS), min_length=1, json_schema_extra=_UNIQUE
    )
    object_operation_id: str | None = Field(default=None, pattern=_OPAQUE_ID_PATTERN)
    provider_service_id: str | None = Field(default=None, pattern=_OPAQUE_ID_PATTERN)
    source_selector: SourceSelector | None = None
    caller_localities: list[WorkloadIdentity] | None = Field(
        default=None, min_length=1, max_length=MAX_CALLER_LOCALITIES, json_schema_extra=_UNIQUE
    )
    compare: list[WorkloadIdentity] | None = Field(
        default=None, min_length=COMPARE_SIZE, max_length=COMPARE_SIZE, json_schema_extra=_UNIQUE
    )
    snapshot_id: str | None = Field(default=None, pattern=SNAPSHOT_ID_PATTERN)
    cursor: str | None = Field(
        default=None, min_length=1, max_length=_MAX_CURSOR_LENGTH, pattern=_CURSOR_PATTERN
    )

    @field_validator("dimensions")
    @classmethod
    def _check_dimensions(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "dimensions")
        return value

    @field_validator("caller_localities")
    @classmethod
    def _check_caller_localities(
        cls, value: list[WorkloadIdentity] | None
    ) -> list[WorkloadIdentity] | None:
        if value is not None:
            _check_sorted_unique(value, workload_identity_key, "caller_localities")
        return value

    @field_validator("compare")
    @classmethod
    def _check_compare(cls, value: list[WorkloadIdentity] | None) -> list[WorkloadIdentity] | None:
        # Request order is meaningful (first, second); only distinctness is required.
        if value is not None and len({workload_identity_key(item) for item in value}) != len(value):
            raise ValueError("compare must name two distinct Workload identities")
        return value

    @field_validator("cursor")
    @classmethod
    def _check_cursor_structure(cls, value: str | None) -> str | None:
        return _check_cursor(value)

    @model_validator(mode="after")
    def _check_request(self) -> LocalityQueryRequest:
        first, last = _parse_day(self.first_day), _parse_day(self.last_day)
        for raw, parsed in ((self.first_day, first), (self.last_day, last)):
            if len(raw) == 10 and parsed is None:
                raise ValueError(f"not a calendar day: {raw!r}")
        if first is not None and last is not None and first > last:
            raise ValueError("first_day must not be after last_day")
        if self.compare is not None and self.caller_localities is not None:
            selected = {workload_identity_key(item) for item in self.caller_localities}
            if not {workload_identity_key(item) for item in self.compare} <= selected:
                raise ValueError("every compare identity must be a member of caller_localities")
        return self


class LocalityEvidenceRequest(BaseModel):
    """`mode: "evidence"` (D11): exact refs resolved at the supplied snapshot."""

    model_config = _closed()

    mode: Literal["evidence"]
    subject_service_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    snapshot_id: str = Field(pattern=SNAPSHOT_ID_PATTERN)
    refs: list[Annotated[str, Field(pattern=_OPAQUE_ID_PATTERN)]] = Field(
        min_length=1, max_length=MAX_EVIDENCE_REFS, json_schema_extra=_UNIQUE
    )
    object_operation_id: str | None = Field(default=None, pattern=_OPAQUE_ID_PATTERN)

    @field_validator("refs")
    @classmethod
    def _check_refs(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "refs")
        return value


class ServiceDependenciesByLocalityRequest(
    RootModel[
        Annotated[LocalityQueryRequest | LocalityEvidenceRequest, Field(discriminator="mode")]
    ]
):
    """The single MCP `request` argument (D1): one of the two modes, discriminated on `mode`."""

    model_config = ConfigDict(frozen=True, title="ServiceDependenciesByLocalityRequest")


# --- Query payload (D10) ------------------------------------------------------------------------


class EvaluatedSource(BaseModel):
    """A capture source that formed at least one pair (D10 `evaluated_sources`)."""

    model_config = _closed()

    source_instance_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    revision: str = Field(pattern=_OPAQUE_ID_PATTERN)
    cluster_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    namespaces: list[Annotated[str, Field(pattern=_OPAQUE_ID_PATTERN)]] = Field(
        json_schema_extra=_UNIQUE
    )
    evidence_mode: str = Field(pattern=_OPAQUE_ID_PATTERN)
    captured_at: str | None

    @field_validator("namespaces")
    @classmethod
    def _check_namespaces(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "namespaces")
        return value


class PairSourceRef(BaseModel):
    model_config = _closed()

    source_instance_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    revision: str = Field(pattern=_OPAQUE_ID_PATTERN)


_Token = Annotated[str, Field(pattern=_OPAQUE_ID_PATTERN)]
_Reason = Annotated[str, Field(pattern=_LOCALITY_REASON_PATTERN)]
_V2Id = Annotated[str, Field(pattern=V2_EVIDENCE_ID_PATTERN)]


def _pair_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `_check_pair` for external validators (I2 `evaluate_pair`/`_phase_4`)."""
    schema["allOf"] = [
        {
            "if": {"properties": {"disposition": {"const": "APPLICABLE"}}},
            "then": {
                "properties": {
                    "phase": {"const": 4},
                    "workload": {"not": {"type": "null"}},
                    "reasons": {"maxItems": 0},
                }
            },
            "else": {"properties": {"workload": {"type": "null"}}},
        },
        {
            "if": {"properties": {"phase": {"const": 2}}},
            "then": {"properties": {"disposition": {"const": "UNSUPPORTED"}}},
        },
    ]


class PairEntry(BaseModel):
    """One admitted (candidate, source) pair, unchanged from I2 (D13). Only an `APPLICABLE` pair
    carries a resolved Workload (`_phase_4`)."""

    model_config = _closed(json_schema_extra=_pair_schema_extra)

    source: PairSourceRef
    admission: list[AdmissionBasis] = Field(min_length=1, json_schema_extra=_UNIQUE)
    phase: Literal[2, 3, 4]
    disposition: LocalDisposition
    reasons: list[_Reason] = Field(json_schema_extra=_UNIQUE)
    limitations: list[CandidateLimitationCode] = Field(json_schema_extra=_UNIQUE)
    workload: CapturedWorkloadRef | None
    evidence_refs: list[_Token] = Field(json_schema_extra=_UNIQUE)

    @field_validator("admission", "reasons", "limitations", "evidence_refs")
    @classmethod
    def _check_lists(cls, value: list[Any]) -> list[Any]:
        _check_sorted_unique([str(item) for item in value], lambda item: item, "pair lists")
        return value

    @model_validator(mode="after")
    def _check_pair(self) -> PairEntry:
        applicable = self.disposition is LocalDisposition.APPLICABLE
        if applicable and (self.phase != 4 or self.workload is None or self.reasons):
            raise ValueError("an APPLICABLE pair is phase 4, with a Workload and no reasons")
        if not applicable and self.workload is not None:
            raise ValueError("only an APPLICABLE pair carries a resolved Workload")
        if self.phase == 2 and self.disposition is not LocalDisposition.UNSUPPORTED:
            raise ValueError("a phase-2 pair is UNSUPPORTED")
        return self


class CandidateEntry(BaseModel):
    """One evaluated v2 candidate: its I2 summary and **every** admitted pair (D4, D10)."""

    model_config = _closed()

    v2_evidence_id: str = Field(pattern=V2_EVIDENCE_ID_PATTERN)
    disposition: LocalDisposition
    reasons: list[_Reason] = Field(json_schema_extra=_UNIQUE)
    limitations: list[CandidateLimitationCode] = Field(json_schema_extra=_UNIQUE)
    workload: CapturedWorkloadRef | None
    pairs: list[PairEntry] = Field(json_schema_extra=_UNIQUE)

    @field_validator("reasons", "limitations")
    @classmethod
    def _check_lists(cls, value: list[Any]) -> list[Any]:
        _check_sorted_unique([str(item) for item in value], lambda item: item, "candidate lists")
        return value

    @field_validator("pairs")
    @classmethod
    def _check_pairs(cls, value: list[PairEntry]) -> list[PairEntry]:
        _check_sorted_unique(value, lambda pair: source_key(pair.source), "pairs")
        return value


class SelectedCaptureRef(BaseModel):
    model_config = _closed()

    source_instance_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    revision: str = Field(pattern=_OPAQUE_ID_PATTERN)
    evidence_mode: str = Field(pattern=_OPAQUE_ID_PATTERN)
    captured_at: str = Field(pattern=_OPAQUE_ID_PATTERN)


class RuleRef(BaseModel):
    model_config = _closed()

    id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    version: int = Field(ge=1)


class LocalObservation(BaseModel):
    model_config = _closed()

    evidence_ids: list[_V2Id] = Field(min_length=1, json_schema_extra=_UNIQUE)
    first_seen: datetime
    last_seen: datetime
    lineage_complete: bool

    @field_validator("evidence_ids")
    @classmethod
    def _check_ids(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "observation.evidence_ids")
        return value

    @model_validator(mode="after")
    def _check_bounds(self) -> LocalObservation:
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must not be after last_seen")
        return self


class SourceLimitation(BaseModel):
    """A non-applicable pair of a contributing candidate (I2 `source_limitations`)."""

    model_config = _closed()

    v2_evidence_id: str = Field(pattern=V2_EVIDENCE_ID_PATTERN)
    pair: PairEntry


class OperationAssessment(BaseModel):
    """One I2 `QualifiedLocalEvidenceAssessment`, values unchanged. The subject, relation,
    environment, window, caller Workload and snapshot are carried once by the containing locality,
    request context and envelope (D16.3)."""

    model_config = _closed()

    assertion_id: str = Field(pattern=_ASSERTION_ID_PATTERN)
    assessment_id: str = Field(pattern=_ASSESSMENT_ID_PATTERN)
    object_operation_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    applicability: Literal["APPLICABLE"]
    qualification: LocalQualification
    observation: LocalObservation
    declared_evidence_ids: list[_Token] = Field(json_schema_extra=_UNIQUE)
    selected_captures: list[SelectedCaptureRef] = Field(min_length=1, json_schema_extra=_UNIQUE)
    capture_evidence_refs: list[_Token] = Field(json_schema_extra=_UNIQUE)
    source_limitations: list[SourceLimitation] = Field(json_schema_extra=_UNIQUE)
    rules: list[RuleRef] = Field(min_length=1, json_schema_extra=_UNIQUE)

    @field_validator("declared_evidence_ids", "capture_evidence_refs")
    @classmethod
    def _check_refs(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "assessment evidence ids")
        return value

    @field_validator("selected_captures")
    @classmethod
    def _check_captures(cls, value: list[SelectedCaptureRef]) -> list[SelectedCaptureRef]:
        _check_sorted_unique(value, lambda c: (c.source_instance_id, c.revision), "captures")
        return value

    @field_validator("source_limitations")
    @classmethod
    def _check_source_limitations(cls, value: list[SourceLimitation]) -> list[SourceLimitation]:
        _check_sorted_unique(
            value, lambda item: (item.v2_evidence_id, *source_key(item.pair.source)), "limitations"
        )
        if any(item.pair.disposition is LocalDisposition.APPLICABLE for item in value):
            raise ValueError("source_limitations holds only non-applicable pairs")
        return value

    @field_validator("rules")
    @classmethod
    def _check_rules(cls, value: list[RuleRef]) -> list[RuleRef]:
        _check_sorted_unique(value, lambda rule: (rule.id, rule.version), "rules")
        return value

    def evidence_union(self) -> set[str]:
        return {
            *self.observation.evidence_ids,
            *self.declared_evidence_ids,
            *self.capture_evidence_refs,
        }


class ProviderGroup(BaseModel):
    """D8: one provider Service in one caller Workload. No group-level qualification."""

    model_config = _closed()

    provider_service_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    operation_ids: list[_Token] = Field(min_length=1, json_schema_extra=_UNIQUE)
    member_qualifications: list[LocalQualification] = Field(
        min_length=1, max_length=2, json_schema_extra=_UNIQUE
    )
    evidence_refs: list[_Token] = Field(min_length=1, json_schema_extra=_UNIQUE)

    @field_validator("operation_ids", "evidence_refs")
    @classmethod
    def _check_lists(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "provider group lists")
        return value

    @field_validator("member_qualifications")
    @classmethod
    def _check_qualifications(cls, value: list[LocalQualification]) -> list[LocalQualification]:
        _check_sorted_unique([item.value for item in value], lambda item: item, "qualifications")
        return value


class UnresolvedOwnerOperation(BaseModel):
    model_config = _closed()

    operation_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    reason: ProviderOwnerReason


class LocalityWorkload(BaseModel):
    """A positive caller Workload: its exact identity plus presentation-only name/logical id."""

    model_config = _closed()

    workload_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    name: str = Field(pattern=_OPAQUE_ID_PATTERN)
    cluster_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    namespace: str = Field(pattern=_OPAQUE_ID_PATTERN)
    kind: CapturedWorkloadKind
    uid: str = Field(pattern=_OPAQUE_ID_PATTERN)

    def identity(self) -> WorkloadIdentity:
        return WorkloadIdentity(
            cluster_uid=self.cluster_uid, namespace=self.namespace, kind=self.kind, uid=self.uid
        )


class LocalityEntry(BaseModel):
    """D10 `localities[]`: one positive caller Workload."""

    model_config = _closed()

    workload: LocalityWorkload
    assessments: list[OperationAssessment] = Field(min_length=1, json_schema_extra=_UNIQUE)
    provider_groups: list[ProviderGroup] = Field(json_schema_extra=_UNIQUE)
    unresolved_owner_operations: list[UnresolvedOwnerOperation] = Field(json_schema_extra=_UNIQUE)
    target_runtime_scope: Literal["UNKNOWN"]
    lineage_complete: bool

    @model_validator(mode="after")
    def _check_locality(self) -> LocalityEntry:
        _check_sorted_unique(self.assessments, lambda item: item.assertion_id, "assessments")
        _check_sorted_unique(
            self.provider_groups, lambda group: group.provider_service_id, "provider_groups"
        )
        _check_sorted_unique(
            self.unresolved_owner_operations,
            lambda item: item.operation_id,
            "unresolved_owner_operations",
        )
        by_operation: dict[str, list[OperationAssessment]] = {}
        for assessment in self.assessments:
            by_operation.setdefault(assessment.object_operation_id, []).append(assessment)
        grouped = [operation for group in self.provider_groups for operation in group.operation_ids]
        unresolved = [item.operation_id for item in self.unresolved_owner_operations]
        placed = grouped + unresolved
        if sorted(placed) != sorted(by_operation) or len(placed) != len(set(placed)):
            raise ValueError(
                "every assessed Operation is in exactly one provider group or unresolved-owner entry"
            )
        for group in self.provider_groups:
            members = [a for operation in group.operation_ids for a in by_operation[operation]]
            if group.member_qualifications != sorted({a.qualification for a in members}):
                raise ValueError("member_qualifications must be the members' distinct statuses")
            if set(group.evidence_refs) != set().union(*(a.evidence_union() for a in members)):
                raise ValueError("a provider group's evidence_refs is its members' union")
        if any(a.observation.lineage_complete != self.lineage_complete for a in self.assessments):
            raise ValueError("assessment lineage must match the locality's lineage_complete")
        return self


class SelectedScope(BaseModel):
    model_config = _closed()

    workload: WorkloadIdentity
    evaluation: ScopeEvaluation


class ComparisonSide(BaseModel):
    model_config = _closed()

    qualification: LocalQualification
    assertion_id: str = Field(pattern=_ASSERTION_ID_PATTERN)
    assessment_id: str = Field(pattern=_ASSESSMENT_ID_PATTERN)


class ComparedMembership(BaseModel):
    """A `(provider Service or unresolved owner, Operation)` membership positive in one scope.
    `provider_service_id` is null when the owner is unresolved (D8)."""

    model_config = _closed()

    provider_service_id: str | None = Field(pattern=_OPAQUE_ID_PATTERN)
    operation_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    side: ComparisonSide


class SharedMembership(BaseModel):
    model_config = _closed()

    provider_service_id: str | None = Field(pattern=_OPAQUE_ID_PATTERN)
    operation_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    first: ComparisonSide
    second: ComparisonSide


def _membership_key(item: ComparedMembership | SharedMembership) -> tuple[str, str]:
    return (item.provider_service_id or "", item.operation_id)


class Comparison(BaseModel):
    """D10 comparison of two selected scopes. Labels mean "positively evidenced here", never
    "absent there"."""

    model_config = _closed()

    scopes: list[SelectedScope] = Field(min_length=COMPARE_SIZE, max_length=COMPARE_SIZE)
    in_both: list[SharedMembership] = Field(json_schema_extra=_UNIQUE)
    only_in_first: list[ComparedMembership] = Field(json_schema_extra=_UNIQUE)
    only_in_second: list[ComparedMembership] = Field(json_schema_extra=_UNIQUE)
    qualification_differs: list[SharedMembership] = Field(json_schema_extra=_UNIQUE)
    completeness: ComparisonCompleteness

    @model_validator(mode="after")
    def _check_comparison(self) -> Comparison:
        for name in ("in_both", "only_in_first", "only_in_second", "qualification_differs"):
            _check_sorted_unique(getattr(self, name), _membership_key, name)
        differs = [m for m in self.in_both if m.first.qualification != m.second.qualification]
        if self.qualification_differs != differs:
            raise ValueError("qualification_differs is the in_both entries whose statuses differ")
        return self


class InventoryBounds(BaseModel):
    """The D4 values actually applied to this answer page."""

    model_config = _closed()

    pair_bound: Literal[2000]
    capture_source_bound: Literal[2000]
    candidate_page_size: int = Field(ge=1, le=MAX_CANDIDATE_PAGE)
    max_localities: Literal[50]
    max_memberships: Literal[200]


def candidate_page_size(considered_capture_sources: int) -> int:
    """D4: `k = min(500, ⌊P / S⌋)`, and 500 when no source is considered."""
    if considered_capture_sources == 0:
        return MAX_CANDIDATE_PAGE
    return min(MAX_CANDIDATE_PAGE, PAIR_BOUND // considered_capture_sources)


class Inventory(BaseModel):
    model_config = _closed()

    considered_capture_source_count: int = Field(ge=0, le=CAPTURE_SOURCE_BOUND)
    evaluated_v2_candidate_count: int = Field(ge=0, le=MAX_CANDIDATE_PAGE)
    admitted_pair_count: int = Field(ge=0, le=PAIR_BOUND)
    evaluated_sources: list[EvaluatedSource] = Field(json_schema_extra=_UNIQUE)
    bounds: InventoryBounds
    i2_truncated: bool
    # D16.11: this page was requested with a cursor, so it never evaluated the whole inventory.
    continuation: bool
    cap_reached: list[PresentationCap] = Field(max_length=2, json_schema_extra=_UNIQUE)
    next_cursor: str | None = Field(
        min_length=1, max_length=_MAX_CURSOR_LENGTH, pattern=_CURSOR_PATTERN
    )
    completeness: Completeness

    @field_validator("cap_reached")
    @classmethod
    def _check_caps(cls, value: list[PresentationCap]) -> list[PresentationCap]:
        _check_sorted_unique([item.value for item in value], lambda item: item, "cap_reached")
        return value

    @field_validator("next_cursor")
    @classmethod
    def _check_next_cursor(cls, value: str | None) -> str | None:
        return _check_cursor(value)

    @model_validator(mode="after")
    def _check_inventory(self) -> Inventory:
        _check_sorted_unique(self.evaluated_sources, source_key, "evaluated_sources")
        if self.bounds.candidate_page_size != candidate_page_size(
            self.considered_capture_source_count
        ):
            raise ValueError("candidate_page_size must be min(500, 2000 // S) (D4)")
        if self.evaluated_v2_candidate_count > self.bounds.candidate_page_size:
            raise ValueError("more candidates than the internal page size")
        more = self.i2_truncated or bool(self.cap_reached)
        if (more or self.continuation) != (self.completeness is Completeness.PARTIAL):
            raise ValueError(
                "completeness is PARTIAL exactly when I2 truncated, a cap was hit or the page "
                "continues a cursor (D7, D16.11)"
            )
        if more != (self.next_cursor is not None):
            raise ValueError("next_cursor is present exactly when more candidates remain")
        return self


class LocalityRequestContext(BaseModel):
    """The normalized, evaluated request (D3, D10). An evaluated request is supported, so its
    relation, dimensions and days are the supported forms."""

    model_config = _closed()

    subject_service_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=ENVIRONMENT_PATTERN)
    first_day: str = Field(pattern=_DAY_PATTERN)
    last_day: str = Field(pattern=_DAY_PATTERN)
    relation_type: Literal["CALLS"]
    dimensions: list[Literal["cluster", "namespace", "workload"]] = Field(
        min_length=1, json_schema_extra=_UNIQUE
    )
    object_operation_id: str | None = Field(pattern=_OPAQUE_ID_PATTERN)
    provider_service_id: str | None = Field(pattern=_OPAQUE_ID_PATTERN)
    source_selector: SourceSelector | None
    caller_localities: list[WorkloadIdentity] | None = Field(
        min_length=1, max_length=MAX_CALLER_LOCALITIES, json_schema_extra=_UNIQUE
    )
    compare: list[WorkloadIdentity] | None = Field(
        min_length=COMPARE_SIZE, max_length=COMPARE_SIZE, json_schema_extra=_UNIQUE
    )
    selection_mode: SelectionMode

    @model_validator(mode="after")
    def _check_context(self) -> LocalityRequestContext:
        _check_sorted_unique_strings(list(self.dimensions), "dimensions")
        first, last = _parse_day(self.first_day), _parse_day(self.last_day)
        if first is None or last is None or first > last:
            raise ValueError("first_day/last_day must be an ordered pair of calendar days")
        if self.caller_localities is not None:
            _check_sorted_unique(self.caller_localities, workload_identity_key, "caller_localities")
        expected_mode = (
            SelectionMode.EXPLICIT_SOURCE
            if self.source_selector is not None
            else SelectionMode.IMPLICIT_COVERING_SOURCES
        )
        if self.selection_mode is not expected_mode:
            raise ValueError(
                "selection_mode must be EXPLICIT_SOURCE exactly with a source_selector"
            )
        return self


def _query_data_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """`comparison` is present exactly when `compare` was requested; `selection` exactly when
    `caller_localities` was (mirrors `_check_query_data`)."""
    schema["allOf"] = [
        {
            "if": {
                "properties": {"request_context": {"properties": {"compare": {"type": "null"}}}}
            },
            "then": {"properties": {"comparison": {"type": "null"}}},
            "else": {"properties": {"comparison": {"not": {"type": "null"}}}},
        },
        {
            "if": {
                "properties": {
                    "request_context": {"properties": {"caller_localities": {"type": "null"}}}
                }
            },
            "then": {"properties": {"selection": {"type": "null"}}},
            "else": {"properties": {"selection": {"not": {"type": "null"}}}},
        },
    ]


class ServiceDependenciesByLocalityData(BaseModel):
    """D10: the `mode: "query"` payload."""

    model_config = _closed(json_schema_extra=_query_data_schema_extra)

    request_context: LocalityRequestContext
    coverage: Literal["LOCAL_WORKLOAD_COVERAGE_UNAVAILABLE"]
    inventory: Inventory
    candidates: list[CandidateEntry] = Field(
        max_length=MAX_CANDIDATE_PAGE, json_schema_extra=_UNIQUE
    )
    localities: list[LocalityEntry] = Field(
        max_length=MAX_LOCALITIES_PER_PAGE, json_schema_extra=_UNIQUE
    )
    selection: list[SelectedScope] | None = Field(
        max_length=MAX_CALLER_LOCALITIES, json_schema_extra=_UNIQUE
    )
    comparison: Comparison | None

    @model_validator(mode="after")
    def _check_query_data(self) -> ServiceDependenciesByLocalityData:
        context, inventory = self.request_context, self.inventory
        _check_sorted_unique(self.candidates, lambda item: item.v2_evidence_id, "candidates")
        _check_sorted_unique(
            self.localities,
            lambda item: workload_identity_key(item.workload.identity()),
            "localities",
        )
        if inventory.evaluated_v2_candidate_count != len(self.candidates):
            raise ValueError("evaluated_v2_candidate_count must equal len(candidates)")
        pairs = [pair for candidate in self.candidates for pair in candidate.pairs]
        if inventory.admitted_pair_count != len(pairs):
            raise ValueError("admitted_pair_count must equal the number of listed pairs")
        if {source_key(pair.source) for pair in pairs} != {
            source_key(source) for source in inventory.evaluated_sources
        }:
            raise ValueError("evaluated_sources are exactly the sources that formed a pair")
        if context.source_selector is not None and inventory.considered_capture_source_count > 1:
            raise ValueError("an explicit source_selector considers at most one source (D4)")
        memberships = sum(len(locality.assessments) for locality in self.localities)
        if memberships > MAX_MEMBERSHIPS_PER_PAGE:
            raise ValueError("more provider/Operation memberships than the D4 cap")
        complete = inventory.completeness is Completeness.COMPLETE
        if any(locality.lineage_complete != complete for locality in self.localities):
            raise ValueError("lineage_complete must equal inventory completeness (D7)")
        if context.provider_service_id is not None and any(
            group.provider_service_id != context.provider_service_id
            for locality in self.localities
            for group in locality.provider_groups
        ):
            # D16.4: the filter scopes the projection; unresolved owners stay listed.
            raise ValueError("with provider_service_id, only that provider's groups are listed")
        if context.caller_localities is not None:
            selected = {workload_identity_key(item) for item in context.caller_localities}
            if any(
                workload_identity_key(locality.workload.identity()) not in selected
                for locality in self.localities
            ):
                raise ValueError("with caller_localities, only selected Workloads are listed")
        self._check_selection(context, complete)
        self._check_comparison(context, complete)
        return self

    def evaluate_scope(self, identity: WorkloadIdentity) -> ScopeEvaluation:
        """D10 selected-scope status, derived from this payload only."""
        key = workload_identity_key(identity)
        if any(workload_identity_key(item.workload.identity()) == key for item in self.localities):
            return ScopeEvaluation.POSITIVE
        if self.inventory.completeness is not Completeness.COMPLETE:
            return ScopeEvaluation.UNKNOWN
        for candidate in self.candidates:
            for pair in candidate.pairs:
                resolved = pair.workload.identity() if pair.workload is not None else None
                if (
                    pair.disposition is LocalDisposition.APPLICABLE
                    and resolved is not None
                    and workload_identity_key(resolved) == key
                ):
                    return ScopeEvaluation.EVALUATED_NO_POSITIVE
        return ScopeEvaluation.UNKNOWN

    def _check_selection(self, context: LocalityRequestContext, complete: bool) -> None:
        if self.selection is None:
            if context.caller_localities is not None:
                raise ValueError("selection is required when caller_localities was requested")
            return
        if context.caller_localities is None:
            raise ValueError("selection is present only when caller_localities was requested")
        if [item.workload for item in self.selection] != context.caller_localities:
            raise ValueError("selection lists exactly the requested caller_localities, in order")
        for item in self.selection:
            if item.evaluation is not self.evaluate_scope(item.workload):
                raise ValueError("a selected scope's evaluation must follow D10")

    def _check_comparison(self, context: LocalityRequestContext, complete: bool) -> None:
        comparison = self.comparison
        if comparison is None:
            if context.compare is not None:
                raise ValueError("comparison is required when compare was requested")
            return
        if context.compare is None:
            raise ValueError("comparison is present only when compare was requested")
        if [scope.workload for scope in comparison.scopes] != context.compare:
            raise ValueError("comparison.scopes are the requested compare identities, in order")
        for scope in comparison.scopes:
            if scope.evaluation is not self.evaluate_scope(scope.workload):
                raise ValueError("a compared scope's evaluation must follow D10")
        unknown = any(scope.evaluation is ScopeEvaluation.UNKNOWN for scope in comparison.scopes)
        expected_completeness = (
            ComparisonCompleteness.PARTIAL
            if not complete
            else ComparisonCompleteness.NOT_ESTABLISHED
            if unknown
            else ComparisonCompleteness.COMPLETE
        )
        if comparison.completeness is not expected_completeness:
            raise ValueError("comparison.completeness must follow D10")
        first, second = (self._memberships(scope.workload) for scope in comparison.scopes)
        expected_both = [
            SharedMembership(
                provider_service_id=key[0] or None,
                operation_id=key[1],
                first=first[key],
                second=second[key],
            )
            for key in sorted(first.keys() & second.keys())
        ]
        if comparison.in_both != expected_both:
            raise ValueError("in_both must be the memberships positive in both scopes")
        for name, mine, other in (
            ("only_in_first", first, second),
            ("only_in_second", second, first),
        ):
            expected = [
                ComparedMembership(
                    provider_service_id=key[0] or None, operation_id=key[1], side=mine[key]
                )
                for key in sorted(mine.keys() - other.keys())
            ]
            if getattr(comparison, name) != expected:
                raise ValueError(f"{name} must be the memberships positive only in that scope")

    def _memberships(self, identity: WorkloadIdentity) -> dict[tuple[str, str], ComparisonSide]:
        key = workload_identity_key(identity)
        for locality in self.localities:
            if workload_identity_key(locality.workload.identity()) != key:
                continue
            provider_by_operation = {
                operation: group.provider_service_id
                for group in locality.provider_groups
                for operation in group.operation_ids
            }
            return {
                (
                    provider_by_operation.get(assessment.object_operation_id, ""),
                    assessment.object_operation_id,
                ): ComparisonSide(
                    qualification=assessment.qualification,
                    assertion_id=assessment.assertion_id,
                    assessment_id=assessment.assessment_id,
                )
                for assessment in locality.assessments
            }
        return {}

    def expected_limitation_codes(self) -> set[LocalityLimitationCode]:
        """D9: the envelope codes this evaluated payload implies."""
        codes: set[LocalityLimitationCode] = set()
        complete = self.inventory.completeness is Completeness.COMPLETE
        if not complete:
            codes.add(LocalityLimitationCode.INVENTORY_INCOMPLETE)
        if self.comparison is not None and (
            self.comparison.completeness is not ComparisonCompleteness.COMPLETE
        ):
            codes.add(LocalityLimitationCode.COMPARISON_INCOMPLETE)
        # D10/D15 R4: an UNKNOWN selected *or compared* identity is not an established scope.
        scopes = [*(self.selection or ()), *(self.comparison.scopes if self.comparison else ())]
        if any(scope.evaluation is ScopeEvaluation.UNKNOWN for scope in scopes):
            codes.add(LocalityLimitationCode.SELECTION_NOT_ESTABLISHED)
        if any(locality.unresolved_owner_operations for locality in self.localities):
            codes.add(LocalityLimitationCode.PROVIDER_OWNER_UNRESOLVED)
        if complete and not self.localities:
            codes.add(LocalityLimitationCode.INSUFFICIENT_EVIDENCE)
        return codes


# --- Evidence payload (D11) ---------------------------------------------------------------------


class ScopedV2Record(BaseModel):
    """D11: the admitted public fields of one `ScopedObservedCallV2` (v2 contract §1, §3)."""

    model_config = _closed()

    id: str = Field(pattern=V2_EVIDENCE_ID_PATTERN)
    subject_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    object_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    environment: str = Field(min_length=1, max_length=128, pattern=ENVIRONMENT_PATTERN)
    bucket_utc_day: str = Field(pattern=_DAY_PATTERN)
    caller_cluster_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    caller_pod_uid: str = Field(pattern=_OPAQUE_ID_PATTERN)
    first_seen: datetime
    last_seen: datetime
    observation_count: int = Field(ge=1)
    correlation_mode: Literal["CLIENT_SERVER", "CLIENT_ONLY"]
    sample_trace_ids: list[_Token] = Field(min_length=1, max_length=5, json_schema_extra=_UNIQUE)
    key_rule_id: Literal["otel-calls-scoped-evidence-v2-key"]
    key_rule_version: Literal[1]
    normalization_rule_id: Literal["otel-client-caller-attribution"]
    normalization_rule_version: Literal[1]

    @field_validator("sample_trace_ids")
    @classmethod
    def _check_samples(cls, value: list[str]) -> list[str]:
        _check_sorted_unique_strings(value, "sample_trace_ids")
        return value

    @model_validator(mode="after")
    def _check_record(self) -> ScopedV2Record:
        if self.first_seen > self.last_seen:
            raise ValueError("first_seen must not be after last_seen")
        return self


def _evidence_entry_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `_check_entry` for external validators."""
    schema["allOf"] = [
        {
            "if": {"properties": {"status": {"const": "NOT_FOUND"}}},
            "then": {
                "properties": {
                    "ref_kind": {"type": "null"},
                    "scoped_record": {"type": "null"},
                    "capture_record": {"type": "null"},
                }
            },
        },
        {
            "if": {"properties": {"ref_kind": {"const": "SCOPED_V2"}}, "required": ["ref_kind"]},
            "then": {
                "properties": {
                    "status": {"const": "RESOLVED"},
                    "ref": {"pattern": V2_EVIDENCE_ID_PATTERN},
                    "scoped_record": {"not": {"type": "null"}},
                    "capture_record": {"type": "null"},
                }
            },
        },
        {
            "if": {
                "properties": {"ref_kind": {"enum": ["POD_CAPTURE", "OWNER_CAPTURE"]}},
                "required": ["ref_kind"],
            },
            "then": {
                "properties": {
                    "status": {"const": "RESOLVED"},
                    "ref": {"not": {"pattern": V2_EVIDENCE_ID_PATTERN}},
                    "scoped_record": {"type": "null"},
                    "capture_record": {
                        "not": {"type": "null"},
                        "properties": {"source_type": {"const": "KUBERNETES"}},
                    },
                }
            },
        },
        {
            "if": {"properties": {"status": {"const": "RESOLVED"}}},
            "then": {"properties": {"ref_kind": {"not": {"type": "null"}}}},
        },
    ]


class EvidenceEntry(BaseModel):
    """One requested ref (D11). A `NOT_FOUND` entry never says why."""

    model_config = _closed(json_schema_extra=_evidence_entry_schema_extra)

    ref: str = Field(pattern=_OPAQUE_ID_PATTERN)
    status: EvidenceRefStatus
    ref_kind: EvidenceRefKind | None
    scoped_record: ScopedV2Record | None
    capture_record: EvidenceRecord | None

    @model_validator(mode="after")
    def _check_entry(self) -> EvidenceEntry:
        if self.status is EvidenceRefStatus.NOT_FOUND:
            if (self.ref_kind, self.scoped_record, self.capture_record) != (None, None, None):
                raise ValueError("a NOT_FOUND entry carries no kind and no record")
            return self
        if self.ref_kind is EvidenceRefKind.SCOPED_V2:
            if self.scoped_record is None or self.capture_record is not None:
                raise ValueError("a SCOPED_V2 entry carries exactly a scoped_record")
            if self.scoped_record.id != self.ref:
                raise ValueError("scoped_record.id must equal ref")
            return self
        if self.ref_kind is None:
            raise ValueError("a RESOLVED entry has a ref_kind")
        if self.capture_record is None or self.scoped_record is not None:
            raise ValueError("a capture entry carries exactly a capture_record")
        if self.capture_record.id != self.ref:
            raise ValueError("capture_record.id must equal ref")
        if self.capture_record.source_type.value != "KUBERNETES":
            raise ValueError("a capture entry resolves Kubernetes evidence only")
        if self.ref.startswith("evidence:otel:calls-scoped:v2:"):
            raise ValueError("a v2-shaped ref is never a capture ref")
        return self


class ScopedLocalityEvidenceData(BaseModel):
    """D11: the `mode: "evidence"` payload."""

    model_config = _closed()

    subject_service_id: str = Field(pattern=_OPAQUE_ID_PATTERN)
    object_operation_id: str | None = Field(pattern=_OPAQUE_ID_PATTERN)
    entries: list[EvidenceEntry] = Field(
        min_length=1, max_length=MAX_EVIDENCE_REFS, json_schema_extra=_UNIQUE
    )

    @model_validator(mode="after")
    def _check_evidence_data(self) -> ScopedLocalityEvidenceData:
        _check_sorted_unique(self.entries, lambda entry: entry.ref, "entries")
        for entry in self.entries:
            record = entry.scoped_record
            if record is not None and (
                record.subject_id != self.subject_service_id
                or (
                    self.object_operation_id is not None
                    and record.object_id != self.object_operation_id
                )
            ):
                raise ValueError("a resolved v2 record must match the requested caller/Operation")
        return self

    def expected_limitation_codes(self) -> set[LocalityLimitationCode]:
        """D9/D16.1: any unresolved ref is INSUFFICIENT_EVIDENCE."""
        if all(entry.status is EvidenceRefStatus.RESOLVED for entry in self.entries):
            return set()
        return {LocalityLimitationCode.INSUFFICIENT_EVIDENCE}

    def any_resolved(self) -> bool:
        return any(entry.status is EvidenceRefStatus.RESOLVED for entry in self.entries)


# --- Envelope (D2, D9) --------------------------------------------------------------------------


class LocalityLimitation(BaseModel):
    """`reasons` carries the I2 `LOCALITY_*` codes behind the limitation, if any."""

    model_config = _closed(
        json_schema_extra={
            "allOf": [
                {
                    "if": {"properties": {"code": {"const": "UNSUPPORTED_REQUEST"}}},
                    "then": {
                        "properties": {
                            "reasons": {
                                "minItems": 1,
                                "items": {"enum": sorted(UNSUPPORTED_REQUEST_REASONS)},
                            }
                        }
                    },
                }
            ]
        }
    )

    code: LocalityLimitationCode
    message: str = Field(min_length=1)
    reasons: list[_Reason] = Field(default_factory=list, json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_limitation(self) -> LocalityLimitation:
        _check_sorted_unique_strings(self.reasons, "reasons")
        if self.code is LocalityLimitationCode.UNSUPPORTED_REQUEST and (
            not self.reasons or not set(self.reasons) <= UNSUPPORTED_REQUEST_REASONS
        ):
            raise ValueError(
                "UNSUPPORTED_REQUEST carries one or more LOCALITY_UNSUPPORTED_* reasons"
            )
        return self


def _codes_contain(*codes: LocalityLimitationCode) -> dict[str, Any]:
    return {
        "properties": {
            "limitations": {
                "contains": {"properties": {"code": {"enum": sorted(c.value for c in codes)}}}
            }
        },
        "required": ["limitations"],
    }


_REFUSAL_ENUM = sorted(code.value for code in REFUSAL_CODES)


def _locality_answer_schema_extra(schema: dict[str, Any], _model: type[BaseModel]) -> None:
    """Mirrors `LocalityAnswer._check_envelope` as far as JSON Schema can express it."""
    data_null = {"properties": {"data": {"type": "null"}}, "required": ["data"]}
    schema["allOf"] = [
        {
            "if": {"properties": {"mode": {"const": "query"}}, "required": ["mode"]},
            # Each payload is closed, so its required keys identify it without a `$ref`.
            "then": {
                "properties": {
                    "data": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "object", "required": ["request_context", "inventory"]},
                        ]
                    }
                }
            },
            "else": {
                "properties": {
                    "data": {
                        "anyOf": [
                            {"type": "null"},
                            {"type": "object", "required": ["entries"]},
                        ]
                    }
                }
            },
        },
        {
            "if": data_null,
            "then": {
                "properties": {
                    "outcome": {"const": "NOT_ANSWERED"},
                    "limitations": {
                        "minItems": 1,
                        "maxItems": 1,
                        "items": {"properties": {"code": {"enum": _REFUSAL_ENUM}}},
                    },
                }
            },
            "else": {
                "properties": {
                    "limitations": {
                        "items": {"properties": {"code": {"not": {"enum": _REFUSAL_ENUM}}}}
                    }
                }
            },
        },
        {
            "if": {"properties": {"outcome": {"const": "ANSWERED"}}, "required": ["outcome"]},
            "then": {"properties": {"limitations": {"maxItems": 0}}},
        },
        {
            "if": {"properties": {"outcome": {"const": "PARTIAL"}}, "required": ["outcome"]},
            "then": {"properties": {"limitations": {"minItems": 1}}},
        },
        {
            "if": {"properties": {"snapshot": {"type": "null"}}, "required": ["snapshot"]},
            "then": _codes_contain(LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE),
        },
        {
            "if": {
                "properties": {
                    "outcome": {"const": "NOT_ANSWERED"},
                    "data": {"not": {"type": "null"}},
                },
                "required": ["outcome", "data"],
            },
            "then": _codes_contain(LocalityLimitationCode.INSUFFICIENT_EVIDENCE),
        },
    ]


class LocalityAnswer(BaseModel):
    """The 0.6 envelope (D2, D9). `data` is null exactly for a refusal that evaluated nothing; an
    evaluated `NOT_ANSWERED` still carries its inventory or entries."""

    model_config = _closed(title="LocalityAnswer", json_schema_extra=_locality_answer_schema_extra)

    schema_version: LocalitySchemaVersion
    producer: Producer
    tool: LocalityToolName
    mode: LocalityMode
    outcome: Outcome
    snapshot: SnapshotRef | None
    data: ServiceDependenciesByLocalityData | ScopedLocalityEvidenceData | None
    limitations: list[LocalityLimitation] = Field(json_schema_extra=_UNIQUE)

    @model_validator(mode="after")
    def _check_envelope(self) -> LocalityAnswer:
        codes = [limitation.code for limitation in self.limitations]
        if [code.value for code in codes] != sorted({code.value for code in codes}):
            raise ValueError("limitations must be sorted by code, one per code")
        if self.snapshot is None and LocalityLimitationCode.SNAPSHOT_NOT_AVAILABLE not in codes:
            raise ValueError("snapshot may be null only with SNAPSHOT_NOT_AVAILABLE")
        if self.data is None:
            if self.outcome is not Outcome.NOT_ANSWERED or len(codes) != 1:
                raise ValueError(
                    "a null data is a NOT_ANSWERED refusal with exactly one limitation"
                )
            if codes[0] not in REFUSAL_CODES:
                raise ValueError("a null data carries a refusal code")
            return self
        expected_type = (
            ServiceDependenciesByLocalityData
            if self.mode == "query"
            else ScopedLocalityEvidenceData
        )
        if type(self.data) is not expected_type:
            raise ValueError(f"mode {self.mode!r} requires {expected_type.__name__} data")
        if self.snapshot is None:
            raise ValueError("an evaluated answer is bound to a snapshot")
        expected_codes = self.data.expected_limitation_codes()
        if set(codes) != expected_codes:
            raise ValueError(f"limitations must be exactly {sorted(expected_codes)} (D9)")
        self._check_outcome(expected_codes)
        if isinstance(self.data, ServiceDependenciesByLocalityData):
            cursor = self.data.inventory.next_cursor
            if (
                cursor is not None
                and decode_cursor(cursor).snapshot_id != self.snapshot.snapshot_id
            ):
                raise ValueError("next_cursor must be bound to the answer's snapshot (D5)")
        return self

    def _check_outcome(self, codes: Iterable[LocalityLimitationCode]) -> None:
        codes = set(codes)
        if isinstance(self.data, ScopedLocalityEvidenceData):
            expected = (
                Outcome.ANSWERED
                if not codes
                else Outcome.PARTIAL
                if self.data.any_resolved()
                else Outcome.NOT_ANSWERED
            )
        else:
            expected = (
                Outcome.NOT_ANSWERED
                if LocalityLimitationCode.INSUFFICIENT_EVIDENCE in codes
                else Outcome.PARTIAL
                if codes
                else Outcome.ANSWERED
            )
        if self.outcome is not expected:
            raise ValueError(f"outcome must be {expected.value} for these limitations (D9)")
