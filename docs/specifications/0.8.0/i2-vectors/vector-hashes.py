"""v0.8 I2 §2: known-answer ids of the promise record for the I1 package, hashlib only.

The natural keys are written by hand from I1 §5.2 and the lookup of I1 §5.3, not read from AIP.
`ld` is the 8-byte big-endian length + UTF-8 bytes per part encoding (v0.7.1 I1 contract §2).
Writes ids.json next to this script.
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / "i1-evidence"
CONFIGURED_SOURCE_ID = "sokol111-catalog"
ENVIRONMENT = "local"

T, C, I, PQ = (
    f"ecommerce-{name}-service" for name in ("tenant", "catalog", "image", "product-query")
)
CQ = "ecommerce-category-query-service"
PROMISES = [
    (T, "SENDS", "TenantUpdated"),
    (C, "SENDS", "ProductEvents"),
    (C, "SENDS", "CategoryEvents"),
    (C, "SENDS", "ProductUpdated"),
    (I, "SENDS", "ProductImagePromoted"),
    (I, "RECEIVES", "ProductUpdated"),
    (PQ, "RECEIVES", "ProductUpdated"),
    (PQ, "RECEIVES", "ProductImagePromoted"),
]
MEMBERSHIPS = [
    ("store-provisioning", T),
    ("catalog-management", C),
    ("catalog-management", I),
    ("storefront", PQ),
    ("storefront", CQ),
]
EVENTS = [
    "TenantUpdated",
    "ProductEvents",
    "CategoryEvents",
    "ProductUpdated",
    "ProductImagePromoted",
]


def ld(*parts: str) -> bytes:
    return b"".join(len(p.encode()).to_bytes(8, "big") + p.encode() for p in parts)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


source = f"urn:aip:source:event-catalog:{sha(ld(CONFIGURED_SOURCE_ID, ENVIRONMENT))}"
catalog_digest = sha((PACKAGE / "catalog.SHA256SUMS").read_bytes())
lookup_digest = sha((PACKAGE / "event-topic-lookup.json").read_bytes())
ids = {
    "configured_source_id": CONFIGURED_SOURCE_ID,
    "environment": ENVIRONMENT,
    "source_instance_id": source,
    "evidence_id": f"catalog-evidence:owned:{sha(ld(source))}",
    "source_revision": f"catalog-sha256:{catalog_digest}+lookup-sha256:{lookup_digest}",
    "promises": {
        f"{s}|{d}|{e}": f"catalog-promise:owned:{sha(ld(source, s, d, e))}" for s, d, e in PROMISES
    },
    "memberships": {
        f"{b}|{s}": f"catalog-membership:owned:{sha(ld(source, b, s))}" for b, s in MEMBERSHIPS
    },
    "event_topics": {e: f"catalog-event-topic:owned:{sha(ld(source, e))}" for e in EVENTS},
}
(HERE / "ids.json").write_text(json.dumps(ids, indent=2, sort_keys=True) + "\n")
