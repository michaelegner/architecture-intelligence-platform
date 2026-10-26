"""v0.8 I1 spec §5: the closed EventCatalog subset and the event -> Topic lookup
(`aip-event-topic-lookup/1`). Pure: it validates already-parsed frontmatter mappings and builds the
typed declaration set. No graph, no adapter, no Service resolution (I2).

Nothing here ever returns, logs or raises a source *value*: a problem carries a stable code and a
pointer made of a catalog-relative path and field names or list indexes only.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.sources.identity import event_catalog_source_revision
from app.sources.model import EventCatalogSourceConfig

LOOKUP_SCHEMA_ID = "aip-event-topic-lookup/1"
VERSION = "1.0.0"

# Reason codes frozen by spec §5.5.
INVALID = "EVENTCATALOG_INVALID"
UNSUPPORTED = "EVENTCATALOG_UNSUPPORTED"
REFERENCE_UNRESOLVED = "EVENTCATALOG_REFERENCE_UNRESOLVED"
MEMBERSHIP_INVALID = "EVENTCATALOG_MEMBERSHIP_INVALID"
# v0.8 I2 §2 (Q1): two registrations with one id or one environment; raised by the import request.
DUPLICATE_SOURCE = "EVENTCATALOG_DUPLICATE_SOURCE"

_MESSAGES = {
    INVALID: "the EventCatalog is malformed or misses a required field",
    UNSUPPORTED: "the EventCatalog uses a file, field or YAML feature outside the supported subset",
    REFERENCE_UNRESOLVED: "an EventCatalog reference or lookup entry does not resolve",
    MEMBERSHIP_INVALID: "a service is in no domain or in several domains",
    DUPLICATE_SOURCE: "another EventCatalog registration uses the same id or environment",
}

# Spec §5.1: the fields read per entry kind; any other field is unsupported.
_FIELDS = {
    "domains": {"id", "name", "version", "owners", "services"},
    "services": {"id", "name", "version", "sends", "receives"},
    "events": {"id", "name", "version", "summary"},
    "teams": {"id", "name"},
}
_REQUIRED = {
    "domains": ("id", "name", "version"),
    "services": ("id", "name", "version"),
    "events": ("id", "name", "version", "summary"),
    "teams": ("id", "name"),
}


@dataclass(frozen=True)
class EventCatalogProblem:
    code: str
    pointer: str = ""

    @property
    def message(self) -> str:
        return _MESSAGES[self.code]


class EventCatalogRejected(Exception):
    def __init__(self, problem: EventCatalogProblem) -> None:
        super().__init__(problem.code)
        self.problem = problem


def _reject(code: str, pointer: str = "") -> EventCatalogRejected:
    return EventCatalogRejected(EventCatalogProblem(code, pointer))


@dataclass(frozen=True)
class EventReference:
    event_id: str
    version: str


@dataclass(frozen=True)
class CatalogDomain:
    id: str
    name: str
    owners: tuple[str, ...]
    services: tuple[str, ...]
    path: str


@dataclass(frozen=True)
class CatalogService:
    id: str
    name: str
    sends: tuple[EventReference, ...]
    receives: tuple[EventReference, ...]
    path: str


@dataclass(frozen=True)
class CatalogEvent:
    id: str
    name: str
    summary: str
    path: str


@dataclass(frozen=True)
class CatalogTeam:
    id: str
    name: str
    path: str


@dataclass(frozen=True)
class LookupEntry:
    event_id: str
    topic: str
    repository: str
    commit: str
    path: str


@dataclass(frozen=True)
class EventCatalogDeclarations:
    """Spec §5.5 loader output. Every item carries its catalog-relative file path; the catalog
    digest is the provenance of the whole set."""

    domains: tuple[CatalogDomain, ...]
    services: tuple[CatalogService, ...]
    events: tuple[CatalogEvent, ...]
    teams: tuple[CatalogTeam, ...]
    lookup: tuple[LookupEntry, ...]
    catalog_digest: str
    # v0.8 I2 D12: SHA-256 of the exact lookup bytes; the revision covers both digests.
    lookup_digest: str
    source_revision: str


def _string(value: object, pointer: str) -> str:
    if not isinstance(value, str) or not value:
        raise _reject(INVALID, pointer)
    return value


def _list(value: object, pointer: str) -> list:
    if not isinstance(value, list):
        raise _reject(INVALID, pointer)
    return value


def _check_fields(kind: str, document: Mapping, path: str) -> None:
    if any(not isinstance(key, str) or key not in _FIELDS[kind] for key in document):
        raise _reject(UNSUPPORTED, path)
    for field in _REQUIRED[kind]:
        if field not in document:
            raise _reject(INVALID, f"{path}#/{field}")
        _string(document[field], f"{path}#/{field}")
    if "version" in _FIELDS[kind] and document["version"] != VERSION:
        raise _reject(INVALID, f"{path}#/version")


def _event_references(value: object, pointer: str) -> tuple[EventReference, ...]:
    references = []
    for index, item in enumerate(_list(value, pointer)):
        item_pointer = f"{pointer}/{index}"
        if not isinstance(item, Mapping):
            raise _reject(INVALID, item_pointer)
        if set(item) - {"id", "version"}:
            raise _reject(UNSUPPORTED, item_pointer)
        if "version" not in item:
            raise _reject(REFERENCE_UNRESOLVED, f"{item_pointer}/version")
        references.append(
            EventReference(
                _string(item.get("id"), f"{item_pointer}/id"),
                _string(item["version"], f"{item_pointer}/version"),
            )
        )
    return tuple(references)


def _id_references(value: object, pointer: str, *, mapping: bool) -> tuple[str, ...]:
    ids = []
    for index, item in enumerate(_list(value, pointer)):
        item_pointer = f"{pointer}/{index}"
        if mapping:
            if not isinstance(item, Mapping):
                raise _reject(INVALID, item_pointer)
            if set(item) != {"id"}:
                raise _reject(UNSUPPORTED if set(item) - {"id"} else INVALID, item_pointer)
            item = item["id"]
        ids.append(_string(item, item_pointer))
    return tuple(ids)


def _unique(items: tuple) -> dict:
    counts = Counter(item.id for item in items)
    for item in items:
        if counts[item.id] > 1:
            raise _reject(INVALID, item.path)
    return {item.id: item for item in items}


def build_declarations(
    entries: Mapping[str, tuple[str, Mapping]],
    lookup_document: object,
    *,
    lookup_pointer: str,
    catalog_digest: str,
    lookup_digest: str,
) -> EventCatalogDeclarations:
    """`entries` maps each catalog-relative path to its (kind, frontmatter). Raises
    `EventCatalogRejected`."""
    domains, services, events, teams = [], [], [], []
    for path, (kind, document) in sorted(entries.items()):
        _check_fields(kind, document, path)
        if kind == "domains":
            domains.append(
                CatalogDomain(
                    document["id"],
                    document["name"],
                    _id_references(document.get("owners", []), f"{path}#/owners", mapping=False),
                    _id_references(document.get("services", []), f"{path}#/services", mapping=True),
                    path,
                )
            )
        elif kind == "services":
            services.append(
                CatalogService(
                    document["id"],
                    document["name"],
                    _event_references(document.get("sends", []), f"{path}#/sends"),
                    _event_references(document.get("receives", []), f"{path}#/receives"),
                    path,
                )
            )
        elif kind == "events":
            events.append(CatalogEvent(document["id"], document["name"], document["summary"], path))
        else:
            teams.append(CatalogTeam(document["id"], document["name"], path))

    by_event = _unique(tuple(events))
    by_service = _unique(tuple(services))
    by_team = _unique(tuple(teams))
    _unique(tuple(domains))

    for service in services:
        for direction, references in (("sends", service.sends), ("receives", service.receives)):
            for index, reference in enumerate(references):
                if reference.event_id not in by_event or reference.version != VERSION:
                    raise _reject(REFERENCE_UNRESOLVED, f"{service.path}#/{direction}/{index}")
    membership: Counter[str] = Counter()
    for domain in domains:
        for index, team in enumerate(domain.owners):
            if team not in by_team:
                raise _reject(REFERENCE_UNRESOLVED, f"{domain.path}#/owners/{index}")
        for index, service_id in enumerate(domain.services):
            if service_id not in by_service:
                raise _reject(REFERENCE_UNRESOLVED, f"{domain.path}#/services/{index}")
            membership[service_id] += 1
    for service in services:
        if membership[service.id] != 1:
            raise _reject(MEMBERSHIP_INVALID, service.path)

    lookup = _lookup_entries(lookup_document, lookup_pointer)
    lookup_ids = Counter(entry.event_id for entry in lookup)
    for index, entry in enumerate(lookup):
        if lookup_ids[entry.event_id] > 1:
            raise _reject(INVALID, f"{lookup_pointer}#/entries/{index}")
        if entry.event_id not in by_event:
            raise _reject(REFERENCE_UNRESOLVED, f"{lookup_pointer}#/entries/{index}")
    for event in events:
        if event.id not in lookup_ids:
            raise _reject(REFERENCE_UNRESOLVED, event.path)

    return EventCatalogDeclarations(
        domains=tuple(domains),
        services=tuple(services),
        events=tuple(events),
        teams=tuple(teams),
        lookup=lookup,
        catalog_digest=catalog_digest,
        lookup_digest=lookup_digest,
        source_revision=event_catalog_source_revision(
            catalog_digest=catalog_digest, lookup_digest=lookup_digest
        ),
    )


def _lookup_entries(document: object, pointer: str) -> tuple[LookupEntry, ...]:
    if not isinstance(document, Mapping):
        raise _reject(INVALID, pointer)
    if set(document) - {"schema", "entries"}:
        raise _reject(UNSUPPORTED, pointer)
    if document.get("schema") != LOOKUP_SCHEMA_ID:
        raise _reject(UNSUPPORTED, f"{pointer}#/schema")
    entries = []
    for index, item in enumerate(_list(document.get("entries"), f"{pointer}#/entries")):
        item_pointer = f"{pointer}#/entries/{index}"
        if not isinstance(item, Mapping) or not isinstance(item.get("source"), Mapping):
            raise _reject(INVALID, item_pointer)
        source = item["source"]
        if set(item) != {"event_id", "topic", "source"} or set(source) != {
            "repository",
            "commit",
            "path",
        }:
            raise _reject(UNSUPPORTED if _extra(item, source) else INVALID, item_pointer)
        entries.append(
            LookupEntry(
                _string(item["event_id"], f"{item_pointer}/event_id"),
                _string(item["topic"], f"{item_pointer}/topic"),
                _string(source["repository"], f"{item_pointer}/source/repository"),
                _string(source["commit"], f"{item_pointer}/source/commit"),
                _string(source["path"], f"{item_pointer}/source/path"),
            )
        )
    return tuple(entries)


def _extra(item: Mapping, source: Mapping) -> bool:
    return bool(set(item) - {"event_id", "topic", "source"}) or bool(
        set(source) - {"repository", "commit", "path"}
    )


def duplicate_registrations(configs: Sequence[EventCatalogSourceConfig]) -> frozenset[str]:
    """I2 §2 (Q1): every configured id used by more than one registration, or by a registration
    whose environment another registration also uses. All of them are rejected
    (`EVENTCATALOG_DUPLICATE_SOURCE`); none commits. v0.8 accepts one catalog per environment."""
    ids = Counter(config.id for config in configs)
    environments = Counter(config.environment for config in configs)
    return frozenset(
        config.id
        for config in configs
        if ids[config.id] > 1 or environments[config.environment] > 1
    )
