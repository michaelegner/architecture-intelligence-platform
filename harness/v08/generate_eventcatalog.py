"""v0.8 I1 spec §5.4: generate the showcase EventCatalog and the event -> Topic lookup from the two
Sokol111 architecture documents at workspace commit f6b4c1c, by the fixed rule of the v0.8
specification §3.1. Standard library only.

    python harness/v08/generate_eventcatalog.py <upstream dir> <package dir>

Writes `catalog/`, `event-topic-lookup.json` and `catalog.SHA256SUMS` into the package directory
and prints the catalog digest. Every input check runs before anything is written.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

UPSTREAM_SHA256 = {
    "platform-overview.md": "b0c88221781fe6b18295c4e78c7d9e684fd043e238d2eb9621dc5be27b4b226a",
    "product-update-flow.md": "312910e8b917dffe43fe41455b5f312ffbdb8b62d4aa1f9283111f7807ada9b2",
}
VERSION = "1.0.0"

TENANT = "ecommerce-tenant-service"
CATALOG = "ecommerce-catalog-service"
IMAGE = "ecommerce-image-service"
PRODUCT_QUERY = "ecommerce-product-query-service"
CATEGORY_QUERY = "ecommerce-category-query-service"

# Spec §5.4 fixed tables.
NODE_SERVICES = {
    "tenant": (TENANT,),
    "catalog": (CATALOG,),
    "Catalog": (CATALOG,),
    "images": (IMAGE,),
    "Image": (IMAGE,),
    "readModels": (PRODUCT_QUERY, CATEGORY_QUERY),
    "ProductQuery": (PRODUCT_QUERY,),
}
BROKER_NODES = {"broker", "Events"}
LABEL_EVENTS = {
    "TenantUpdated event": ("TenantUpdated",),
    "Product and category events": ("ProductEvents", "CategoryEvents"),
    "ProductUpdated event": ("ProductUpdated",),
    "ProductImagePromoted event": ("ProductImagePromoted",),
    "image promotion event": ("ProductImagePromoted",),
}
NON_EVENT_LABELS = {"build projections"}
SEQUENCE_PREFIXES = ("Publish ", "Consume ")

SERVICES = {
    TENANT: "Tenant Service",
    CATALOG: "Catalog Service",
    IMAGE: "Image Service",
    PRODUCT_QUERY: "Product Query Service",
    CATEGORY_QUERY: "Category Query Service",
}
# (domain id, name, owner team id, team name, member services) - parent §3.1 rule 1.
DOMAINS = (
    ("catalog-management", "Catalog Management", "catalog-team", "Catalog Team", (CATALOG, IMAGE)),
    (
        "store-provisioning",
        "Store Provisioning",
        "provisioning-team",
        "Provisioning Team",
        (TENANT,),
    ),
    (
        "storefront",
        "Storefront",
        "storefront-team",
        "Storefront Team",
        (PRODUCT_QUERY, CATEGORY_QUERY),
    ),
)
EVENTS = {
    "TenantUpdated": "Event type TenantUpdated.",
    "ProductEvents": "Stands for the family of product event types (label 'Product and category events').",
    "CategoryEvents": "Stands for the family of category event types (label 'Product and category events').",
    "ProductUpdated": "Event type ProductUpdated.",
    "ProductImagePromoted": "Event type ProductImagePromoted.",
}
_API = {
    "tenant": ("Sokol111/ecommerce-tenant-service-api", "d9b90972f77b6a2df7ebee0f52e0cd8124937fe7"),
    "catalog": (
        "Sokol111/ecommerce-catalog-service-api",
        "7cecb3e1131dbd5199ce25e9cf101d75d3365171",
    ),
    "image": ("Sokol111/ecommerce-image-service-api", "2167948573ced4b2854d8aed93fb83b242cf2e7f"),
}
# Spec §5.3: event -> (topic, *-service-api whose topics.go maps it).
LOOKUP = {
    "TenantUpdated": ("tenant.tenant.events", "tenant"),
    "ProductEvents": ("catalog.product.events", "catalog"),
    "CategoryEvents": ("catalog.category.events", "catalog"),
    "ProductUpdated": ("catalog.product.events", "catalog"),
    "ProductImagePromoted": ("catalog.product.events", "image"),
}

_DOTTED = re.compile(r"^\s*(\w+)\s+-\.\s+(.+?)\s+\.->\s+(\w+)\s*$")
_LABELED_HOP = re.compile(r"-->\|([^|]*)\|\s*(\w+)")
_LABELED_START = re.compile(r"^\s*(\w+)\s+-->\|")
_SEQUENCE = re.compile(r"^\s*(\w+)->>(\w+):\s*(.+?)\s*$")


class GenerationError(Exception):
    pass


def _arrows(name: str, text: str):
    """(line number, source node, label, target node) for every recognized arrow form inside the
    Mermaid blocks; a chained flowchart line yields one arrow per hop."""
    in_mermaid = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_mermaid = line.strip() == "```mermaid"
            continue
        if not in_mermaid:
            continue
        if match := _DOTTED.match(line):
            yield number, match[1], match[2], match[3]
        elif match := _LABELED_START.match(line):
            source = match[1]
            for hop in _LABELED_HOP.finditer(line):
                yield number, source, hop[1].strip(), hop[2]
                source = hop[2]
        elif match := _SEQUENCE.match(line):
            label = match[3]
            for prefix in SEQUENCE_PREFIXES:
                label = label.removeprefix(prefix)
            yield number, match[1], label, match[2]


def derive_entries(documents: dict[str, str]) -> dict[str, dict[str, set[str]]]:
    """Parent §3.1 rules 2-4: `{service: {"sends": {...}, "receives": {...}}}`."""
    entries = {service: {"sends": set(), "receives": set()} for service in SERVICES}
    for name in sorted(documents):
        for number, source, label, target in _arrows(name, documents[name]):
            if source in NODE_SERVICES and target in BROKER_NODES:
                direction, node = "sends", source
            elif source in BROKER_NODES and target in NODE_SERVICES:
                direction, node = "receives", target
            else:
                continue
            if label in NON_EVENT_LABELS:
                continue
            if label not in LABEL_EVENTS:
                raise GenerationError(f"{name}:{number}: unknown label on a broker-service arrow")
            for service in NODE_SERVICES[node]:
                entries[service][direction].update(LABEL_EVENTS[label])
    return entries


def _frontmatter(fields: list[str], body: str) -> str:
    return "---\n" + "\n".join(fields) + "\n---\n\n" + body + "\n"


def _references(key: str, ids) -> list[str]:
    if not ids:
        return []
    return [f"{key}:"] + [
        line for i in sorted(ids) for line in (f"  - id: {i}", f"    version: {VERSION}")
    ]


def render(entries) -> dict[str, str]:
    """Relative path under `catalog/` -> file text."""
    note = "Generated by harness/v08/generate_eventcatalog.py (v0.8 I1 spec §5.4). Do not edit."
    files = {}
    for domain_id, name, team_id, team_name, members in DOMAINS:
        files[f"domains/{domain_id}/index.mdx"] = _frontmatter(
            [
                f"id: {domain_id}",
                f"name: {name}",
                f"version: {VERSION}",
                "owners:",
                f"  - {team_id}",
                "services:",
            ]
            + [f"  - id: {service}" for service in sorted(members)],
            note,
        )
        files[f"teams/{team_id}.mdx"] = _frontmatter([f"id: {team_id}", f"name: {team_name}"], note)
    for service, name in SERVICES.items():
        files[f"services/{service}/index.mdx"] = _frontmatter(
            [
                f"id: {service}",
                f"name: {name}",
                f"version: {VERSION}",
                *_references("sends", entries[service]["sends"]),
                *_references("receives", entries[service]["receives"]),
            ],
            note,
        )
    for event, summary in EVENTS.items():
        files[f"events/{event}/index.mdx"] = _frontmatter(
            [
                f"id: {event}",
                f"name: {event}",
                f"version: {VERSION}",
                f"summary: {json.dumps(summary)}",
            ],
            note,
        )
    return dict(sorted(files.items()))


def render_lookup() -> str:
    entries = []
    for event in sorted(LOOKUP):
        topic, api = LOOKUP[event]
        repository, commit = _API[api]
        entries.append(
            {
                "event_id": event,
                "topic": topic,
                "source": {
                    "repository": repository,
                    "commit": commit,
                    "path": "pkg/events/topics.go",
                },
            }
        )
    return (
        json.dumps(
            {"schema": "aip-event-topic-lookup/1", "entries": entries}, indent=2, sort_keys=True
        )
        + "\n"
    )


def sha256sums(files: dict[str, str]) -> str:
    return "".join(
        f"{hashlib.sha256(text.encode()).hexdigest()}  {path}\n"
        for path, text in sorted(files.items())
    )


def generate(upstream: Path, package: Path) -> str:
    documents = {}
    for name, expected in UPSTREAM_SHA256.items():
        raw = (upstream / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise GenerationError(f"{name}: digest differs from the pinned value")
        documents[name] = raw.decode()
    files = render(derive_entries(documents))
    lookup, sums = render_lookup(), sha256sums(files)
    # Every check has passed; write.
    for path, text in files.items():
        target = package / "catalog" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    (package / "event-topic-lookup.json").write_text(lookup, encoding="utf-8", newline="\n")
    (package / "catalog.SHA256SUMS").write_text(sums, encoding="utf-8", newline="\n")
    return hashlib.sha256(sums.encode()).hexdigest()


if __name__ == "__main__":
    try:
        print(generate(Path(sys.argv[1]), Path(sys.argv[2])))
    except GenerationError as exc:
        sys.exit(f"error: {exc}")
