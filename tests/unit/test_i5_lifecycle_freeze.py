"""Guards the frozen I5 Slice 4 inputs against drift: the lifecycle mutations, the lifecycle profile,
and the coverage-matrix fixture revisions (I5 §§9-10).

Nothing here imports into AIP. The tests materialize each frozen lifecycle step into a temporary
directory and check its content digest, and they check that the frozen dossiers stay untouched.
"""

import importlib.util
import json
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


RELEASED_PRODUCER_VERSION = "0.6.0"
I5_PRODUCER_VERSION = "0.4.2"

# v0.6.1 I1a/I1b moved snapshot canonicalization 3 -> 4 and added Broker facts (new always-present `brokers` key), which
# legitimately re-pins every scenario's frozen `snapshot_id`/`model_revision` (spec §5.3). The I5
# pin stays the identity at the I5 candidate, so the copy also reverts exactly those literals:
# current digest -> the digest the scenario carried at the I5 candidate (read from the frozen
# scenarios before the v4 re-pin). Anything else that changed in a scenario still fails the pin.
V4_REPIN_TO_I5_DIGEST = {
    "1bdb84f32dd309c183e62ccd300d8c68ef8c29374fb744c75489553328d8d2d7": (
        "8d3cbb8c8b728b4a73fe321cfd6aa54f55c53e0fa551b034926f9fb1f084dd79"
    ),
    "1fc238f213fa57720270258455bcee6a5822bdaa08f6061a8d7f3c9bb70a14a8": (
        "7e56b34b66794714178978c793a749284bf585dd569d030a62cbb2d0b804d2af"
    ),
    "262bf59d8c18ce9a55288022ea02b5d854789c2bb1491fdb9c17a2581567fee2": (
        "cdf1537bb253019b4c4613fa954f938bceda258c14cf338877153462dce4352e"
    ),
    "279e9730b644e87524e76cc3c506fad2ea2ffb56ec5b3870642e62b42342bf76": (
        "61e7161903c3604ef40e910040e5f25345cc14f448a07ab72a92baec98f47f62"
    ),
    "3a680b802f7bd79979998daf05939a27568496ca8021187afde20fa550015343": (
        "a2ddd774ad6fba41ae8d54750d5d1ec0147cd05a32fcfb15fb9d01b01b383134"
    ),
    "3c1394a93250a2945b795cfa4583a80fc13466553ea86f33aac605400c9c86ac": (
        "a789ba301268358e313849751a17072760e24631f7361f56dedde855df886690"
    ),
    "4b715bafe7df2d9319c38ab5db92ece3546004eb6ee82040a625af88e7f1c49a": (
        "ec6cf3e7cf2bc56bcfafb30e3748a543393dbea8cb0c574097713dd8f1481894"
    ),
    "515cea053a90789701bfee8957e7b2a26030876d3fe8dacbbe43593c8007f154": (
        "e6bb335554bd85c70035c63aa3d2a59fb7fedfd376c0b497576550d7233b0b3d"
    ),
    "51b9698e1521428ba9ff64563781387252faa971ccb046fb4762997ba53915e6": (
        "40af1984e44beef311daeadda930354ff432445527ffd58e05fd63dac0e4ce76"
    ),
    "5f52424f380f74835cac2782b8ac65f07d71e00944e5401b2cbe8dac8507b32d": (
        "020bce9d9fd248bbd7e0f11c65bd88876eb07baf748c0d3f9cf5f908da0267a3"
    ),
    "87fc23284e166e839983acdf39be84dd50a2a0dd84f777dfefc89d33339a9e5a": (
        "14eef652c468324f1e3dfe55387bbe9a6a0a6c0d5b79cd6e2183f29ce137cf67"
    ),
    "88ab84741174f5959b61654ed2cc2887570efc2d8b2f9cf82e0b9fcc100ddc4b": (
        "dc8e75fdebda954081059c96d17ae072ceec8c952261929e6276945c5f52e09c"
    ),
    "8d4d1540fc945eacec2444f7bec9f8540f43864b84f723fb11ede000480cb802": (
        "98325cc951d8a91f450615e504978de5ba136a6f90790d1eacd0ea13336a56f6"
    ),
    "9898d9daaa9e1a8afabce49085bd55d12252fdb8867708fa9117ee4bda215f76": (
        "bcb24b1a7620745578b4e82f7a6e05cda260b39a5da879d4a8c8fcd1a79366d8"
    ),
    "99cb25a154856bf2a6451786b281d864d41d345c40cd6874da46a2f7b0b24a09": (
        "60c6ce7ac17e7ff2f287139b593e1cca78bd5918ed0c0243add3793c505f054e"
    ),
    "b64eb96013b066d53db29415042143487d380e42c7e47e6f516ca096247d53ca": (
        "06125cc5dabfbc5ed755f0aa5227af044f4a989ce52f9ff0d4e6bdd3c79241bd"
    ),
    "b8127e7569ee844ea2fcd1af05ed17363a3fb6a42d254ea8e804c756634b2737": (
        "2339182b5d89574d2662c1121d45b4d45f304e722fa0dbc7aa89f508572ffd45"
    ),
    "c6ff0c8cbc9b45643959e19cf63bebb9075e24fa6f8f2816c13cd5c7107c25c3": (
        "251edaee1ae62c23c62502e8e6e9a953cb36ebaa0f64138ea1687847a628456a"
    ),
    "d937f3350a384c994b9fdab38d22b148b0f13a13f225fe99c791a786471f1007": (
        "80435ac3525e9bd95af0903bc6a868cd4ee71f12f5272e16ec5f14510194972a"
    ),
    "da0595ec6f473989d107c3af7cd01baed2bd1ec75e911cd802c7b65737ab41f2": (
        "d75d4df52e05cb8cbb9696f25d8b07d2a97a19225da48e91ca9e115f7ffe32fa"
    ),
    "e0911799822d74cea3a6641eb18f8df86f66df7e90929957d04a7dcb9c61e133": (
        "513f953708386eafcd51af89ec901a1c34d877d9fbe6e7bb1a2b7d992637efa6"
    ),
    "e11e9eace70ddf916906f4d660340449a7650d976b3ccdbfe9eeb1514a235b62": (
        "3728800bd4780e6492aa3ac7888d03041d5c6aa16955763951591aeba760e5a6"
    ),
}


def _scenarios_as_at_the_i5_candidate(scenarios: Path, workdir: Path) -> Path:
    """v0.5.0 I6 §6/§9: release preparation may change the evaluation scenarios'
    `producer.version` and nothing else. The I5 pin in coverage-matrix.md stays the identity at the
    I5 candidate `aa04a15`, and the frozen I5 record is not edited. This reverts exactly that one
    permitted change in a copy, one occurrence per expected answer, and proves it is the producer
    field. The unchanged pin must then match, so any other scenario change still fails."""
    copy = workdir / "scenarios"
    for source in sorted(scenarios.rglob("*")):
        if not source.is_file() or "__pycache__" in source.parts:
            continue
        target = copy / source.relative_to(scenarios)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if source.name == "expected_answer.json":
            text = data.decode()
            released = f'"version": "{RELEASED_PRODUCER_VERSION}"'
            assert text.count(released) == 1, source
            assert json.loads(text)["producer"]["version"] == RELEASED_PRODUCER_VERSION, source
            data = text.replace(released, f'"version": "{I5_PRODUCER_VERSION}"').encode()
        if source.name in ("expected_answer.json", "request.yaml"):
            text = data.decode()
            for current, at_i5 in V4_REPIN_TO_I5_DIGEST.items():
                text = text.replace(current, at_i5)
            data = text.encode()
        target.write_bytes(data)
    return copy


def test_coverage_matrix_fixture_digests_match_the_files_on_disk(tmp_path):
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
        tree = ROOT / path
        if path == "evaluation/architecture_answers/scenarios":
            tree = _scenarios_as_at_the_i5_candidate(tree, tmp_path)
        # The one documented algorithm (coverage-matrix.md names mutate.py::tree_digest).
        assert mutate.tree_digest(tree, exclude=frozenset()) == digest, path


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
