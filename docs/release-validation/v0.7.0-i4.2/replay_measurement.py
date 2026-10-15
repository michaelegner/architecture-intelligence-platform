"""v0.7.0 I4.2: selected-source (APISIX) import/replay cost and association rates (I4 spec §8).

Run from a clean checkout of the exact candidate, with that checkout on PYTHONPATH:

    PYTHONPATH=. uv run python replay_measurement.py --candidate-sha <sha> --out replay-measurement.json

It uses only the frozen replay path of `evaluation.i4.apisix_replay` (the committed real captures,
imported through `run_all_configured_sources`); it changes no qualification code, expectation or
fixture, and asserts nothing about answers (qualification is the A/B report). For each of REPEATS
repetitions it empties a disposable Neo4j, times the import of revision R1 (from an empty graph)
and then of R2 (an authoritative update), and reads the canonical state after each. The
association counts come from the state of the last repetition (they are identical in every
repetition: the script checks that). Evidence, not an SLO."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path

from testcontainers.community.neo4j import Neo4jContainer

from app.graph.schema import ensure_schema
from evaluation.i4 import apisix_replay as replay

NEO4J = "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
REPEATS = 5


def counts(state: dict) -> dict:
    usage = state["api_usage_v1"]
    rows = usage["qualification_rows"]
    return {
        "routes": len(state["gateway_configuration_v1"]["routes"]),
        "consumers": len(state["gateway_configuration_v1"]["consumers"]),
        "configured_access": len(state["gateway_configuration_v1"]["configured_access"]),
        "mapping_entries": len(usage["mapping_entries"]),
        "route_operation": dict(Counter(r["operation"] for r in usage["route_operation"])),
        "target_service": dict(Counter(r["target"] for r in usage["target_service"])),
        "route_coverage": dict(Counter(r["coverage"] for r in usage["coverage"])),
        "qualification_rows": len(rows),
        "configured_status": dict(Counter(r["configured_status"] for r in rows)),
        "usage_status": dict(Counter(r["usage_status"] for r in rows)),
        "observed_interactions": len(usage["interactions"]),
        "attributions": len(usage["attributions"]),
        "consumer_outcome": dict(Counter(r["consumer_outcome"] for r in usage["attributions"])),
        "route_outcome": dict(Counter(r["route_outcome"] for r in usage["attributions"])),
        "series": len(usage["series"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert head == args.candidate_sha, "the checkout is not the candidate"
    assert not subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], text=True
    ), "the checkout is not clean"
    timings: dict[str, list[float]] = {"r1_from_empty": [], "r2_update": []}
    observed = []
    with Neo4jContainer(NEO4J) as container:
        driver = container.get_driver()
        for _ in range(REPEATS):
            with driver.session(database=replay.DATABASE) as session:
                session.run("MATCH (n) DETACH DELETE n").consume()
                ensure_schema(session)
            with tempfile.TemporaryDirectory(prefix="aip-i4-measure-") as work:
                start = time.perf_counter()
                replay.import_revision(driver, "r1", Path(work))
                timings["r1_from_empty"].append(time.perf_counter() - start)
                first = counts(replay.read_state(driver))
                start = time.perf_counter()
                replay.import_revision(driver, "r2", Path(work))
                timings["r2_update"].append(time.perf_counter() - start)
                second = counts(replay.read_state(driver))
            observed.append({"r1": first, "r2": second})
    assert all(item == observed[0] for item in observed), (
        "association counts differ between repeats"
    )
    result = {
        "benchmark": "i4-apisix-replay-measurement",
        "candidate_sha": head,
        "verified_head": head,
        "dirty_worktree": False,
        "container_image": NEO4J,
        "repeats": REPEATS,
        "scope": "run_all_configured_sources over the examples directory and the committed real "
        "APISIX configuration capture and measurement fixture of the revision",
        "timings_seconds": {
            name: {
                "median": round(statistics.median(values), 3),
                "min": round(min(values), 3),
                "max": round(max(values), 3),
                "all": [round(v, 3) for v in values],
            }
            for name, values in timings.items()
        },
        "manual_mappings_supplied": 0,
        "state": observed[0],
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
