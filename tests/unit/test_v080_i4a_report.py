"""v0.8 I4a: the report generator (I4 spec §8) on synthetic frozen inputs.

The same inputs give the same bytes; the four parts and the five questions are there; there is one
requirement chain per INBOUND/OUTBOUND row after the wave, linked to its key item and plan items;
the disclosures are there; the wording rules hold for the report's own text, and the agent's quoted
words are exempt.
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "harness/v08/i4"))

import report

from .v080_i4_plans import (
    EXPECTED_AFTER,
    after_answer,
    answer_of,
    perfect_plan,
    recording,
    write_manifest,
)


def manifest(tmp_path: Path, plan_md: str = "The plan.\n") -> Path:
    rec = recording()
    before = answer_of(rec["agent_requests"][0]["answer"]["data"]["rows"])
    return write_manifest(tmp_path, before, after_answer(), perfect_plan(), rec, plan_md)


def test_same_inputs_same_bytes(tmp_path):
    path = manifest(tmp_path)
    assert report.render(path) == report.render(path)


def test_four_parts_and_five_questions(tmp_path):
    html = report.render(manifest(tmp_path))
    for heading in ("1. Before", "2. Insight", "3. Agent", "4. After"):
        assert f"<h2>{heading}" in html
    assert re.findall(r'<p class="question">\((\d)\)', html) == ["1", "2", "3", "4", "5"]


def test_one_chain_per_crossing_row_after_the_wave(tmp_path):
    manifest(tmp_path)
    inputs = {
        name: json.loads((tmp_path / f"{name}.json").read_text())
        for name in ("before", "after", "scoring", "citations", "functional_test")
    }
    chains = report.chains(
        inputs | {"replication": [], "lag": []}, report.load_key(), perfect_plan()
    )
    crossing = [r for r in EXPECTED_AFTER["rows"] if r["crossing"] in ("INBOUND", "OUTBOUND")]
    assert len(chains) == len(crossing) == 6
    by_topic = {c["row"]["topic_name"]: c for c in chains}
    assert by_topic["catalog.category.events"]["key"]["id"] == "K3"
    assert [i["id"] for i in by_topic["tenant.tenant.events"]["plan_items"]] == ["m-tenant"]
    assert by_topic["catalog.attribute.events"]["proof_b"] == "COVERED"
    assert by_topic["tenant.tenant.events"]["verification"]["functional"].endswith("PASSED")


def test_disclosures_and_independence(tmp_path):
    html = report.render(manifest(tmp_path))
    for text in (
        "confirmed promises by assumption",
        "authored for the showcase",
        "Logto pinned",
        "task card",
        "Transcript audit",
    ):
        assert text in html


def test_wording_rules_hold_and_agent_quotes_are_exempt(tmp_path):
    html = report.render(
        manifest(tmp_path, plan_md="We stop Catalog during the cut-over; its dependencies stay.\n")
    )
    assert "during the cut-over" in html  # the agent's words, quoted
    assert report.wording_problems(html) == []
    own_text = html.replace(
        "<h2>Proof boundaries</h2>", "<h2>Proof boundaries during the move</h2>"
    )
    assert report.wording_problems(own_text) == ["during"]


def test_no_live_attachment_here(tmp_path):
    html = report.render(manifest(tmp_path))
    section = html[html.index("No live attachment here") :]
    assert (
        "ecommerce-catalog-service &times; <code>tenant.tenant.events</code> on Redpanda" in section
    )


def test_every_plan_item_with_its_citations(tmp_path):
    """Parent §6 part 3: the wave plan, each item linked to the AIP claims it cites."""
    html = report.render(manifest(tmp_path))
    section = html[
        html.index("The plan, item by item") : html.index("The agent's plan, as written")
    ]
    for item in perfect_plan()["items"]:
        assert f'<span class="agent">{item["id"]}: ' in section
    assert section.count('class="SUPPORTS"') == 6  # the six citations of K1-K4's items
    assert section.count('class="JUSTIFIED"') == len(perfect_plan()["items"])


def _rewrite(tmp_path: Path, name: str, change) -> None:
    path = tmp_path / f"{name}.json"
    content = json.loads(path.read_text())
    change(content)
    path.write_text(json.dumps(content))


def test_a_refused_report_answer_stops(tmp_path):
    path = manifest(tmp_path)
    _rewrite(
        tmp_path,
        "after",
        lambda c: c["report_request"].update(
            answer={"outcome": "NOT_ANSWERED", "data": None, "limitations": []}
        ),
    )
    with pytest.raises(SystemExit, match="refused"):
        report.render(path)


def test_audit_hits_are_unresolved_without_an_evidenced_waiver(tmp_path):
    path = manifest(tmp_path)
    hit = {
        "kind": "WITHHELD_PATH",
        "session": "execution",
        "line": 7,
        "tool": "Bash",
        "detail": "x",
        "denied": True,
    }
    _rewrite(tmp_path, "audit", lambda c: c.update(hits=[hit], clean=False))
    assert "1 unresolved hit(s): the run is not valid" in report.render(path)
    waiver = {
        "session": "execution",
        "line": 7,
        "kind": "WITHHELD_PATH",
        "evidence": "the denied tool_result",
    }
    _rewrite(tmp_path, "agent", lambda c: c.update(waivers=[waiver]))
    html = report.render(path)
    assert "waived by the owner" in html and "not valid" not in html


def test_a_row_without_a_live_attachment_after_counts(tmp_path):
    """Image x catalog.product.events stays on Redpanda as PROMISED_NOT_OBSERVED, with no group."""
    html = report.render(manifest(tmp_path))
    section = html[html.index("No live attachment here") :]
    assert (
        "ecommerce-image-service &times; <code>catalog.product.events</code> on Redpanda" in section
    )
