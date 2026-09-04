"""The exact immutable source revision (git commit SHA) an evaluation run qualifies (spec §10) -
resolved once per `run_suite` call and threaded as one explicit value through producer injection,
comparator verification, and the recorded result artifact, rather than independently re-derived at
different times by different components. Spec §27 names "producer build revision is missing or
mutable" as a named release blocker, and §28 requires I1 tests to prove that missing or placeholder
build provenance cannot qualify a release artifact - a hardcoded literal like `"0" * 40` is exactly
the placeholder that rule exists to catch, and silently trusting the ambient `git rev-parse HEAD` at
whatever moment each component happens to run is not meaningfully different from that: nothing
records *which* SHA was actually qualified, and the value is free to drift between the run that
produced the committed evidence and the commit that evidence ends up living in.

`python -m evaluation answers --candidate-sha <40hex>` is the real release-qualification path - an
explicit, frozen literal decided before the run starts. Omitting it falls back to the current git
HEAD, for ad-hoc/local runs where "whatever I have checked out" is an acceptable answer.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def current_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
        cwd=_REPO_ROOT,
    )
    return result.stdout.strip()


class InvalidCandidateSha(ValueError):
    """An explicit --candidate-sha was given but isn't a well-formed 40-hex git SHA."""


def resolve_candidate_sha(explicit: str | None = None) -> str:
    """The candidate SHA one `run_suite` call qualifies - `explicit` if given (validated as a real
    40-hex SHA, not just any string), otherwise the current git HEAD."""
    if explicit is None:
        return current_git_sha()
    if not _SHA_PATTERN.match(explicit):
        raise InvalidCandidateSha(f"not a well-formed 40-hex git SHA: {explicit!r}")
    return explicit
