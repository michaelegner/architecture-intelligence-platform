"""Authoring-time CLI: prints independently-derived identity literals for a scenario, to be
hand-copied into its `expected_answer.json`. Never invoked by the live evaluation run - see
`canonical_json.py`'s module docstring.

    uv run python -m evaluation.architecture_answers.reference snapshot <scenario-dir>
    uv run python -m evaluation.architecture_answers.reference context-id <environment> <window_start> <window_end>
    uv run python -m evaluation.architecture_answers.reference claim-id <subject_id> <predicate> <object_id> <delivery_kind> <delivery_via_id>
    uv run python -m evaluation.architecture_answers.reference declared-evidence-id <source_type> <service_slug> [revision]
    uv run python -m evaluation.architecture_answers.reference observed-evidence-id <environment> <bucket_start> <subject_id> <relation_type> <object_id>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from testcontainers.community.neo4j import Neo4jContainer

from evaluation import fixture_setup
from evaluation.architecture_answers.reference import identities, snapshot

_DATABASE = "neo4j"


def _print_snapshot(scenario_dir: str) -> None:
    # Evidence.source_file (spec §18's allowlist) reflects the exact path string import_all_sources
    # was given verbatim - deliberately NOT resolved to an absolute path. An absolute,
    # checkout-location-specific path would make the printed fingerprint (and any expected_answer
    # .json literal frozen from it) unreproducible anywhere but this exact machine - invoke this
    # command with a path relative to the repo root, the same way every other caller
    # (evaluation/__main__.py's ANSWER_SCENARIOS_DIR, the test suite's SCENARIOS_DIR) does.
    scenario_path = Path(scenario_dir)
    with Neo4jContainer("neo4j:5") as container:
        driver = container.get_driver()
        try:
            fixture_setup.prepare_scenario(driver, database=_DATABASE, scenario_path=scenario_path)
            with driver.session(database=_DATABASE) as session:
                snapshot_id, model_revision = snapshot.fingerprint(
                    session, coverage_qualification_enabled=True
                )
        finally:
            driver.close()
    print(f"snapshot_id: {snapshot_id}")
    print(f"model_revision: {model_revision}")


def _print_context_id(environment: str, window_start: str, window_end: str) -> None:
    print(
        identities.context_id(
            environment=environment,
            window_start=datetime.fromisoformat(window_start),
            window_end=datetime.fromisoformat(window_end),
        )
    )


def _print_claim_id(
    subject_id: str, predicate: str, object_id: str, delivery_kind: str, delivery_via_id: str
) -> None:
    print(
        identities.claim_id(
            subject_id=subject_id,
            predicate=predicate,
            object_id=object_id,
            delivery_kind=delivery_kind,
            delivery_via_id=delivery_via_id,
        )
    )


def _print_declared_evidence_id(
    source_type: str, service_slug: str, revision: str | None = None
) -> None:
    print(identities.declared_evidence_id(source_type, service_slug, revision))


def _print_observed_evidence_id(
    environment: str, bucket_start: str, subject_id: str, relation_type: str, object_id: str
) -> None:
    print(
        identities.observed_evidence_id(
            environment=environment,
            bucket_start=datetime.fromisoformat(bucket_start),
            subject_id=subject_id,
            relation_type=relation_type,
            object_id=object_id,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evaluation.architecture_answers.reference")
    subparsers = parser.add_subparsers(dest="command", required=True)

    snap = subparsers.add_parser(
        "snapshot", help="prepare a scenario fixture, print its fingerprint"
    )
    snap.add_argument("scenario_dir")

    ctx = subparsers.add_parser("context-id")
    ctx.add_argument("environment")
    ctx.add_argument("window_start")
    ctx.add_argument("window_end")

    claim = subparsers.add_parser("claim-id")
    claim.add_argument("subject_id")
    claim.add_argument("predicate")
    claim.add_argument("object_id")
    claim.add_argument("delivery_kind")
    claim.add_argument("delivery_via_id")

    declared = subparsers.add_parser("declared-evidence-id")
    declared.add_argument("source_type")
    declared.add_argument("service_slug")
    declared.add_argument("revision", nargs="?", default=None)

    observed = subparsers.add_parser("observed-evidence-id")
    observed.add_argument("environment")
    observed.add_argument("bucket_start")
    observed.add_argument("subject_id")
    observed.add_argument("relation_type")
    observed.add_argument("object_id")

    args = parser.parse_args(argv)
    if args.command == "snapshot":
        _print_snapshot(args.scenario_dir)
    elif args.command == "context-id":
        _print_context_id(args.environment, args.window_start, args.window_end)
    elif args.command == "claim-id":
        _print_claim_id(
            args.subject_id,
            args.predicate,
            args.object_id,
            args.delivery_kind,
            args.delivery_via_id,
        )
    elif args.command == "declared-evidence-id":
        _print_declared_evidence_id(args.source_type, args.service_slug, args.revision)
    elif args.command == "observed-evidence-id":
        _print_observed_evidence_id(
            args.environment, args.bucket_start, args.subject_id, args.relation_type, args.object_id
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
