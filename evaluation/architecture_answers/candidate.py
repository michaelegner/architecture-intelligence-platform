"""The exact immutable source revision (git commit SHA) this evaluation run is qualifying (spec
§10) - computed directly from git, never a placeholder literal. Spec §27 names "producer build
revision is missing or mutable" as a named release blocker, and §28 explicitly requires I1 tests to
prove that missing or placeholder build provenance cannot qualify a release artifact - a hardcoded
literal like `"0" * 40` is exactly the placeholder that rule exists to catch.

Asked independently by both `runner.py` (what it injects into the real service call) and
`comparator.py` (what it independently verifies the answer against) rather than one trusting the
other's computation - there's no "shared defect" risk in doing so twice, since neither side
reimplements a formula; both just ask git the same trustworthy question.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
    )
    return result.stdout.strip()
