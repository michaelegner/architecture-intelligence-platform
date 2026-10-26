"""v0.8 I1 spec §5.5: the registration-bound EventCatalog loader. Reads the catalog directory and
the event -> Topic lookup that a registration names, checks the bounds and the closed subset, and
returns either the typed declaration set or a stable rejection. It returns, logs and raises no
source value. I1 persists nothing; I2 wires the result into the import."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.common.bounded_yaml import (
    BoundedYamlLimitExceeded,
    BoundedYamlMalformed,
    load_bounded_yaml_documents,
)
from app.common.jcs import json_nesting_depth
from app.common.locators import confined_path
from app.sources.event_catalog_contract import (
    INVALID,
    UNSUPPORTED,
    EventCatalogDeclarations,
    EventCatalogProblem,
    EventCatalogRejected,
    build_declarations,
)
from app.sources.model import EventCatalogSourceConfig

MAX_FILES = 1000
MAX_FILE_BYTES = 256 * 1024
MAX_NESTING = 32
_DELIMITER = "---"


@dataclass(frozen=True)
class LoadedEventCatalog:
    declarations: EventCatalogDeclarations


@dataclass(frozen=True)
class RejectedEventCatalog:
    problem: EventCatalogProblem


def catalog_sha256sums(files: dict[str, bytes]) -> bytes:
    """Spec §5.4: one `sha256sum` line per catalog file, sorted by catalog-relative path."""
    return "".join(
        f"{hashlib.sha256(content).hexdigest()}  {path}\n"
        for path, content in sorted(files.items())
    ).encode()


def _kind(relative: str) -> str | None:
    """Spec §5.1 layout: `<kind>/<id>/index.mdx` for domains, services and events;
    `teams/<id>.mdx`."""
    parts = relative.split("/")
    if (
        len(parts) == 3
        and parts[0] in {"domains", "services", "events"}
        and parts[2] == "index.mdx"
    ):
        return parts[0]
    if len(parts) == 2 and parts[0] == "teams" and parts[1].endswith(".mdx") and parts[1] != ".mdx":
        return "teams"
    return None


def _read(path: Path, pointer: str) -> bytes:
    try:
        with path.open("rb") as handle:
            content = handle.read(MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer)) from exc
    if len(content) > MAX_FILE_BYTES:
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, pointer))
    return content


def _frontmatter(content: bytes, pointer: str) -> dict:
    try:
        lines = content.decode().split("\n")
    except UnicodeDecodeError as exc:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer)) from exc
    if not lines or lines[0] != _DELIMITER or _DELIMITER not in lines[1:]:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer))
    end = lines.index(_DELIMITER, 1)
    try:
        documents = load_bounded_yaml_documents("\n".join(lines[1:end]), max_depth=MAX_NESTING)
    except BoundedYamlLimitExceeded as exc:
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, pointer)) from exc
    except BoundedYamlMalformed as exc:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer)) from exc
    except yaml.constructor.ConstructorError as exc:  # a custom tag
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, pointer)) from exc
    except yaml.YAMLError as exc:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer)) from exc
    if len(documents) != 1 or not isinstance(documents[0], dict):
        raise EventCatalogRejected(EventCatalogProblem(INVALID, pointer))
    return documents[0]


def _load(config: EventCatalogSourceConfig) -> EventCatalogDeclarations:
    catalog_root = confined_path(config.root, config.catalog_relative_path)
    lookup_path = confined_path(config.root, config.lookup_relative_path)
    if catalog_root is None or not catalog_root.is_dir():
        raise EventCatalogRejected(EventCatalogProblem(INVALID, "/catalog_relative_path"))
    if lookup_path is None:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, "/lookup_relative_path"))

    paths = sorted(p for p in catalog_root.rglob("*") if not p.is_dir())
    if len(paths) > MAX_FILES:
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED))
    files: dict[str, bytes] = {}
    entries = {}
    for path in paths:
        relative = path.relative_to(catalog_root).as_posix()
        kind = _kind(relative)
        # A symlink is never part of the generated catalog; it could also leave the root.
        if kind is None or path.is_symlink():
            raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, relative))
        files[relative] = _read(path, relative)
        entries[relative] = (kind, _frontmatter(files[relative], relative))

    lookup_pointer = config.lookup_relative_path
    lookup_bytes = _read(lookup_path, lookup_pointer)
    try:
        lookup_document = json.loads(lookup_bytes)
    except RecursionError as exc:
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, lookup_pointer)) from exc
    except ValueError as exc:
        raise EventCatalogRejected(EventCatalogProblem(INVALID, lookup_pointer)) from exc
    if json_nesting_depth(lookup_document) > MAX_NESTING:
        raise EventCatalogRejected(EventCatalogProblem(UNSUPPORTED, lookup_pointer))

    return build_declarations(
        entries,
        lookup_document,
        lookup_pointer=lookup_pointer,
        catalog_digest=hashlib.sha256(catalog_sha256sums(files)).hexdigest(),
    )


def load_event_catalog(
    config: EventCatalogSourceConfig,
) -> LoadedEventCatalog | RejectedEventCatalog:
    try:
        return LoadedEventCatalog(_load(config))
    except EventCatalogRejected as exc:
        return RejectedEventCatalog(exc.problem)
