"""v0.7.1 I2.2 internal, source-owned Kafka Service-mapping carriers (I2.1 contract §5) - never public
canonical entities, never NL/MCP-visible, never relationships to a public entity. Ids follow the
independent vectors M04-M06 in `docs/specifications/0.7.1/i2-vectors/ids.json`.

An entry stores the mapping exactly as written: the Service is resolved per snapshot in the
attribution projection, never here, so no Service and no `KafkaConsumerGroup` is ever created from a
mapping. `consumer_id` is the I1 consumer identity (vector M07 = K05), the join key to attachments.
"""

from pydantic import BaseModel, Field

KAFKA_SERVICE_MAPPING_ENTRY_LABEL = "KafkaServiceMappingEntry"
KAFKA_SERVICE_MAPPING_EVIDENCE_LABEL = "KafkaServiceMappingEvidence"


class KafkaServiceMappingEntry(BaseModel):
    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    group_id: str = Field(min_length=1)
    consumer_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    service_namespace: str | None = None
    evidence_ids: list[str] = Field(min_length=1)


class KafkaServiceMappingEvidence(BaseModel):
    id: str = Field(min_length=1)
    source_instance_id: str = Field(min_length=1)
    # The registration that produced this source, so retirement can protect a still-configured
    # registration whose replacement did not commit.
    configured_source_id: str = Field(min_length=1)
    broker_id: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    artifact_sha256: str = Field(min_length=64, max_length=64)
    source_revision: str = Field(min_length=1)
