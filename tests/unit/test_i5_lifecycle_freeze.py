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
# tombstones.yaml. The Quarkus L4b, L2, L5 and L3 digests were re-pinned by the I5 §6 correction of X
# (finding F7; lifecycle/README.md "Revision history"). Every other digest is unchanged.
PINNED = {
    "quarkus-super-heroes": {
        "S0": "72052574a730100a29ff2da60f602cb74147950ad1b344c1ef752045488e4cb6",
        "L1": "72052574a730100a29ff2da60f602cb74147950ad1b344c1ef752045488e4cb6",
        "L4a": "b21aa1fa456453ab04287f3789149025580b1196f5fdb03d5df6b03e30486e8b",
        "L4b": "f340ac40ea907b8728c7e14547e3f4956b9f3b84a9621632f0714c5c2a595438",
        "L6": "b3dbede5f9f8f988048333805ccce8d0aa10b62f28cea728abfb824458d43175",
        "L2": "6bfc75c8101c38cf2f40467aae19538ac1ab6cbc87518073b2b84fc4b0240eb8",
        "R": "72052574a730100a29ff2da60f602cb74147950ad1b344c1ef752045488e4cb6",
        "L5": "82399fdc25c35d83404dba727a81bda2a522d3e60cec7220f561325828769959",
        "L3": "4bff75852deff48baa77b70957fa1514531bba51d75039f0554597fd9963df6d",
    },
    "apache-airflow": {
        "S0": "e6e00555f1805f00d464aab8b2a45a738afc570abfce378ddcff4dfc0fc96011",
        "L1": "e6e00555f1805f00d464aab8b2a45a738afc570abfce378ddcff4dfc0fc96011",
        "L4a": "3de2defbd233cf4df7c9b92ee25639bed98437a03d4d10e00d727b1108f38446",
        "L4b": "6b72961e8d7145394c72d6f263d828191558a46594bfa206776bf5246b86c8c7",
        "L6": "a78c6e16df7eae8d8506a0e9b4e3aef40ccc5b0d3962927e9777d7ac9ef970d0",
        "L2": "3a728ad38910c61a8fb7283c41ba4333eb8c37d667a94965df130c4b621d1ebf",
        "R": "e6e00555f1805f00d464aab8b2a45a738afc570abfce378ddcff4dfc0fc96011",
        "L5": "fb829f2990f2846a1f8af5e6e51b9963eeed0186acd0df84fefad117abd54d28",
        "L3": "4e4b72fdfab1bb4a52da7a8bc221a71139f818686badd3b57f00d789bef935de",
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
        document = yaml.safe_load(
            (root / "bindings" / "architecture-identity-bindings.yaml").read_text()
        )
        return {b["sourceInstanceId"] for b in document["bindings"]}

    s0 = _materialize(tmp_path, target, "S0") / "declarations"
    bindings_file = "bindings/architecture-identity-bindings.yaml"

    l2 = _materialize(tmp_path, target, "L2") / "declarations"
    assert not (l2 / x).exists()
    if x_sid in bindings(s0):  # Airflow: X is bound, and exactly its binding is dropped
        assert bindings(l2) == bindings(s0) - {x_sid}
    else:  # Quarkus: X is the manifest, resolved by its own x-aip-service-id, so no edit
        assert (l2 / bindings_file).read_bytes() == (frozen / bindings_file).read_bytes()

    l4b = _materialize(tmp_path, target, "L4b") / "declarations"
    copy = scenario["steps"][STEPS.index("L4b")]["unbound_copy"]
    assert (l4b / copy["to"]).read_bytes() == (frozen / copy["from"]).read_bytes()
    assert not (l4b / x).exists()

    l6 = _materialize(tmp_path, target, "L6") / "declarations"
    inject = scenario["steps"][STEPS.index("L6")]["inject"]
    injected = yaml.safe_load((l6 / inject["file"]).read_text())
    original = yaml.safe_load((frozen / inject["file"]).read_text())
    assert injected.pop("x-aip-service-id") == inject["service_id"]
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
    # Finding F6: when every row is removed, the output is empty, exactly as cypher-shell prints an
    # empty result (no header), so a diff against the step's own output exits 0.
    only_x = 'type, source, target, key, owners\n"PROVIDES", "service:x", "op:x", "k2", ["sx"]\n'
    assert module.without_x(only_x, "sx") == ""
    assert module.without_x("", "sx") == ""


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


@pytest.mark.parametrize("target", sorted(PINNED))
def test_every_materialized_declaration_is_an_enumerated_candidate_name(tmp_path, target):
    # Slice 5 attempt 1 stopped because a bindings document name was not enumerated (see the
    # dossiers' profile.md "Revision history").
    from app.ingestion.filesystem_discoverer import CANDIDATE_FILENAMES

    for step in STEPS:
        workdir = _materialize(tmp_path, target, step)
        for path in workdir.rglob("*"):
            if path.is_file() and path.name not in {"config.yaml", "tombstones.yaml"}:
                relative = path.relative_to(workdir)
                assert path.name in CANDIDATE_FILENAMES, (step, relative)
                # <workdir>/<root>/<subdirectory>/<candidate name>: the discoverer's layout.
                assert len(relative.parts) == 3, (step, relative)


# The ledger's commit expectation per step (lifecycle/README.md): the committing steps must be
# commit-eligible inputs, and the non-committing ones must not be. Finding F7 was an input the ledger
# expected to commit although the contract rejects it; this catches such an input before any run.
COMMITS = {"S0": True, "L1": True, "L4a": False, "L4b": False, "L6": False, "L2": True, "R": True}
COMMITS |= {"L5": True, "L3": True}


@pytest.mark.parametrize("target", sorted(PINNED))
def test_every_step_is_an_input_whose_discovery_matches_the_ledger(tmp_path, target):
    from app.ingestion.orchestrator import run_filesystem_discovery
    from app.sources.model import FilesystemSourceConfig

    mutate = _mutate()
    scenario = mutate.load_scenario(target)
    x_sid = mutate.x_source_instance_id(scenario)
    for step in STEPS:
        workdir = _materialize(tmp_path, target, step)
        root = workdir / scenario["steps"][STEPS.index(step)]["root"]
        result = run_filesystem_discovery(
            FilesystemSourceConfig(id=scenario["declarations_source_id"], root=root)
        )
        assert result.commit_eligible is COMMITS[step], step
        if step in {"L2", "L5", "L3"}:  # X is omitted, and nothing else is rejected
            assert x_sid not in result.source_outcomes, step
            assert all(
                o.outcome.result.value.startswith("ACCEPTED")
                for o in result.source_outcomes.values()
            ), step
