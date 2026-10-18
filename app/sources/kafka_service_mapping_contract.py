"""v0.7.1 I2.2: the Kafka consumer-group -> Service mapping artifact
(`aip-kafka-consumer-service-mapping/1`). Pure and dependency-free: no graph, no adapter, no Service
resolution (that happens per snapshot in the attribution projection). The shape and every rule
below are frozen by the I2.1 contract (`docs/specifications/0.7.1/i2-kafka-service-mapping-
contract.md`) and the independent vectors in `i2-vectors/mapping-rejections.json`.

Nothing here ever returns, logs or raises a source *value* or key name: validation reports a stable
code and, at most, a JSON index path.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.sources.model import KafkaServiceMappingSourceConfig

SCHEMA_ID = "aip-kafka-consumer-service-mapping/1"
MAX_ENTRIES = 10_000

# Rejection codes frozen by contract §4.
UNSUPPORTED_SCHEMA = "KSM_UNSUPPORTED_SCHEMA"
BROKER_MISMATCH = "KSM_BROKER_MISMATCH"
ENVIRONMENT_MISMATCH = "KSM_ENVIRONMENT_MISMATCH"
DUPLICATE_GROUP = "KSM_DUPLICATE_GROUP"
ARTIFACT_INVALID = "KSM_ARTIFACT_INVALID"
LIMIT_EXCEEDED = "KSM_LIMIT_EXCEEDED"
DUPLICATE_SOURCE = "KSM_DUPLICATE_SOURCE"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MappingEntry(_Strict):
    group_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    service_namespace: str | None = Field(default=None, min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _namespace_is_absent_or_a_string(cls, data: object) -> object:
        # Contract §3: every value is a non-empty string. An explicit null would mean the same as an
        # absent namespace but hash differently, so it is rejected rather than collapsed.
        if isinstance(data, Mapping) and data.get("service_namespace", "") is None:
            raise ValueError("service_namespace must be absent or a non-empty string")
        return data


class KafkaServiceMappingArtifact(_Strict):
    schema_: str = Field(alias="schema")
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    mappings: list[MappingEntry]


@dataclass(frozen=True)
class KafkaMappingProblem:
    """A stable rejection: the frozen code and, at most, a JSON index path - never a source value."""

    code: str
    subject: str | None = None


def _first_duplicate(values: Sequence[str]) -> str | None:
    return next((value for value, count in Counter(values).items() if count > 1), None)


def validate_mapping_document(document: object) -> KafkaMappingProblem | None:
    """The registration-independent checks (Q01, Q04-Q06, Q08's entry bound). `None` means the
    document is a well-formed artifact."""
    if not isinstance(document, Mapping):
        return KafkaMappingProblem(ARTIFACT_INVALID)
    if "schema" not in document:
        return KafkaMappingProblem(ARTIFACT_INVALID, "/schema")
    if document["schema"] != SCHEMA_ID:
        return KafkaMappingProblem(UNSUPPORTED_SCHEMA, "/schema")
    mappings = document.get("mappings")
    if isinstance(mappings, list) and len(mappings) > MAX_ENTRIES:
        return KafkaMappingProblem(LIMIT_EXCEEDED, "/mappings")
    try:
        artifact = KafkaServiceMappingArtifact.model_validate(document)
    except ValidationError as exc:
        first = exc.errors(include_input=False, include_url=False)[0]
        location = first["loc"]
        if first["type"] == "extra_forbidden":
            location = location[:-1]  # an unknown key's name is source content: report its parent
        return KafkaMappingProblem(ARTIFACT_INVALID, "/" + "/".join(str(part) for part in location))
    if _first_duplicate([entry.group_id for entry in artifact.mappings]) is not None:
        return KafkaMappingProblem(DUPLICATE_GROUP, "/mappings")
    return None


def check_against_registration(
    artifact: KafkaServiceMappingArtifact, config: KafkaServiceMappingSourceConfig
) -> KafkaMappingProblem | None:
    """Contract §3-§4 (Q02, Q03): the artifact names the registration's broker and environment."""
    if artifact.broker_id != config.broker_id:
        return KafkaMappingProblem(BROKER_MISMATCH, "/broker_id")
    if artifact.environment != config.environment:
        return KafkaMappingProblem(ENVIRONMENT_MISMATCH, "/environment")
    return None


def duplicate_registrations(configs: Sequence[KafkaServiceMappingSourceConfig]) -> frozenset[str]:
    """Contract §1 (Q09): every configured id used by more than one registration. All of those
    registrations are rejected; none commits. Distinct ids for one broker and environment are allowed:
    each is a separate evidence authority."""
    counts = Counter(config.id for config in configs)
    return frozenset(source_id for source_id, count in counts.items() if count > 1)
