"""v0.8 I1 spec §6: the known-answer Topic ids of both Sokol111 brokers.

`ids.json` was written by the hashlib-only `vector-hashes.py`; the spec table and the production
derivation must both agree with it.
"""

import json
import re
from pathlib import Path

from app.sources.owner_ids import topic_owned_id

REPO = Path(__file__).resolve().parents[2]
SPEC = REPO / "docs/specifications/0.8.0/i1-declared-side-and-inventory.md"
IDS = json.loads((REPO / "docs/specifications/0.8.0/i1-vectors/ids.json").read_text())
BROKERS = ("kafka:sokol111-local", "kafka:sokol111-kafka")


def test_the_vectors_equal_the_production_derivation() -> None:
    assert sorted(IDS) == sorted(BROKERS)
    for broker, topics in IDS.items():
        assert len(topics) == 4
        for name, topic_id in topics.items():
            assert topic_id == topic_owned_id(
                stable_broker_id=broker,
                normalized_namespace_or_empty="",
                exact_topic_address=name,
            )


def test_the_vectors_equal_the_specification_table() -> None:
    rows = re.findall(
        r"^\| `([a-z.]+)` \| `(topic:owned:[0-9a-f]{64})` \| `(topic:owned:[0-9a-f]{64})` \|$",
        SPEC.read_text(),
        flags=re.MULTILINE,
    )
    assert {name: (local, kafka) for name, local, kafka in rows} == {
        name: (IDS[BROKERS[0]][name], IDS[BROKERS[1]][name]) for name in IDS[BROKERS[0]]
    }
