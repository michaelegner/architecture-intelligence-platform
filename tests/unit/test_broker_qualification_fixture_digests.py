"""v0.6.1 I3a: the Broker qualification fixtures are frozen inputs. `SHA256SUMS` pins every file, so a
fixture (or its hand-authored expectation) can only change deliberately, together with its digest,
and the release record can cite exact fixture digests. The sibling expectations are also checked
against the *untouched* Pub/Sub declarations they describe, so an expectation cannot silently drift
from the declarations it claims to qualify."""

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_ROOT = ROOT / "tests" / "fixtures" / "broker-qualification"
PUBSUB_ROOT = ROOT / "tests" / "fixtures" / "pubsub"
SIBLINGS = ("azure-service-bus", "google-pubsub", "kafka")
SYSTEMS = ("calm-fluxnova", "airflow-negative")
SECTIONS = (
    "**Retrieval date:**",
    "## Authored scenario data",
    "## Expected facts",
    "## Forbidden facts",
    "## Unsupported / deferred",
)


def _manifest() -> dict[str, str]:
    entries = {}
    for line in (FIXTURES_ROOT / "SHA256SUMS").read_text().splitlines():
        digest, path = line.split(maxsplit=1)
        entries[path.removeprefix("./")] = digest
    return entries


def test_every_fixture_file_matches_its_pinned_digest():
    on_disk = {
        path.relative_to(FIXTURES_ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(FIXTURES_ROOT.rglob("*"))
        if path.is_file() and path.name != "SHA256SUMS"
    }
    assert on_disk == _manifest()


def test_each_fixture_carries_its_required_disclosure_parts():
    for name in (*SIBLINGS, *SYSTEMS):
        provenance = (FIXTURES_ROOT / name / "PROVENANCE.md").read_text()
        for section in SECTIONS:
            assert section in provenance, (name, section)
        assert (FIXTURES_ROOT / name / "expected.yaml").is_file()


def test_each_pubsub_sibling_states_the_deviation_from_extending_in_place():
    for name in SIBLINGS:
        provenance = (FIXTURES_ROOT / name / "PROVENANCE.md").read_text()
        assert "sibling" in provenance and "untouched" in provenance, name
        assert f"tests/fixtures/pubsub/{name}/declarations" in provenance, name


def test_each_sibling_expectation_matches_the_untouched_declarations_it_describes():
    for name in SIBLINGS:
        expected = yaml.safe_load((FIXTURES_ROOT / name / "expected.yaml").read_text())
        declarations = ROOT / expected["declarations"]
        assert declarations == PUBSUB_ROOT / name / "declarations"
        declared: dict[str, set[str]] = {}
        for path in sorted(declarations.glob("*/asyncapi.yaml")):
            document = yaml.safe_load(path.read_text())
            ids = {
                server["x-aip-broker-id"]
                for server in (document.get("servers") or {}).values()
                if "x-aip-broker-id" in server
            }
            declared[path.parent.name] = ids
        # every declaring service uses exactly the declared Broker; nothing else is expected
        assert sorted(expected["brokers"]) == sorted({b for ids in declared.values() for b in ids})
        assert sorted(tuple(pair) for pair in expected["uses_broker"]) == sorted(
            (slug, broker) for slug, ids in declared.items() for broker in ids
        )
