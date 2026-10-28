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
