from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


# The source types a *public* evidence answer may carry. `app.architecture_intelligence.contracts`
# types the frozen v0.5 evidence schema's `source_type` from this enum.
#
# KUBERNETES and CONFIGURATION were added in v0.5.0 I3 (spec §16.1): I2 Draft 0.2 §9 kept ALL
# Kubernetes evidence off every public surface with no exception. I3 narrows that boundary rather
# than removing it - a Kubernetes/configuration-mapping evidence record becomes publicly reachable
# only when the current snapshot makes it reachable from a public DEPLOYED_AS claim or
# DeploymentResolution (I3 spec §16.2's exact reachability gate); every other Kubernetes evidence
# record remains exactly as internal as I2 left it. This enum widening reflects that a public
# payload CAN now carry these values under that gate - it does not itself relax the gate, which is
# enforced elsewhere (I3's reconciliation/exposure layer, not this type definition). The internal
# Kubernetes source-type value lives at `app.canonical.infrastructure.KUBERNETES_SOURCE_TYPE`; the
# configuration-mapping source type has no internal-module constant of its own yet since I3's
# mapping-artifact evidence lands in a later slice.
#
# Kept as a comment rather than a class docstring on purpose: Pydantic exports a model/enum
# docstring as the generated JSON Schema's `description`, so writing this as a docstring would
# itself change the frozen public schema (caught by tests/unit/test_architecture_intelligence_
# schema_frozen.py).
class SourceType(StrEnum):
    OPENAPI = "OPENAPI"
    ASYNCAPI = "ASYNCAPI"
    MANIFEST = "MANIFEST"
    OPENTELEMETRY = "OPENTELEMETRY"
    KUBERNETES = "KUBERNETES"
    CONFIGURATION = "CONFIGURATION"


class EvidenceType(StrEnum):
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"


class Provenance(BaseModel):
    id: str
    source_type: str  # OPENAPI | ASYNCAPI | MANIFEST | OPENTELEMETRY
    source_file: str
    source_revision: str | None = None
    evidence_type: str = "DECLARED"


class ObservedEvidence(Provenance):
    """A single-observation evidence seed (spec §16) - a degenerate bucket-of-one produced by a
    resolver (e.g. app.telemetry.adapter). The Aggregator (H4 Iteration 11E) merges many seeds for
    the same bucket into the real persisted, time-bounded evidence (summing observation_count,
    expanding first_seen/last_seen, capping sample_trace_ids at 5)."""

    source_type: str = SourceType.OPENTELEMETRY
    source_file: str = "opentelemetry"
    evidence_type: str = EvidenceType.OBSERVED

    environment: str
    bucket_start: datetime
    bucket_end: datetime
    first_seen: datetime
    last_seen: datetime
    observation_count: int
    sample_trace_ids: list[str] = Field(default_factory=list)
    service_version: str | None = None
    # How this evidence was derived (11H R3/spec §14 - see app.telemetry.model.CorrelationMode for
    # the allowed values). Optional so pre-11H-C construction sites keep working unmodified.
    correlation_mode: str | None = None
