"""Standalone known-answer generator for ids.json. Uses only hashlib; imports nothing from app.

ld(*parts) = for each part: 8-byte big-endian UTF-8 byte length, then the UTF-8 bytes.
Run: python3 vector-hashes.py   (prints the object that must equal ids.json["vectors"])
"""

import hashlib
import json
import unicodedata


def ld(*parts: str) -> bytes:
    out = b""
    for p in parts:
        b = p.encode("utf-8")
        out += len(b).to_bytes(8, "big") + b
    return out


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def scope_digest(groups: list[str]) -> str:
    return sha(ld(*sorted(groups)))


def source_instance(source_id: str, broker: str, env: str, groups: list[str]) -> str:
    return "urn:aip:source:kafka-consumer-state:" + sha(
        ld(source_id, broker, env, scope_digest(groups))
    )


def consumer(broker: str, env: str, group: str) -> str:
    return "consumer:" + sha(ld("kafka_consumer_state", broker, env, group))


def topic(broker: str, topic_name: str) -> str:
    return "topic:owned:" + sha(ld(broker, "", unicodedata.normalize("NFC", topic_name)))


def attachment(consumer_id: str, topic_id: str) -> str:
    return "kafka-attachment:owned:" + sha(ld(consumer_id, topic_id))


B, E = "kafka:cluster-a", "prod"
G = ["payment-service", "order-service"]
c_pay = consumer(B, E, "payment-service")
t_orders = topic(B, "orders.created")
vectors = {
    "K01_scope_digest": scope_digest(G),
    "K02_scope_digest_order_independent": scope_digest(list(reversed(G))),
    "K03_source_instance": source_instance("kafka-prod", B, E, G),
    "K04_source_instance_other_scope": source_instance("kafka-prod", B, E, ["payment-service"]),
    "K05_consumer_payment": c_pay,
    "K06_consumer_other_environment": consumer(B, "staging", "payment-service"),
    "K07_consumer_other_broker": consumer("kafka:cluster-b", E, "payment-service"),
    "K08_consumer_order": consumer(B, E, "order-service"),
    "K09_topic_orders_created": t_orders,
    "K10_attachment_payment_orders": attachment(c_pay, t_orders),
    "K11_consumer_groupid_verbatim_case": consumer(B, E, "Payment-Service"),
    "K12_topic_nfc_composed": topic(B, "caf\u00e9"),
    "K13_topic_nfc_decomposed_equal": topic(B, "cafe\u0301"),
}
print(json.dumps(vectors, indent=2))
