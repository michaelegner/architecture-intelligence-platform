"""The v0.7 cost rerun on the exact I4 candidate (I4 spec §3, §8; decision record D1, D8).

    python -m evaluation.i4.api_usage_cost_run --candidate-sha <sha> --out <path.json>

`benchmarks/api_usage_cost.py` is the I3 measurement tool and records only its own commit. An I4 cost
artifact must also verify the exact candidate and carry the candidate's check-run identity, so this
wrapper runs the same measurement through the I4 identity machinery: the candidate is verified
against a clean `HEAD` that descends from the v0.6 baseline, the producer build revision must equal
it (and both pinned environment variables), the identity block of `benchmarks.i4_metadata` is added
with the v0.7 input pins, and the CI check-runs of that SHA are read from the API and judged by the
same rules as the qualification report. The cost is evidence, not an SLO; a CI blocker is recorded
in the artifact and the exit code, never hidden."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from benchmarks import api_usage_cost, i4_metadata
from evaluation.i4.__main__ import ROOT, ci_blockers, verify_candidate
from evaluation.i4.profiles import V07

REPOSITORY = "michaelegner/architecture-intelligence-platform"
PIN_ROOTS = (
    ROOT / "benchmarks",
    ROOT / "schemas/architecture_intelligence/v0.7",
    ROOT / "docs/specifications/0.7.0",
    ROOT / "evaluation/i4",
)


def check_runs(candidate_sha: str) -> tuple[list[dict] | None, str | None]:
    """The check-runs of the candidate SHA from the API (never `gh pr checks`)."""
    completed = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{REPOSITORY}/commits/{candidate_sha}/check-runs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        return None, completed.stderr
    return [c for page in json.loads(completed.stdout) for c in page["check_runs"]], None


def ci_section(candidate_sha: str) -> tuple[dict, list[str]]:
    """The artifact's CI block and its blockers, judged by the qualification report's rules."""
    runs, error = check_runs(candidate_sha)
    if runs is None:
        return {"error": error, "blockers": ["exact-SHA CI query failed"]}, [
            "exact-SHA CI query failed"
        ]
    blockers = ci_blockers(runs, candidate_sha, V07.required_ci_checks)
    checks = [{k: c[k] for k in ("id", "name", "status", "conclusion", "head_sha")} for c in runs]
    return {"checks": checks, "blockers": blockers}, blockers


def main(argv: list[str] | None = None) -> int:
    from testcontainers.community.neo4j import Neo4jContainer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--profile", choices=sorted(api_usage_cost.PROFILES), default="i3")
    args = parser.parse_args(argv)
    verify_candidate(args.candidate_sha)  # raises before Docker on a wrong or dirty identity
    producer = i4_metadata.producer(args.candidate_sha)
    with Neo4jContainer(
        "neo4j:5.26.32@sha256:f1e52d4dc6da122468c4a3c1050a4f5e117f6d3268625237c34d49166f0d6082"
    ) as container:
        driver = container.get_driver()
        try:
            result = api_usage_cost.run(args.profile, driver, producer)
            assert result["commit"] == args.candidate_sha and not result["dirty_worktree"]
            result.update(
                i4_metadata.metadata(
                    args.candidate_sha,
                    producer,
                    container,
                    {"profile": args.profile, "page_limit": api_usage_cost.PAGE_LIMIT},
                    pin_roots=PIN_ROOTS,
                    pin_files=(),
                    skip_pins=("-cost.json",),
                )
            )
        finally:
            driver.close()
    result["ci"], blockers = ci_section(args.candidate_sha)
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.out.write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return int(bool(blockers))


if __name__ == "__main__":
    raise SystemExit(main())
