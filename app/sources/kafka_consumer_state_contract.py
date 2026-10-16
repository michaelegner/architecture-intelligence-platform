"""v0.7.1 I1.2: the Kafka consumer-state capture envelope (`aip-kafka-consumer-state/1`) shared by
the separate capture step (`app.kafka_capture`, which writes it) and the registration-bound loader
(which validates it). Pure and dependency-free: no Kafka client, no graph, no adapter. The shape and
every rule below are frozen by the I1.1 contract (`docs/specifications/0.7.1/i1-kafka-source-
contract.md`) and the independent vectors in `i1-vectors/capture-rejections.json`.

Nothing here ever returns, logs or raises a source *value*: validation reports a stable code and, at
most, the JSON path of an offending field.
"""

import re
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.sources.model import KafkaConsumerStateSourceConfig

SCHEMA_ID = "aip-kafka-consumer-state/1"

# The only group readings that make a capture usable (contract §4). Anything else is a transitional
# or unknown state and rejects the whole capture.
STABLE = "Stable"
EMPTY = "Empty"
DEAD = "Dead"
ACCEPTED_STATES = frozenset({STABLE, EMPTY, DEAD})

# Rejection codes frozen by contract §8.
BROKER_MISMATCH = "KAFKA_BROKER_MISMATCH"
ENVIRONMENT_MISMATCH = "KAFKA_ENVIRONMENT_MISMATCH"
SCOPE_MISMATCH = "KAFKA_SCOPE_MISMATCH"
GROUP_NOT_DESCRIBED = "KAFKA_GROUP_NOT_DESCRIBED"
STATE_NOT_STABLE = "KAFKA_STATE_NOT_STABLE"
CAPTURE_INCOMPLETE = "KAFKA_CAPTURE_INCOMPLETE"
CAPTURE_UNREDACTED = "KAFKA_CAPTURE_UNREDACTED"
CAPTURE_INVALID = "KAFKA_CAPTURE_INVALID"
UNSUPPORTED_SCHEMA = "KAFKA_UNSUPPORTED_SCHEMA"
DUPLICATE_SOURCE = "KAFKA_DUPLICATE_SOURCE"

# Substrings that mark a credential or security property. Matched case-insensitively against every
# object *key* at any depth (never against values: a group may legitimately be named "token-service").
_SECRET_KEY_MARKERS = (
    "password",
    "passwd",
    "secret",
    "token",
    "credential",
    "jaas",
    "sasl",
    "ssl.",
    "apikey",
    "api_key",
    "private_key",
    "authorization",
)

REDACTED_KEY = "<redacted-key>"

_RFC3339_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class CaptureAssignment(_Strict):
    topic: str = Field(min_length=1)
    partitions: list[int]


class CaptureMember(_Strict):
    member_id: str
    client_id: str
    host: str
    assignments: list[CaptureAssignment]


class CaptureGroup(_Strict):
    group_id: str = Field(min_length=1)
    # `None` only with `error`: a group the utility could not read (an acquisition failure), which
    # makes the whole capture incomplete. A broker-reported reading is always a state string.
    state: str | None = None
    error: str | None = None
    members: list[CaptureMember] = Field(default_factory=list)


class KafkaConsumerStateEnvelope(_Strict):
    schema_: str = Field(alias="schema")
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    captured_at: str
    tool_version: str = Field(min_length=1)
    kafka_version: str = Field(min_length=1)
    complete: bool
    group_scope: list[str]
    groups: list[CaptureGroup]

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, populate_by_name=True)

    @property
    def source_revision(self) -> str:
        """Contract §4: `kafka:<kafka_version>+capture:<captured_at>`."""
        return source_revision(self.kafka_version, self.captured_at)


def source_revision(kafka_version: str, captured_at: str) -> str:
    return f"kafka:{kafka_version}+capture:{captured_at}"


@dataclass(frozen=True)
class KafkaCaptureProblem:
    """A stable rejection: the frozen code and, at most, a JSON path - never a source value."""

    code: str
    subject: str | None = None


def unredacted_secret_paths(document: object, forbidden_values: Collection[str] = ()) -> list[str]:
    """JSON paths (never values, and never the name of an offending key) of everything a redacted capture must not contain: an object key
    that names a credential or security property, or a string (key or value) that contains one of
    the `forbidden_values`. A secret's value cannot be recognized by shape, so the value check only
    covers the secret values the caller knows (for example the capture client's own settings, or a
    canary); it is the caller's job to supply them."""
    forbidden = [value for value in forbidden_values if value]
    found: list[str] = []

    def leaks(text: str) -> bool:
        return any(value in text for value in forbidden)

    def walk(node: object, path: str) -> None:
        if isinstance(node, Mapping):
            for name, child in node.items():
                lowered = str(name).lower()
                if any(marker in lowered for marker in _SECRET_KEY_MARKERS) or leaks(str(name)):
                    # The key itself may carry the secret, so it is never part of a reported path.
                    found.append(f"{path}/{REDACTED_KEY}")
                    continue
                walk(child, f"{path}/{name}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}/{index}")
        elif isinstance(node, str) and leaks(node):
            found.append(path)

    walk(document, "")
    return sorted(set(found))


def _first_duplicate(values: Sequence[str]) -> str | None:
    return next((value for value, count in Counter(values).items() if count > 1), None)


def _captured_at_is_rfc3339_utc(value: str) -> bool:
    if not _RFC3339_UTC.match(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_capture_document(
    document: object, forbidden_values: Collection[str] = ()
) -> KafkaCaptureProblem | None:
    """The registration-independent checks, in the order the I1.1 vectors require: schema (R11),
    unredacted secrets (R09), structure (R10), duplicates (R13). `None` means acceptable."""
    if not isinstance(document, Mapping):
        return KafkaCaptureProblem(CAPTURE_INVALID)
    if "schema" not in document:
        return KafkaCaptureProblem(CAPTURE_INVALID, "/schema")
    if document["schema"] != SCHEMA_ID:
        return KafkaCaptureProblem(UNSUPPORTED_SCHEMA, "/schema")
    secret_paths = unredacted_secret_paths(document, forbidden_values)
    if secret_paths:
        return KafkaCaptureProblem(CAPTURE_UNREDACTED, secret_paths[0])
    try:
        envelope = KafkaConsumerStateEnvelope.model_validate(document)
    except ValidationError as exc:
        first = exc.errors(include_input=False, include_url=False)[0]
        location = first["loc"]
        if first["type"] == "extra_forbidden":
            location = location[:-1]  # an unknown key's name is source content: report its parent
        return KafkaCaptureProblem(CAPTURE_INVALID, "/" + "/".join(str(part) for part in location))
    if not _captured_at_is_rfc3339_utc(envelope.captured_at):
        return KafkaCaptureProblem(CAPTURE_INVALID, "/captured_at")
    if _first_duplicate(envelope.group_scope) is not None:
        return KafkaCaptureProblem(CAPTURE_INVALID, "/group_scope")
    if _first_duplicate([group.group_id for group in envelope.groups]) is not None:
        return KafkaCaptureProblem(CAPTURE_INVALID, "/groups")
    return None


def check_against_registration(
    envelope: KafkaConsumerStateEnvelope, config: KafkaConsumerStateSourceConfig
) -> KafkaCaptureProblem | None:
    """Contract §4: the registration-bound acceptance rules, in order. `None` means the capture is
    complete and accepted for this source."""
    if envelope.broker_id != config.broker_id:
        return KafkaCaptureProblem(BROKER_MISMATCH, "/broker_id")
    if envelope.environment != config.environment:
        return KafkaCaptureProblem(ENVIRONMENT_MISMATCH, "/environment")
    allow_list = set(config.consumer_groups)
    if set(envelope.group_scope) != allow_list:
        return KafkaCaptureProblem(SCOPE_MISMATCH, "/group_scope")
    described = {group.group_id for group in envelope.groups}
    if not described <= allow_list:
        return KafkaCaptureProblem(SCOPE_MISMATCH, "/groups")
    if described != allow_list:
        return KafkaCaptureProblem(GROUP_NOT_DESCRIBED, "/groups")
    if envelope.complete is not True:
        return KafkaCaptureProblem(CAPTURE_INCOMPLETE, "/complete")
    for index, group in enumerate(envelope.groups):
        if group.error is not None:
            return KafkaCaptureProblem(CAPTURE_INCOMPLETE, f"/groups/{index}/error")
        if group.state not in ACCEPTED_STATES:
            return KafkaCaptureProblem(STATE_NOT_STABLE, f"/groups/{index}/state")
    return None


def duplicate_registrations(
    configs: Sequence[KafkaConsumerStateSourceConfig],
) -> frozenset[str]:
    """Contract §1 (R12): ids of every registration that shares a `broker_id` and `environment` with
    another and also shares at least one allow-listed group. All of them are rejected; none commits."""
    conflicting: set[str] = set()
    for index, first in enumerate(configs):
        for second in configs[index + 1 :]:
            if (
                first.broker_id == second.broker_id
                and first.environment == second.environment
                and set(first.consumer_groups) & set(second.consumer_groups)
            ):
                conflicting.update((first.id, second.id))
    return frozenset(conflicting)
