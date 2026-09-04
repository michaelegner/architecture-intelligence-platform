"""v0.4.0 I1.3 - the `get_service_dependencies` request shape (spec §8.1).

`ObservationContextInput` is deliberately distinct from `app.architecture_intelligence.contracts.
ObservationContextRef`: it represents what a caller actually supplies, which may be entirely absent
or incomplete - the semantic boundary needs that shape to construct as a valid request (spec §8.1)
so it can return the required `NOT_ANSWERED / OBSERVATION_CONTEXT_REQUIRED` result instead of an
input-schema error. Malformed *values* inside a supplied context (bad offset, reversed window,
excessive window, invalid environment) remain input-schema errors - those are rejected by
`app.architecture_intelligence.observation_context.build_observation_context_ref`, which reuses
`ObservationContextRef`'s own validators, not duplicated here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.architecture_intelligence.contracts import _SNAPSHOT_ID_PATTERN

_SERVICE_ID_PATTERN = r"^service:"
_MAX_SERVICE_ID_LENGTH = 512


class ObservationContextInput(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    environment: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None

    @property
    def is_complete(self) -> bool:
        return (
            self.environment is not None
            and self.window_start is not None
            and self.window_end is not None
        )


class ServiceDependenciesRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    service_id: str = Field(
        min_length=1, max_length=_MAX_SERVICE_ID_LENGTH, pattern=_SERVICE_ID_PATTERN
    )
    observation_context: ObservationContextInput | None = None
    snapshot_id: str | None = Field(default=None, pattern=_SNAPSHOT_ID_PATTERN)


class EvidenceRequest(BaseModel):
    """v0.4.0 I2.1 - the `get_evidence` request shape (spec §11.1). Unlike
    `ServiceDependenciesRequest`, `snapshot_id` is required here - `get_evidence` never defaults to
    the current snapshot, and there is no observation-context input at all."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_refs: list[str] = Field(
        min_length=1, max_length=20, json_schema_extra={"uniqueItems": True}
    )
    snapshot_id: str = Field(pattern=_SNAPSHOT_ID_PATTERN)

    @field_validator("evidence_refs")
    @classmethod
    def _check_deduplicated(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must not contain duplicates")
        return value
