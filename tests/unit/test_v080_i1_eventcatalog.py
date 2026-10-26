"""v0.8 I1 A1-A3: the EventCatalog generator, the committed catalog and the loader rejections.

The expected catalog content below is written by hand from the v0.8 specification §3.1 result
table and the I1 spec §5.2, never derived from the generator's output.
"""

import hashlib
import importlib.util
import re
import shutil
from pathlib import Path

import pytest

from app.sources.event_catalog_contract import (
    INVALID,
    MEMBERSHIP_INVALID,
    REFERENCE_UNRESOLVED,
    UNSUPPORTED,
)
from app.sources.event_catalog_loader import (
    LoadedEventCatalog,
    RejectedEventCatalog,
    load_event_catalog,
)
from app.sources.model import EventCatalogSourceConfig

REPO = Path(__file__).resolve().parents[2]
PACKAGE = REPO / "docs/specifications/0.8.0/i1-evidence"
_spec = importlib.util.spec_from_file_location(
    "generate_eventcatalog", REPO / "harness/v08/generate_eventcatalog.py"
)
assert _spec is not None and _spec.loader is not None
generator = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generator)

CANARY = "CANARY-7f3a"
T, C, I, PQ, CQ = (
    f"ecommerce-{name}-service"
    for name in ("tenant", "catalog", "image", "product-query", "category-query")
)
# v0.8 specification §3.1 result table.
EXPECTED_ENTRIES = {
    T: ({"TenantUpdated"}, set()),
    C: ({"ProductEvents", "CategoryEvents", "ProductUpdated"}, set()),
    I: ({"ProductImagePromoted"}, {"ProductUpdated"}),
    PQ: (set(), {"ProductUpdated", "ProductImagePromoted"}),
    CQ: (set(), set()),
}
# I1 spec §5.2.
EXPECTED_DOMAINS = {
    "store-provisioning": (("provisioning-team",), {T}),
    "catalog-management": (("catalog-team",), {C, I}),
    "storefront": (("storefront-team",), {PQ, CQ}),
}
EXPECTED_LOOKUP = {
    "TenantUpdated": ("tenant.tenant.events", "Sokol111/ecommerce-tenant-service-api"),
    "ProductEvents": ("catalog.product.events", "Sokol111/ecommerce-catalog-service-api"),
    "CategoryEvents": ("catalog.category.events", "Sokol111/ecommerce-catalog-service-api"),
    "ProductUpdated": ("catalog.product.events", "Sokol111/ecommerce-catalog-service-api"),
    "ProductImagePromoted": ("catalog.product.events", "Sokol111/ecommerce-image-service-api"),
}


def _tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _committed_output() -> dict[str, bytes]:
    files = {f"catalog/{k}": v for k, v in _tree(PACKAGE / "catalog").items()}
    for name in ("event-topic-lookup.json", "catalog.SHA256SUMS"):
        files[name] = (PACKAGE / name).read_bytes()
    return files


# A1


def test_the_generator_reproduces_the_committed_output_byte_for_byte(tmp_path) -> None:
    digest = generator.generate(PACKAGE / "upstream", tmp_path)
    assert _tree(tmp_path) == _committed_output()
    assert digest == hashlib.sha256((PACKAGE / "catalog.SHA256SUMS").read_bytes()).hexdigest()


def test_a_changed_upstream_digest_stops_before_any_write(tmp_path) -> None:
    upstream = tmp_path / "upstream"
    shutil.copytree(PACKAGE / "upstream", upstream)
    (upstream / "platform-overview.md").write_text("changed\n")
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(generator.GenerationError, match=re.escape("platform-overview.md: digest")):
        generator.generate(upstream, out)
    assert list(out.iterdir()) == []


def test_an_unknown_label_on_a_broker_arrow_stops_with_file_and_line(tmp_path, monkeypatch) -> None:
    upstream = tmp_path / "upstream"
    shutil.copytree(PACKAGE / "upstream", upstream)
    path = upstream / "product-update-flow.md"
    text = path.read_text().replace("Publish ProductUpdated event", "Publish PriceChanged event")
    path.write_text(text)
    line = next(n for n, row in enumerate(text.splitlines(), 1) if "PriceChanged" in row)
    monkeypatch.setitem(
        generator.UPSTREAM_SHA256,
        "product-update-flow.md",
        hashlib.sha256(text.encode()).hexdigest(),
    )
    out = tmp_path / "out"
    out.mkdir()
    with pytest.raises(
        generator.GenerationError, match=re.escape(f"product-update-flow.md:{line}: unknown")
    ):
        generator.generate(upstream, out)
    assert list(out.iterdir()) == []


# A2


def _config(root: Path = PACKAGE) -> EventCatalogSourceConfig:
    return EventCatalogSourceConfig(id="sokol111-catalog", root=root, environment="local")


def test_the_loaded_catalog_equals_the_specification() -> None:
    result = load_event_catalog(_config())
    assert isinstance(result, LoadedEventCatalog)
    declarations = result.declarations

    assert {
        s.id: ({r.event_id for r in s.sends}, {r.event_id for r in s.receives})
        for s in declarations.services
    } == EXPECTED_ENTRIES
    assert {d.id: (d.owners, set(d.services)) for d in declarations.domains} == EXPECTED_DOMAINS
    assert {t.id for t in declarations.teams} == {
        "provisioning-team",
        "catalog-team",
        "storefront-team",
    }
    assert {e.id for e in declarations.events} == set(EXPECTED_LOOKUP)
    assert {e.event_id: (e.topic, e.repository) for e in declarations.lookup} == EXPECTED_LOOKUP
    digest = hashlib.sha256((PACKAGE / "catalog.SHA256SUMS").read_bytes()).hexdigest()
    assert declarations.catalog_digest == digest
    assert declarations.source_revision == f"catalog-sha256:{digest}"
    assert all(s.path == f"services/{s.id}/index.mdx" for s in declarations.services)


# A3


def _mutated(tmp_path: Path, relative: str, old: str, new: str) -> RejectedEventCatalog:
    root = tmp_path / "package"
    shutil.copytree(PACKAGE, root)
    path = root / relative
    text = path.read_text()
    assert old in text
    path.write_text(text.replace(old, new, 1))
    result = load_event_catalog(_config(root))
    assert isinstance(result, RejectedEventCatalog)
    assert CANARY not in repr(result) and CANARY not in result.problem.message
    return result


IMAGE = f"catalog/services/{I}/index.mdx"
STOREFRONT = "catalog/domains/storefront/index.mdx"


@pytest.mark.parametrize(
    ("relative", "old", "new", "code"),
    [
        # Missing required field.
        (IMAGE, "name: Image Service\n", "", INVALID),
        # Malformed frontmatter (no closing delimiter).
        (IMAGE, "\n---\n", f"\n{CANARY}\n", INVALID),
        # Duplicate key.
        (IMAGE, "name: Image Service\n", f"name: Image Service\nname: {CANARY}\n", INVALID),
        # Version other than 1.0.0 on an entry.
        (IMAGE, "version: 1.0.0\nsends", f"version: {CANARY}\nsends", INVALID),
        # Unknown field.
        (IMAGE, "name: Image Service\n", f"name: Image Service\nowners: [{CANARY}]\n", UNSUPPORTED),
        # YAML alias.
        (IMAGE, "name: Image Service\n", f"name: &a {CANARY}\nsummaryx: *a\n", UNSUPPORTED),
        # Custom tag.
        (IMAGE, "name: Image Service\n", f"name: !secret {CANARY}\n", UNSUPPORTED),
        # Reference without version.
        (
            IMAGE,
            "  - id: ProductUpdated\n    version: 1.0.0\n",
            "  - id: ProductUpdated\n",
            REFERENCE_UNRESOLVED,
        ),
        # Reference to an unknown event.
        (IMAGE, "id: ProductUpdated", f"id: {CANARY}", REFERENCE_UNRESOLVED),
        # Reference version mismatch.
        (
            IMAGE,
            "    version: 1.0.0\nreceives",
            "    version: 2.0.0\nreceives",
            REFERENCE_UNRESOLVED,
        ),
        # Unknown owner team.
        (STOREFRONT, "  - storefront-team", f"  - {CANARY}", REFERENCE_UNRESOLVED),
        # Lookup misses an event.
        (
            "event-topic-lookup.json",
            '"event_id": "TenantUpdated"',
            f'"event_id": "{CANARY}"',
            REFERENCE_UNRESOLVED,
        ),
        # A service in no domain.
        (STOREFRONT, f"  - id: {CQ}\n", "", MEMBERSHIP_INVALID),
        # A service in two domains.
        (
            STOREFRONT,
            f"  - id: {CQ}\n",
            f"  - id: {CQ}\n  - id: {I}\n",
            MEMBERSHIP_INVALID,
        ),
    ],
)
def test_each_rejection_has_its_code_and_echoes_no_value(
    tmp_path, relative, old, new, code
) -> None:
    assert _mutated(tmp_path, relative, old, new).problem.code == code


def test_an_unknown_file_is_unsupported(tmp_path) -> None:
    root = tmp_path / "package"
    shutil.copytree(PACKAGE, root)
    (root / "catalog/flows").mkdir()
    (root / "catalog/flows/index.mdx").write_text(f"---\nid: {CANARY}\n---\n")
    result = load_event_catalog(_config(root))
    assert isinstance(result, RejectedEventCatalog)
    assert result.problem.code == UNSUPPORTED and CANARY not in repr(result)


def test_a_symlinked_directory_under_the_catalog_is_unsupported(tmp_path) -> None:
    root = tmp_path / "package"
    shutil.copytree(PACKAGE, root)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / "catalog/flows").symlink_to(elsewhere, target_is_directory=True)
    result = load_event_catalog(_config(root))
    assert isinstance(result, RejectedEventCatalog)
    assert (result.problem.code, result.problem.pointer) == (UNSUPPORTED, "flows")


def test_a_duplicate_key_in_the_lookup_is_invalid(tmp_path) -> None:
    result = _mutated(
        tmp_path,
        "event-topic-lookup.json",
        '"topic": "tenant.tenant.events"',
        f'"topic": "tenant.tenant.events", "topic": "{CANARY}"',
    )
    assert result.problem.code == INVALID


def test_a_path_outside_the_root_is_invalid(tmp_path) -> None:
    config = EventCatalogSourceConfig(
        id="c", root=PACKAGE, environment="local", lookup_relative_path="../../i1-vectors/ids.json"
    )
    result = load_event_catalog(config)
    assert isinstance(result, RejectedEventCatalog)
    assert result.problem.code == INVALID
