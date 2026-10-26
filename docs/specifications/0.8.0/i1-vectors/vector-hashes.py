"""v0.8 I1 spec §6: known-answer Topic ids for the four Sokol111 topics on both brokers.

hashlib only, independent of `app`: topic:owned:<sha256(ld(broker id, "", topic))>, where ld is
the 8-byte big-endian length + UTF-8 bytes per part (v0.7.1 I1 contract §2, K09). Writes ids.json
next to this script.
"""

import hashlib
import json
from pathlib import Path

BROKERS = ("kafka:sokol111-local", "kafka:sokol111-kafka")
TOPICS = (
    "catalog.attribute.events",
    "catalog.category.events",
    "catalog.product.events",
    "tenant.tenant.events",
)


def ld(*parts: str) -> bytes:
    return b"".join(len(p.encode()).to_bytes(8, "big") + p.encode() for p in parts)


ids = {
    broker: {
        topic: f"topic:owned:{hashlib.sha256(ld(broker, '', topic)).hexdigest()}"
        for topic in TOPICS
    }
    for broker in BROKERS
}
Path(__file__).with_name("ids.json").write_text(json.dumps(ids, indent=2, sort_keys=True) + "\n")
