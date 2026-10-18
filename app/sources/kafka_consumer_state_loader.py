"""v0.7.1 I1.2: the registration-bound loader. Reads the one normalized capture file a registration
names, validates it against the I1.1 contract and returns either the accepted capture or a stable
rejection. Offline only: it never contacts Kafka and returns, logs and raises no source value.
Wiring into discovery/import and any persistence is I1.3."""

import hashlib
import json
from collections.abc import Collection
from dataclasses import dataclass

from app.common.jcs import json_nesting_depth
from app.common.locators import confined_path
from app.sources.kafka_consumer_state_contract import (
    CAPTURE_INVALID,
    KafkaCaptureProblem,
    KafkaConsumerStateEnvelope,
    check_against_registration,
    validate_capture_document,
)
from app.sources.model import KafkaConsumerStateSourceConfig

MAX_CAPTURE_BYTES = 8 * 1024 * 1024
MAX_NESTING = 64


@dataclass(frozen=True)
class LoadedKafkaCapture:
    envelope: KafkaConsumerStateEnvelope
    content_sha256: str
    source_revision: str


@dataclass(frozen=True)
class RejectedKafkaCapture:
    problem: KafkaCaptureProblem


def load_capture(
    config: KafkaConsumerStateSourceConfig, *, forbidden_values: Collection[str] = ()
) -> LoadedKafkaCapture | RejectedKafkaCapture:
    path = confined_path(config.root, config.capture_relative_path)
    if path is None:
        return RejectedKafkaCapture(KafkaCaptureProblem(CAPTURE_INVALID, "/capture_relative_path"))
    try:
        with path.open("rb") as handle:
            content = handle.read(MAX_CAPTURE_BYTES + 1)
    except OSError:
        return RejectedKafkaCapture(KafkaCaptureProblem(CAPTURE_INVALID))
    if len(content) > MAX_CAPTURE_BYTES:
        return RejectedKafkaCapture(KafkaCaptureProblem(CAPTURE_INVALID))
    try:
        document = json.loads(content)
    except (ValueError, RecursionError):
        return RejectedKafkaCapture(KafkaCaptureProblem(CAPTURE_INVALID))
    if json_nesting_depth(document) > MAX_NESTING:
        return RejectedKafkaCapture(KafkaCaptureProblem(CAPTURE_INVALID))
    problem = validate_capture_document(document, forbidden_values)
    if problem is not None:
        return RejectedKafkaCapture(problem)
    envelope = KafkaConsumerStateEnvelope.model_validate(document)
    problem = check_against_registration(envelope, config)
    if problem is not None:
        return RejectedKafkaCapture(problem)
    return LoadedKafkaCapture(
        envelope=envelope,
        content_sha256=hashlib.sha256(content).hexdigest(),
        source_revision=envelope.source_revision,
    )
