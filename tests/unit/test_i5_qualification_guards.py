"""Qualification must reject missing independent adoption or corrupted source evidence."""

import hashlib
import runpy
from pathlib import Path

import pytest

from evaluation.i5.checks import facts_from_dossier

TOOLS = Path("harness/locality-capture/replay")


def test_unadopted_oracle_is_rejected(tmp_path):
    dossier = tmp_path / "expected.md"
    dossier.write_text("**Review/adoption:** PENDING\n```json\n{}\n```\n")
    with pytest.raises(AssertionError, match="owner adoption"):
        facts_from_dossier(dossier)


def test_changed_source_bytes_are_rejected(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS.resolve()))
    helper = runpy.run_path(str(TOOLS / "expected_actual.py"))
    raw = tmp_path / "recording.jsonl"
    raw.write_bytes(b"original\n")
    checksum = hashlib.sha256(raw.read_bytes()).hexdigest()
    (tmp_path / "SHA256SUMS").write_text(f"{checksum}  recording.jsonl\n")
    raw.write_bytes(b"changed\n")
    with pytest.raises(AssertionError, match=r"recording\.jsonl"):
        helper["verified_hashes"](tmp_path)
