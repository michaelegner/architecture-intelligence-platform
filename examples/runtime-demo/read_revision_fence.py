"""v0.4.2 I3 - read-only revision-fence CLI helper (spec
`docs/specifications/0.4.2/i3-client-qualification-and-release-preparation.md` §6.3).

Runs read-only, inside the already-running `architecture-intelligence` container, alongside
`check_fixture_state.py`:

    "${COMPOSE[@]}" exec -T architecture-intelligence python \\
        examples/runtime-demo/read_revision_fence.py --json

I3's actual-client qualification procedure (spec §6.2/§6.12) reads `(:AipInternalState).revision`
before and after each client run to prove the client made zero graph writes, independent of whether
the canonical snapshot happens to look the same afterward. This helper is that one read, factored out
of `check_fixture_state.py` rather than requiring every caller to run the full fixture classifier just
to see the fence value.

It performs exactly one read of one scalar in one Bolt query, which is already atomic with respect to
that value - unlike `check_fixture_state.py`'s composite read (whole-database counts, canonical state,
and a separate `get_architecture_drift` call, each its own round trip), this helper has nothing that
could land "between" reads, so it does not need that file's bounded discard-and-retry loop.

A missing `(:AipInternalState)` singleton is a legitimate state on a virgin/EMPTY database (spec
§15.2), not a fencing failure, so it is reported as `{"revision": null}` with exit code 0 rather than
as an error - "fail safely on missing/invalid revision state" (spec §6.3) means never crash or attempt
repair, not that a legitimately empty fence must look like a script failure to a caller checking exit
codes. This helper cannot distinguish a legitimately empty database from a corrupted/partial one (both
raise the same `RevisionSingletonMissing` from `read_revision`) - a caller needing that distinction
must use `check_fixture_state.py`'s full EMPTY/COMPLETE/PARTIAL_OR_INCOMPATIBLE classification instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Invoked as `python examples/runtime-demo/read_revision_fence.py`, which puts only this file's own
# directory on sys.path - put the repo root back on sys.path explicitly so the `app.*` imports below
# resolve regardless of invocation style (same fixup as check_fixture_state.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.graph.repository import build_driver, open_session
from app.graph.revision_fence import RevisionSingletonMissing, read_revision
from app.settings import load_settings

_CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.yaml"))


def read_revision_fence(driver, *, database: str) -> dict[str, int | None]:
    """The Neo4j-backed half of this tool, factored out from `run()` so integration tests can drive
    it directly against a real (e.g. testcontainers) driver without going through `load_settings`'s
    environment-variable contract - same split as `check_fixture_state.py`'s `classify_fixture`."""
    with open_session(driver, database=database, read_only=True) as session:
        try:
            return {"revision": read_revision(session)}
        except RevisionSingletonMissing:
            return {"revision": None}


def run() -> dict[str, int | None]:
    settings = load_settings(_CONFIG_PATH)
    driver = build_driver(
        settings.config.graph.uri, settings.secrets.neo4j_user, settings.secrets.neo4j_password
    )
    try:
        return read_revision_fence(driver, database=settings.config.graph.database)
    finally:
        driver.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        required=True,
        help="Emit the revision fence as JSON to stdout (currently the only supported output mode).",
    )
    parser.parse_args(argv)

    result = run()
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
