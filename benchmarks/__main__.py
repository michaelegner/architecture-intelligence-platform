"""CLI entry point for the AIP snapshot/read-cost benchmark (v0.4.1 I3.1).

    uv run python -m benchmarks --profile smoke
    uv run python -m benchmarks --profile review-comparable
    uv run python -m benchmarks --profile smoke --candidate-sha <40hex> \\
        --out docs/release-validation/v0.4.1-read-cost-benchmark.json

Boots its own disposable Neo4j via Testcontainers (never the developer's normal AIP database) and
serves the real production app (`app.main.create_app()`) over real network HTTP, exactly the same
mechanism `tests/integration/test_mcp_independent_client_golden_path.py` already proves correct -
so this must be invoked from the repository root with Docker available, the same requirement
`evaluation`'s own CLI already carries.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import httpx
import jsonschema
from testcontainers.community.neo4j import Neo4jContainer

import app.main
from benchmarks.snapshot_read_cost import (
    InvalidCandidateSha,
    RevisionFenceMoved,
    is_dirty_worktree,
    render_human_summary,
    resolve_candidate_sha,
    run_profile,
)
from tests.integration.support.live_server import free_loopback_port, serve_over_real_http

SCHEMA_PATH = Path(__file__).resolve().parent / "snapshot_read_cost.schema.json"

EXIT_OK = 0
EXIT_VALIDATION_FAILED = 1
EXIT_INVALID_ARGS = 2


def _write_config(config_path: Path, *, base_url: str, port: int) -> None:
    config_path.write_text(
        "architecture_intelligence:\n"
        "  mcp:\n"
        f'    allowed-origins: ["{base_url}"]\n'
        f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
    )


def _neo4j_version(container: Neo4jContainer) -> str | None:
    image = getattr(container, "image", None)
    if isinstance(image, str) and ":" in image:
        return image.split(":", 1)[1]
    return None


def _run(*, profile: str, candidate_sha: str | None, dirty_worktree: bool | None, out: Path) -> int:
    try:
        resolved_sha = resolve_candidate_sha(candidate_sha)
    except InvalidCandidateSha as exc:
        print(f"invalid --candidate-sha: {exc}", file=sys.stderr)
        return EXIT_INVALID_ARGS

    resolved_dirty = dirty_worktree if dirty_worktree is not None else is_dirty_worktree()
    if resolved_dirty is None:
        resolved_dirty = True  # fail safe: unknown worktree state is treated as dirty

    with Neo4jContainer("neo4j:5") as container:
        driver = container.get_driver()
        try:
            os.environ["NEO4J_URI"] = container.get_connection_url()
            os.environ["NEO4J_USER"] = container.username
            os.environ["NEO4J_PASSWORD"] = container.password
            os.environ.setdefault("OPENAI_API_KEY", "")

            port = free_loopback_port()
            base_url = f"http://127.0.0.1:{port}"
            with tempfile.TemporaryDirectory(prefix="aip-benchmark-") as config_dir:
                config_path = Path(config_dir) / "config.yaml"
                _write_config(config_path, base_url=base_url, port=port)
                app.main.CONFIG_PATH = config_path

                real_app = app.main.create_app()
                with (
                    serve_over_real_http(real_app, port=port),
                    httpx.Client(
                        base_url=base_url, headers={"origin": base_url}, timeout=60.0
                    ) as client,
                ):
                    result = run_profile(
                        profile,
                        driver=driver,
                        client=client,
                        candidate_sha=resolved_sha,
                        dirty_worktree=resolved_dirty,
                        neo4j_version=_neo4j_version(container),
                    )
        except RevisionFenceMoved as exc:
            print(str(exc), file=sys.stderr)
            return EXIT_VALIDATION_FAILED
        finally:
            driver.close()

    schema = json.loads(SCHEMA_PATH.read_text())
    jsonschema.validate(instance=result, schema=schema)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(render_human_summary(result))
    print(f"\nwrote {out}")

    all_passed = all(
        point["structural_validation"] == "PASS" and point["semantic_validation"] == "PASS"
        for point in result["scale_points"]
    )
    return EXIT_OK if all_passed else EXIT_VALIDATION_FAILED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks")
    parser.add_argument("--profile", choices=["smoke", "review-comparable"], required=True)
    parser.add_argument(
        "--candidate-sha",
        default=None,
        help="explicit 40-hex candidate git SHA this run qualifies; defaults to current git HEAD",
    )
    parser.add_argument(
        "--dirty-worktree",
        dest="dirty_worktree",
        action="store_true",
        default=None,
        help="force dirty_worktree=true regardless of `git status` (e.g. when git isn't available)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("benchmark-result.json"),
        help="where to write the JSON result (default: ./benchmark-result.json)",
    )
    args = parser.parse_args(argv)
    return _run(
        profile=args.profile,
        candidate_sha=args.candidate_sha,
        dirty_worktree=args.dirty_worktree,
        out=args.out,
    )


if __name__ == "__main__":
    sys.exit(main())
