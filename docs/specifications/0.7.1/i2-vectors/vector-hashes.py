"""Standalone known-answer generator for ids.json. Uses only hashlib; imports nothing from app.

ld(*parts) = for each part: 8-byte big-endian UTF-8 byte length, then the UTF-8 bytes.
Run: python3 vector-hashes.py   (prints the object that must equal ids.json["vectors"])
"""

import hashlib
import json


def ld(*parts: str) -> bytes:
    out = b""
    for p in parts:
        b = p.encode("utf-8")
        out += len(b).to_bytes(8, "big") + b
    return out


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_instance(source_id: str, broker: str, env: str) -> str:
    return "urn:aip:source:kafka-service-mapping:" + sha(ld(source_id, broker, env))


def entry(source_instance_id: str, group: str) -> str:
    return "kafka-service-mapping:owned:" + sha(ld(source_instance_id, group))


def evidence(source_instance_id: str) -> str:
    return "kafka-service-mapping-evidence:owned:" + sha(ld(source_instance_id))


def consumer(broker: str, env: str, group: str) -> str:
    # The I1 consumer identity (v0.7.1 I1.1 K05): the join key, not a new identity.
    return "consumer:" + sha(ld("kafka_consumer_state", broker, env, group))


B, E = "kafka:cluster-a", "prod"
s_a = source_instance("map-a", B, E)
vectors = {
    "M01_source_instance_map_a": s_a,
    "M02_source_instance_map_b": source_instance("map-b", B, E),
    "M03_source_instance_other_environment": source_instance("map-a", B, "staging"),
    "M04_entry_map_a_payment": entry(s_a, "payment-service"),
    "M05_entry_map_a_order": entry(s_a, "order-service"),
    "M06_evidence_map_a": evidence(s_a),
    "M07_join_key_payment_equals_i1_k05": consumer(B, E, "payment-service"),
    "M08_join_key_case_is_exact": consumer(B, E, "Payment-Service"),
    "M09_source_revision_example": "artifact-sha256:" + sha(b"example"),
}
print(json.dumps(vectors, indent=2))
