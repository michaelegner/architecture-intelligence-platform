"""Guards the frozen I5 Slice 4 inputs against drift: the lifecycle mutations, the lifecycle profile,
and the coverage-matrix fixture revisions (I5 §§9-10).

Nothing here imports into AIP. The tests materialize each frozen lifecycle step into a temporary
directory and check its content digest, and they check that the frozen dossiers stay untouched.
"""

import importlib.util
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
V05 = ROOT / "docs" / "real-world-validation" / "v0.5.0"
LIFECYCLE = V05 / "lifecycle"
STEPS = ("S0", "L1", "L4a", "L4b", "L6", "L2", "R", "L5", "L3")

# `mutate.py <target> <step>` output digests, frozen in Slice 4. L3 excludes its run-time-bound
# tombstones.yaml.
PINNED = {
    "quarkus-super-heroes": {
        "S0": "d69aa4f315510419436b2f0b7cb772cf09e63bbf746dea8da1c1d9452aa55cf0",
        "L1": "d69aa4f315510419436b2f0b7cb772cf09e63bbf746dea8da1c1d9452aa55cf0",
        "L4a": "b21aa1fa456453ab04287f3789149025580b1196f5fdb03d5df6b03e30486e8b",
        "L4b": "79b9879c4cff171cda93262f18db8fb930189ff591898c90a02c4b64939d4835",
        "L6": "b69899848356e23859cb0080939c0047f4ed907983b4638723355af87341bde5",
        "L2": "76296104e4cb476fc6d0fc2be0e47a4d423e6743a9f0e51bbbb0b864faef964e",
        "R": "d69aa4f315510419436b2f0b7cb772cf09e63bbf746dea8da1c1d9452aa55cf0",
        "L5": "6a1f752d19e7544791828b46409298bbcf56da5e3be192c8d8a03c10ebbfcf85",
        "L3": "6385797a8cd917110b68c4f2edf33f69d2ad13f00089902a406aec10dd429f2c",
    },
    "apache-airflow": {
        "S0": "05013f2a477972a8d9bf7d13a351160323f8a5e31b7aa882f2ac6b63521bf89a",
        "L1": "05013f2a477972a8d9bf7d13a351160323f8a5e31b7aa882f2ac6b63521bf89a",
        "L4a": "3de2defbd233cf4df7c9b92ee25639bed98437a03d4d10e00d727b1108f38446",
        "L4b": "cbab3c8218760f734cbe0c3fc30a0f40625e6676b591c9d7b1475bd6363c0661",
        "L6": "10406f3ce0d324bd87a9a1096bfeb5cfa9f128ae843815ecab461b18b4a8c571",
        "L2": "ef5c539c7f7dc0d2ead2847a1595cdcdcc94d114daa402a2ac7d2968fff3ed87",
        "R": "05013f2a477972a8d9bf7d13a351160323f8a5e31b7aa882f2ac6b63521bf89a",
        "L5": "1357ac5639e1e613b5f64074ddfb5e47c28ff60f553345d54e01c015dbc5f098",
        "L3": "66c00f645fae7ba81d8e8cea11f5d3277c83c2ad07fa11108ff2d3facef3c9e5",
    },
}
Q_INV_SAMPLE = (
    "i.discovery_scope_id, i.scope_definition_digest, i.inventory_revision\n"
    '"urn:aip:discovery-scope:x", "ab", "urn:aip:inventory-revision:y"\n'
)


def _mutate():
    spec = importlib.util.spec_from_file_location("i5_lifecycle_mutate", LIFECYCLE / "mutate.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _materialize(tmp_path: Path, target: str, step: str) -> Path:
    workdir = tmp_path / f"{target}-{step}"
    workdir.mkdir()
    inventory = None
    if step == "L3":
        inventory = tmp_path / "q-inv.txt"
        inventory.write_text(Q_INV_SAMPLE)
    _mutate().materialize(target, step, workdir, inventory)
    return workdir


@pytest.mark.parametrize("target", sorted(PINNED))
def test_every_step_materializes_to_its_frozen_digest_without_touching_the_dossier(
    tmp_path, target
):
    mutate = _mutate()
    dossier = V05 / target / "runtime" / "declarations"
    before = mutate.tree_digest(dossier, exclude=frozenset())
    for step in STEPS:
        workdir = _materialize(tmp_path, target, step)
        assert mutate.tree_digest(workdir) == PINNED[target][step], step
    assert mutate.tree_digest(dossier, exclude=frozenset()) == before


@pytest.mark.parametrize("target", sorted(PINNED))
def test_each_mutation_is_exactly_the_frozen_edit(tmp_path, target):
    mutate = _mutate()
    scenario = mutate.load_scenario(target)
    x = scenario["x"]
    x_sid = mutate.x_source_instance_id(scenario)
    frozen = V05 / target / "runtime" / "declarations"

    def bindings(root: Path) -> set[str]:
        document = yaml.safe_load((root / "identity-bindings.yaml").read_text())
        return {b["sourceInstanceId"] for b in document["bindings"]}

    s0 = _materialize(tmp_path, target, "S0") / "declarations"
    assert x_sid in bindings(s0)

    l2 = _materialize(tmp_path, target, "L2") / "declarations"
    assert not (l2 / x).exists()
    assert bindings(l2) == bindings(s0) - {x_sid}

    l4b = _materialize(tmp_path, target, "L4b") / "declarations"
    copy = scenario["steps"][STEPS.index("L4b")]["unbound_copy"]
    assert (l4b / copy["to"]).read_bytes() == (frozen / copy["from"]).read_bytes()
    assert not (l4b / x).exists()

    l6 = _materialize(tmp_path, target, "L6") / "declarations"
    injected = yaml.safe_load((l6 / x).read_text())
    original = yaml.safe_load((frozen / x).read_text())
    assert (
        injected.pop("x-aip-service-id")
        == scenario["steps"][STEPS.index("L6")]["inject_x_service_id"]
    )
    assert injected == original

    l4a = _materialize(tmp_path, target, "L4a")
    assert not (l4a / "declarations-missing").exists()

    l3 = _materialize(tmp_path, target, "L3")
    tombstone = yaml.safe_load((l3 / "tombstones.yaml").read_text())["tombstones"][0]
    assert tombstone["target_source_instance_id"] == x_sid
    assert tombstone["expected_prior_inventory_revision"] == "urn:aip:inventory-revision:y"
    assert not (l3 / "declarations-relocated" / x).exists()


def test_a_tombstone_step_refuses_to_run_without_the_committed_inventory(tmp_path):
    workdir = tmp_path / "w"
    workdir.mkdir()
    with pytest.raises(SystemExit):
        _mutate().materialize("apache-airflow", "L3", workdir, None)


def test_lifecycle_compose_interpolates_only_required_variables_and_pins_images():
    text = "\n".join(
        line
        for line in (LIFECYCLE / "docker-compose.lifecycle.yml").read_text().splitlines()
        if not line.lstrip().startswith("#")
    )
    names = set(re.findall(r"(?<!\$)\$\{([A-Za-z_][A-Za-z0-9_]*)", text))
    assert names == {"AIP_CANDIDATE_SHA", "NEO4J_PASSWORD", "LIFECYCLE_WORKDIR"}
    assert all(
        re.fullmatch(r"\$\{[A-Z0-9_]+:\?[^}]*\}", m)
        for m in re.findall(r"(?<!\$)\$\{[^}]*\}", text)
    )
    services = yaml.safe_load(text)["services"]
    assert services["architecture-intelligence"]["image"].startswith(
        "aip-i5-candidate:${AIP_CANDIDATE_SHA"
    )
    assert "@sha256:" in services["neo4j"]["image"]


def test_lifecycle_runbook_invokes_compose_only_through_the_frozen_helper():
    runbook = (LIFECYCLE / "runbook.md").read_text()
    helper = re.search(r"^frozen_compose\(\) \{\n(.*?)\n\}", runbook, re.DOTALL | re.MULTILINE)

    assert helper is not None
    assert " ".join(helper.group(1).split()) == (
        'docker compose -p i5-lifecycle --project-directory "$LIFECYCLE" \\ '
        '-f "$LIFECYCLE/docker-compose.lifecycle.yml" --env-file /dev/null "$@"'
    )
    assert runbook.count("docker compose") == 1
    assert "--access-mode read" in runbook


def test_frozen_queries_are_read_only():
    # Word boundaries, so a write clause followed by a newline or a tab is still caught (PR #244).
    writes = re.compile(r"\b(CREATE|MERGE|SET|DELETE|REMOVE|DETACH|LOAD\s+CSV|FOREACH)\b")
    queries = sorted((V05 / "queries").glob("*.cypher"))
    assert {q.stem for q in queries} == {
        "Q-INV",
        "Q-SRC",
        "Q-SRC-SEM",
        "Q-OWN",
        "Q-SVC",
        "Q-REL",
        "Q-GRAPH",
    }
    for query in queries:
        text = re.sub(r"//.*", "", query.read_text()).upper()
        assert writes.search(text) is None, query.name


def test_q_graph_orders_the_combined_union_once():
    # PR #244 review: branch-local ORDER BYs do not order a UNION ALL's combined rows.
    text = re.sub(r"//.*", "", (V05 / "queries" / "Q-GRAPH.cypher").read_text())
    assert re.search(r"\}\s*RETURN kind, id, entity\s*ORDER BY kind, id;\s*$", text)
    assert text.count("ORDER BY") == 1


def test_without_x_is_the_exact_owned_graph_projection():
    spec = importlib.util.spec_from_file_location("i5_without_x", LIFECYCLE / "without_x.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    q_rel = (
        "type, source, target, key, owners\n"
        '"CALLS", "service:a", "op:b", "k1", ["s1", "sx"]\n'
        '"PROVIDES", "service:x", "op:x", "k2", ["sx"]\n'
        '"PROVIDES", "service:a", "op:a", NULL, ["s1"]\n'
    )
    assert module.without_x(q_rel, "sx") == (
        "type, source, target, key, owners\n"
        '"CALLS", "service:a", "op:b", "k1", ["s1"]\n'
        '"PROVIDES", "service:a", "op:a", NULL, ["s1"]\n'
    )


def test_lifecycle_runbook_queries_every_frozen_state_query():
    runbook = (LIFECYCLE / "runbook.md").read_text()
    assert "for q in Q-INV Q-SRC Q-SRC-SEM Q-OWN Q-SVC Q-REL; do" in runbook


def test_coverage_matrix_fixture_digests_match_the_files_on_disk():
    mutate = _mutate()
    matrix = (V05 / "coverage-matrix.md").read_text()
    pinned = re.findall(r"`((?:tests|evaluation)/[^`]+)`[^|]*?digest `([0-9a-f]{64})`", matrix)
    assert {path for path, _ in pinned} == {
        "tests/fixtures/kubernetes/i2-independent-capture",
        "tests/fixtures/deployment/i3-cross-source",
        "tests/fixtures/pubsub",
        "tests/fixtures/pubsub/kafka",
        "evaluation/architecture_answers/scenarios",
    }
    for path, digest in pinned:
        # The one documented algorithm (coverage-matrix.md names mutate.py::tree_digest).
        assert mutate.tree_digest(ROOT / path, exclude=frozenset()) == digest, path
