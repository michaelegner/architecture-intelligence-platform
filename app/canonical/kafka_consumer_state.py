"""v0.7.1 I1.3 internal, source-owned Kafka consumer-state carriers (I1.1 contract §6) - never public
canonical entities, never NL/MCP-visible, never relationships to a public entity. Ids follow the
independent vectors K05 and K10 in `docs/specifications/0.7.1/i1-vectors/ids.json`; the capture
evidence id is `kafka-capture:owned:<sha256(ld(source instance id))>`.

Like the gateway evidence, the capture evidence is a dedicated carrier, not a `Provenance`: a
`Provenance` is written as an `:Evidence` node, which the public evidence reads treat as publicly
reachable. Public exposure is I3's decision. No member id, client id, host or partition is a
canonical identity; they live only in `support_json` / `group_states_json`, as evidence detail.
"""

from pydantic import BaseModel, Field

from app.common.encoding import length_delimited, sha256_hex, utf8

KAFKA_CONSUMER_GROUP_LABEL = "KafkaConsumerGroup"
KAFKA_CONSUMER_ATTACHMENT_LABEL = "KafkaConsumerAttachment"
KAFKA_CAPTURE_EVIDENCE_LABEL = "KafkaCaptureEvidence"


def kafka_capture_evidence_id(source_instance_id: str) -> str:
    """One evidence carrier per source instance: the last accepted capture of that source."""
    return f"kafka-capture:owned:{sha256_hex(length_delimited(utf8(source_instance_id)))}"


class KafkaConsumerGroup(BaseModel):
    """The broker-native consumer identity (I0 D1): one per allow-listed group, whatever its state.
    It is not a Subscription and not a Service."""

    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)


class KafkaConsumerAttachment(BaseModel):
    """Consumer identity G is attached to already-declared Topic D at capture time T. It does not
    mean a message was processed."""

    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    topic_id: str = Field(min_length=1)
    captured_at: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    # RFC 8785 canonical JSON of the members and partitions that support this attachment (Neo4j
    # cannot hold a nested map). Evidence detail only.
    support_json: str = "[]"


class KafkaCaptureEvidence(BaseModel):
    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    captured_at: str = Field(min_length=1)
    capture_content_sha256: str = Field(min_length=64, max_length=64)
    scope_digest: str = Field(min_length=64, max_length=64)
    source_revision: str = Field(min_length=1)
    # RFC 8785 canonical JSON of `{group id: state}` for every described group, so "zero live
    # attachment at T" is explicit evidence and never inferred from absence.
    group_states_json: str = "{}"
    evidence_type: str = Field(default="OBSERVED", pattern=r"^OBSERVED$")
