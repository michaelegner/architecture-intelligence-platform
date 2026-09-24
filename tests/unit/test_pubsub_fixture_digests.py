"""v0.5.0 I4 slice 5: the §13.3 broker-semantic fixtures are frozen inputs - `SHA256SUMS` pins every
file, so a fixture (or its hand-authored expectation) can only change deliberately, together with
its digest, and the slice-6 completion record can cite exact fixture digests."""

import hashlib
from pathlib import Path

FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "pubsub"


def _manifest() -> dict[str, str]:
    entries = {}
    for line in (FIXTURES_ROOT / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        entries[path.removeprefix("./")] = digest
    return entries


def test_every_fixture_file_matches_its_pinned_digest():
    manifest = _manifest()
    on_disk = {
        path.relative_to(FIXTURES_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURES_ROOT.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert on_disk == manifest


def test_each_broker_fixture_carries_its_required_disclosure_parts():
    for fixture in ("azure-service-bus", "google-pubsub", "kafka"):
        root = FIXTURES_ROOT / fixture
        assert (root / "spans.yaml").is_file()
        assert (root / "expected.yaml").is_file()
        assert list((root / "declarations").glob("*/asyncapi.yaml"))
        provenance = (root / "PROVENANCE.md").read_text()
        for section in (
            "**Retrieval date:** 2026-09-23",
            "## Authored scenario data",
            "## Expected facts",
            "## Forbidden facts",
            "## Unsupported / deferred",
        ):
            assert section in provenance, (fixture, section)
