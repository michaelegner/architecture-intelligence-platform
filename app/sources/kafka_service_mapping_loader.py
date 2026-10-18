"""v0.7.1 I2.2: the registration-bound loader for the Kafka Service-mapping artifact. Reads the one
file a registration names, validates it against the I2.1 contract and returns either the accepted
artifact or a stable rejection. It returns, logs and raises no source value."""

import hashlib
import json
from dataclasses import dataclass

from app.common.jcs import json_nesting_depth
from app.common.locators import confined_path
from app.sources.identity import kafka_service_mapping_source_revision
from app.sources.kafka_service_mapping_contract import (
    ARTIFACT_INVALID,
    LIMIT_EXCEEDED,
    KafkaMappingProblem,
    KafkaServiceMappingArtifact,
    check_against_registration,
    validate_mapping_document,
)
from app.sources.model import KafkaServiceMappingSourceConfig

MAX_ARTIFACT_BYTES = 1024 * 1024
MAX_NESTING = 64


@dataclass(frozen=True)
class LoadedMappingArtifact:
    artifact: KafkaServiceMappingArtifact
    content_sha256: str
    source_revision: str


@dataclass(frozen=True)
class RejectedMappingArtifact:
    problem: KafkaMappingProblem


def load_mapping_artifact(
    config: KafkaServiceMappingSourceConfig,
) -> LoadedMappingArtifact | RejectedMappingArtifact:
    """Contract §3-§4, in order: path inside the root (Q07), size (Q08), JSON (Q07), nesting (Q08),
    the document checks (Q01, Q04-Q06, Q08), then broker and environment (Q02, Q03)."""
    path = confined_path(config.root, config.artifact_relative_path)
    if path is None:
        return RejectedMappingArtifact(
            KafkaMappingProblem(ARTIFACT_INVALID, "/artifact_relative_path")
        )
    try:
        with path.open("rb") as handle:
            content = handle.read(MAX_ARTIFACT_BYTES + 1)
    except OSError:
        return RejectedMappingArtifact(KafkaMappingProblem(ARTIFACT_INVALID))
    if len(content) > MAX_ARTIFACT_BYTES:
        return RejectedMappingArtifact(KafkaMappingProblem(LIMIT_EXCEEDED))
    try:
        document = json.loads(content)
    except RecursionError:
        return RejectedMappingArtifact(KafkaMappingProblem(LIMIT_EXCEEDED))
    except ValueError:
        return RejectedMappingArtifact(KafkaMappingProblem(ARTIFACT_INVALID))
    if json_nesting_depth(document) > MAX_NESTING:
        return RejectedMappingArtifact(KafkaMappingProblem(LIMIT_EXCEEDED))
    problem = validate_mapping_document(document)
    if problem is not None:
        return RejectedMappingArtifact(problem)
    artifact = KafkaServiceMappingArtifact.model_validate(document)
    problem = check_against_registration(artifact, config)
    if problem is not None:
        return RejectedMappingArtifact(problem)
    content_sha256 = hashlib.sha256(content).hexdigest()
    return LoadedMappingArtifact(
        artifact=artifact,
        content_sha256=content_sha256,
        source_revision=kafka_service_mapping_source_revision(content_sha256),
    )
