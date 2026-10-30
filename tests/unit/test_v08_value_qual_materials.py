"""v0.8 value qualification: the frozen materials (spec §4.4, §5). The cards differ from the v0.8
card only in the passages of spec §4.4; the settings give each type its access; `matrix.json` equals
the Step 1 table; every frozen file has its digest."""

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))
sys.path.insert(0, str(REPO / "harness/v08/value-qual"))

import make_cards
import vq_format
import vq_settings

EVIDENCE = vq_format.EVIDENCE
STEP1 = REPO / "docs/specifications/evaluation/v08-showcase-value-qualification-step1.md"
V08_CARD = make_cards.V08_CARD.read_text()
AIP_TEXT = "connected as the MCP server `aip`"


def card(card_type: str) -> str:
    return vq_format.card(card_type).read_text()


@pytest.mark.parametrize("card_type", vq_format.TYPES)
def test_the_committed_cards_and_settings_are_what_the_generator_builds(card_type, tmp_path):
    subprocess.run(
        [sys.executable, str(make_cards.HERE / "make_cards.py"), str(tmp_path / "cards")],
        check=True,
    )
    assert (tmp_path / f"cards/task-card.{card_type}.md").read_text() == card(card_type)
    built = (tmp_path / f"settings/settings.{card_type}.json").read_text()
    assert built == (EVIDENCE / f"settings/settings.{card_type}.json").read_text()


@pytest.mark.parametrize("card_type", vq_format.TYPES)
def test_each_card_keeps_the_shared_v08_text(card_type):
    text = card(card_type)
    for heading in ("Goal", "Constraints"):
        assert make_cards._section(V08_CARD, heading) in text
    assert "Execution session" not in text and "amendment-schema" not in text
    assert ("Requests" in text) == card_type.startswith("T")
    assert (AIP_TEXT in text) == card_type.endswith("+")
    if card_type.startswith("F"):
        assert "`src/ecommerce-infrastructure/environments/local/values/`" in text
        assert "run one command per Bash call" in text
    else:
        assert "no cluster or broker access" in text
        assert "ecommerce-infrastructure`" not in text.split("## Requests")[1]


def test_the_cards_of_one_setting_differ_only_in_the_aip_paragraph():
    for setting in "FT":
        with_aip, without = card(f"{setting}+").splitlines(), card(f"{setting}-").splitlines()
        removed = [line for line in with_aip if line not in without]
        assert removed and all(
            line in make_cards._section(V08_CARD, "Environment") for line in removed
        )
        assert [line for line in without if line not in with_aip] == []


@pytest.mark.parametrize("card_type", vq_format.TYPES)
def test_the_card_schemas_parse_and_accept_the_fixture_outputs(card_type):
    sys.path.insert(0, str(Path(__file__).parent))
    import v08_value_qual_fixtures as fixtures

    path = vq_format.card(card_type)
    for name in ("plan-schema", "answers-schema"):
        assert vq_format.schema(name, path)["$schema"].endswith("2020-12/schema")
    assert vq_format._errors(fixtures.perfect_plan(), "plan-schema", path) == []
    assert vq_format._errors(fixtures.perfect_answers(), "answers-schema", path) == []
    has_requests = "```json requests-schema" in path.read_text()
    assert has_requests == card_type.startswith("T")


def test_the_plan_schema_changes_only_the_evidence_fields():
    v08 = vq_format.schema("plan-schema", make_cards.V08_CARD)
    new = vq_format.schema("plan-schema", vq_format.card("F+"))
    old_item, new_item = (s["properties"]["items"]["items"] for s in (v08, new))
    kept = set(old_item["properties"]) - {"architecture_citations", "implementation_justification"}
    assert set(new_item["properties"]) == kept | {"evidence"}
    assert all(old_item["properties"][k] == new_item["properties"][k] for k in kept)
    assert v08["properties"]["allow_lists"] == new["properties"]["allow_lists"]


def test_settings_give_each_type_its_access():
    for card_type in vq_format.TYPES:
        settings = json.loads((EVIDENCE / f"settings/settings.{card_type}.json").read_text())
        allow, deny = settings["permissions"]["allow"], settings["permissions"]["deny"]
        assert ("mcp__aip" in allow) == card_type.endswith("+")
        assert ("mcp__aip" in deny) == card_type.endswith("-")
        assert settings["enableAllProjectMcpServers"] == card_type.endswith("+")
        for path in ("src", "aip", "package", "catalogue"):
            assert f"Read(/__RUN_HOME__/{path}/**)" in deny
        assert "Read(/__OTHER_SESSIONS__/**)" in deny
        commands = [r for r in allow if r.startswith("Bash(")]
        broker = [r for r in commands if re.search(r"docker|kubectl|helm|rpk|kafka", r)]
        assert bool(broker) == card_type.startswith("F")
        if card_type.startswith("T"):
            assert {"Bash(docker:*)", "Bash(kubectl:*)", "Bash(helm:*)", "Bash(rpk:*)"} <= set(deny)
        writes = {r for r in allow if r.startswith("Edit(")}
        assert writes == {f"Edit(/__WORKSPACE__/{n})" for n in vq_settings.outputs(card_type)}


def test_render_fills_every_placeholder():
    rendered = vq_settings.render(
        vq_settings.template("T-"),
        run_home="/run",
        workspace="/run/sessions/T-_r1/workspace",
        config="/run/sessions/T-_r1/claude",
        withheld=["/code/aip"],
        operator_state=["/home/op/.claude", "/home/op/.claude.json"],
        other_sessions=["/run/sessions/F+_r1"],
    )
    deny = rendered["permissions"]["deny"]
    assert "Read(//run/src/**)" in deny and "Read(//run/aip/**)" in deny
    assert "Read(//run/sessions/F+_r1/**)" in deny
    assert "Read(//home/op/.claude/**)" in deny and "Read(//home/op/.claude.json)" in deny
    assert "Edit(//run/sessions/T-_r1/workspace/requests.json)" in rendered["permissions"]["allow"]
    with pytest.raises(ValueError, match="unfilled"):
        vq_settings.render(
            {"permissions": {"allow": ["Edit(/__NEW__/x)"], "deny": []}},
            run_home="/r", workspace="/w", config="/c", withheld=[], operator_state=[], other_sessions=[],
        )  # fmt: skip


def _step1_table() -> dict[int, list[str]]:
    rows = {}
    for line in STEP1.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and cells[0].isdigit():
            rows[int(cells[0])] = [c.split()[0] for c in cells[3:9]]
    return rows


def test_matrix_json_equals_the_step1_table_cell_for_cell():
    matrix = json.loads((EVIDENCE / "matrix.json").read_text())
    table = _step1_table()
    assert sorted(table) == [r["row"] for r in matrix["rows"]] == list(range(1, 10))
    for row in matrix["rows"]:
        assert list(row["cells"].values()) == table[row["row"]]
        documents = row["cells"]["documents"]
        assert row["documented"] == {"Y": "yes", "N": "no", "P": "partly"}[documents]


def test_matrix_rows_are_the_i2_rows_and_every_location_parses():
    matrix = json.loads((EVIDENCE / "matrix.json").read_text())
    c1 = json.loads((REPO / "docs/specifications/0.8.0/i2-vectors/c1-expected.json").read_text())
    want = sorted(
        (r["consumer_service_id"].removeprefix("service:"), r["topic_name"], r["crossing"])
        for r in c1["rows"]
    )
    assert sorted((r["consumer"], r["topic"], r["crossing"]) for r in matrix["rows"]) == want
    locations = [
        loc
        for r in matrix["rows"]
        for groups in r["support"].values()
        for group in groups
        for loc in group
    ] + [p for r in matrix["rows"] for p in r["partial"]]
    locations += [loc for groups in matrix["producers"].values() for g in groups for loc in g]
    assert all(vq_format.location(loc) for loc in locations)
    team = json.loads((EVIDENCE / "catalogue/r2-list.json").read_text())["team_scoped"]
    for r in matrix["rows"]:  # a Y in team source has a support entry inside the team repositories
        team_entries = [
            g for g in r["support"]["binding"] if all(loc.split("/")[0] in team for loc in g)
        ]
        assert bool(team_entries) == (
            r["cells"]["team_source"] == "Y" or r["cells"]["documents"] == "Y"
        )


def test_the_comprehension_key_is_the_crossing_rows_of_the_matrix():
    key = json.loads((EVIDENCE / "comprehension-key.json").read_text())
    matrix = json.loads((EVIDENCE / "matrix.json").read_text())
    crossing = [r["row"] for r in matrix["rows"] if r["crossing"] in ("INBOUND", "OUTBOUND")]
    assert key["q2"]["crossing_rows"] == crossing
    assert sorted(key["q4"]) == sorted(str(n) for n in crossing)
    assert len(key["q5"]) == 4


def test_the_r2_list_is_every_other_repository_except_infrastructure():
    listing = json.loads((EVIDENCE / "catalogue/r2-list.json").read_text())
    freeze = (REPO / "docs/specifications/0.7.2/i2-evidence/sokol111/freeze.md").read_text()
    every = set(re.findall(r"`Sokol111/([\w.-]+)`", freeze))
    assert len(every) == 16
    assert set(listing["repositories"]) == every - set(listing["team_scoped"]) - {
        "ecommerce-infrastructure"
    }
    assert listing["excluded"] == ["ecommerce-infrastructure"]


def test_r1_is_the_frozen_v08_capture():
    v08 = REPO / "docs/specifications/0.8.0/i4-evidence/raw/S1-13-groups-describe.txt"
    assert (EVIDENCE / "catalogue/R1.txt").read_bytes() == v08.read_bytes()


def test_sha256sums_cover_every_frozen_file():
    lines = (EVIDENCE / "SHA256SUMS").read_text().splitlines()
    listed = {}
    for line in lines:
        digest, name = line.split(maxsplit=1)
        listed[name] = digest
        assert hashlib.sha256((EVIDENCE / name).read_bytes()).hexdigest() == digest, name
    frozen = {
        str(p.relative_to(EVIDENCE))
        for p in EVIDENCE.rglob("*")
        if p.is_file() and p.name not in ("SHA256SUMS", "README.md")
    }
    assert frozen <= set(listed)
    plan_key = "../../0.8.0/i4-evidence/plan-key.json"
    pinned = (REPO / "docs/specifications/0.8.0/i4-evidence/plan-key.sha256").read_text().split()[0]
    assert listed[plan_key] == pinned
