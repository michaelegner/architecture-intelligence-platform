"""v0.4.1 I3.1 - spec `docs/specifications/0.4.1/i3-hardening-qualification-and-release.md` §17
items 9-10: safe disposable-Neo4j seed/cleanup lifecycle against the shared session-scoped
`driver`/`neo4j_container` fixtures (`tests/integration/conftest.py`), and one real smoke
execution of the benchmark harness through production snapshot/fingerprint code and the real MCP
dependency path (via the extracted `tests/integration/support/live_server.py` helper). The
expensive `review-comparable` profile never runs here (spec §17's explicit CI exclusion) - only
`benchmarks.snapshot_read_cost.SMOKE_PROFILE`, invoked through the standalone CLI during candidate
qualification instead."""

from __future__ import annotations

import httpx
import pytest

import app.main
from app.graph.repository import open_session
from benchmarks.snapshot_read_cost import (
    SMOKE_PROFILE,
    build_fixture_plan,
    resolve_candidate_sha,
    run_profile,
    seed_scale_point,
    verify_structural_counts,
    wipe_database,
)

from .support.live_server import free_loopback_port, serve_over_real_http

DATABASE = "neo4j"


@pytest.fixture(autouse=True)
def clean_database(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    yield


@pytest.fixture
def benchmark_app_client(driver, neo4j_container, tmp_path, monkeypatch):
    """The same real-production-app-over-real-HTTP mechanism
    `tests/integration/test_mcp_independent_client_golden_path.py` proves correct, reused here so
    the benchmark's own `get_service_dependencies` timing leg crosses the real MCP boundary rather
    than an isolated harness (spec R2)."""
    monkeypatch.setenv("NEO4J_URI", neo4j_container.get_connection_url())
    monkeypatch.setenv("NEO4J_USER", neo4j_container.username)
    monkeypatch.setenv("NEO4J_PASSWORD", neo4j_container.password)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    port = free_loopback_port()
    base_url = f"http://127.0.0.1:{port}"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "architecture_intelligence:\n"
        "  mcp:\n"
        f'    allowed-origins: ["{base_url}"]\n'
        f'    allowed-hosts: ["127.0.0.1:{port}"]\n'
    )
    monkeypatch.setattr(app.main, "CONFIG_PATH", config_path)

    real_app = app.main.create_app()
    with (
        serve_over_real_http(real_app, port=port),
        httpx.Client(base_url=base_url, headers={"origin": base_url}, timeout=30.0) as client,
    ):
        yield client


def test_seed_scale_point_produces_exactly_the_planned_structural_delta(driver):
    plan = build_fixture_plan(SMOKE_PROFILE, 0)
    counts_after_target, counts_after_unrelated = seed_scale_point(driver, plan)
    result = verify_structural_counts(counts_after_target, counts_after_unrelated, plan)
    assert result.passed, result.detail


def test_wipe_database_removes_everything_including_the_target_subgraph(driver):
    plan = build_fixture_plan(SMOKE_PROFILE, 0)
    seed_scale_point(driver, plan)

    wipe_database(driver)

    with open_session(driver, database=DATABASE, read_only=True) as session:
        remaining = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    assert remaining == 0


def test_smoke_profile_runs_end_to_end_through_real_snapshot_and_mcp_code(
    driver, benchmark_app_client
):
    result = run_profile(
        SMOKE_PROFILE,
        driver=driver,
        client=benchmark_app_client,
        candidate_sha=resolve_candidate_sha(),
        dirty_worktree=True,  # irrelevant to this smoke assertion - not a release-bound run
        neo4j_version="5",
    )

    assert result["profile"] == SMOKE_PROFILE
    assert len(result["scale_points"]) >= 2
    target_claim_counts = set()
    for point in result["scale_points"]:
        assert point["structural_validation"] == "PASS", point["structural_validation_detail"]
        assert point["semantic_validation"] == "PASS", result["semantic_validation_detail"]
        assert point["snapshot_id_consistent"] is True
        assert point["model_revision_consistent"] is True
        assert point["target_claim_count"] > 0
        target_claim_counts.add(point["target_claim_count"])
    # order-service's real declared+observed dependency candidates (spec §9's fixed target
    # subgraph) - unaffected by the unrelated filler at any scale point.
    assert len(target_claim_counts) == 1
