"""v0.6.0 I3.2a: the reviewed I2 read hooks on real Neo4j (I3 decision record D4, D6, D8, D17.4).

`read_applicability_page` reads the captures first, lets the caller choose the candidate page size
from I3 D4's `S`, and stops before reading any candidate when the caller returns `None`. It runs
inside the caller's stable-snapshot attempt, so a write during the read discards the whole attempt.
I2's own entry points keep their fixed 500-record page unless a smaller `page_size` is given.
"""

import pytest

from app.architecture_intelligence.repository import read_stable_snapshot_from_session
from app.architecture_intelligence.scoped_applicability import SourceSelector
from app.architecture_intelligence.scoped_evidence_repository import (
    read_applicability_page,
    read_provider_owners,
    read_scoped_applicability,
)
from app.canonical.ids import scoped_observed_call_v2_id
from app.graph.revision_fence import bump_revision
from app.graph.schema import ensure_schema
from tests.integration.test_scoped_applicability import (
    _cap,
    _deployment_chain,
    _import,
    _store,
)
from tests.unit.test_scoped_applicability import K2, P1, P1_NAME, _record, _request

DATABASE = "neo4j"


@pytest.fixture
def graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)
    return driver


@pytest.fixture
def session(graph):
    with graph.session(database=DATABASE) as s:
        yield s


def _variant(n: int):
    """A distinct v2 record of the base vector: same caller Pod, its own Operation."""
    base = _record("V01-base")
    fields = {
        "environment": base.environment,
        "bucket_utc_day": base.bucket_utc_day,
        "subject_id": base.subject_id,
        "object_id": f"operation:service:pricing:GET:/p{n}",
        "caller_cluster_uid": base.caller_cluster_uid,
        "caller_pod_uid": base.caller_pod_uid,
    }
    return _record(
        "V01-base", object_id=fields["object_id"], id=scoped_observed_call_v2_id(**fields)
    )


def _source(graph, tmp_path, name="a", **overrides):
    return _import(
        graph,
        tmp_path,
        **_cap("CAP-A", name, resources=_deployment_chain("orders", [(P1_NAME, P1)]), **overrides),
    )


def _page(session, request=None, *, after_id=None, page_size_for=lambda _count: 500):
    return read_applicability_page(
        session, request or _request(), after_id=after_id, page_size_for=page_size_for
    )


def test_a_smaller_page_size_walks_every_candidate_once(graph, session, tmp_path):
    _source(graph, tmp_path)
    records = [_variant(n) for n in range(5)]
    for record in records:
        _store(session, record)

    seen, after_id, pages = [], None, 0
    while True:
        read = read_scoped_applicability(
            session,
            _request(),
            coverage_qualification_enabled=False,
            after_id=after_id,
            page_size=2,
        )
        pages += 1
        ids = [candidate.record.id for candidate in read.result.candidates]
        assert len(ids) <= 2
        seen += ids
        if not read.result.truncated:
            break
        assert read.result.next_after_id == ids[-1]
        after_id = read.result.next_after_id

    assert pages == 3
    assert seen == sorted(record.id for record in records)


def test_the_default_page_is_unchanged(graph, session, tmp_path):
    _source(graph, tmp_path)
    for n in range(3):
        _store(session, _variant(n))

    default = read_scoped_applicability(session, _request(), coverage_qualification_enabled=False)
    explicit = read_scoped_applicability(
        session, _request(), coverage_qualification_enabled=False, page_size=500
    )

    assert default == explicit
    assert len(default.result.candidates) == 3 and not default.result.truncated


def test_s_counts_every_accepted_capture_or_the_current_selected_one(graph, session, tmp_path):
    selected = _source(graph, tmp_path, "a")
    # An unrelated capture never pairs, but D4 still counts it (conservative bound).
    _source(graph, tmp_path, "b", cluster_uid=K2)
    _store(session, _record("V01-base"))
    counts = []

    def page_size_for(count):
        counts.append(count)
        return 500

    implicit = _page(session, page_size_for=page_size_for)
    explicit = _page(session, _request(selector=selected), page_size_for=page_size_for)
    stale = _page(
        session,
        _request(selector=SourceSelector(selected.source_instance_id, "no-such-revision")),
        page_size_for=page_size_for,
    )

    assert counts == [2, 1, 0]
    assert (implicit.considered_source_count, explicit.considered_source_count) == (2, 1)
    assert stale.considered_source_count == 0
    assert len(implicit.captures) == 2
    # The stale selector still yields D13.3's zero pairs, not a refusal.
    assert stale.result is not None
    assert [len(c.pairs) for c in stale.result.candidates] == [0]


class _RecordingRunner:
    def __init__(self, session):
        self._session = session
        self.queries = []

    def run(self, query, **params):
        self.queries.append(query)
        return self._session.run(query, **params)


def test_returning_none_stops_before_any_candidate_is_read(graph, session, tmp_path):
    _source(graph, tmp_path)
    _store(session, _record("V01-base"))
    runner = _RecordingRunner(session)

    page = _page(runner, page_size_for=lambda _count: None)

    assert page.result is None
    assert page.considered_source_count == 1 and len(page.captures) == 1
    assert len(runner.queries) == 1, "only the capture inventory may be read"
    assert "ScopedObservedCallV2" not in runner.queries[0]


def test_a_phase_1_refusal_reads_nothing(graph, session, tmp_path):
    _source(graph, tmp_path)
    runner = _RecordingRunner(session)

    page = _page(
        runner,
        _request(relation_type="SENDS"),
        page_size_for=lambda _count: pytest.fail("the hook must not run for a refusal"),
    )

    assert runner.queries == []
    assert page.result is not None and page.result.refusal is not None


def test_the_hook_runs_inside_the_stable_snapshot_attempt(graph, session, tmp_path):
    """A write between the capture read and the candidate read discards the attempt: the retry
    re-reads the captures, calls the hook again and sees the record the write added."""
    _source(graph, tmp_path)
    late = _record("V01-base")
    calls = []

    def page_size_for(count):
        calls.append(count)
        if len(calls) == 1:
            with graph.session(database=DATABASE) as writer:
                writer.execute_write(lambda tx: (_store(tx, late), bump_revision(tx)))
        return 500

    snapshot = read_stable_snapshot_from_session(
        session,
        coverage_qualification_enabled=False,
        read_extra=lambda runner: _page(runner, page_size_for=page_size_for),
    )

    assert len(calls) == 2
    assert snapshot.extra.result is not None
    assert [c.record.id for c in snapshot.extra.result.candidates] == [late.id]


def test_provider_owners_read_provides_rows_and_their_evidence(graph, session):
    session.run(
        "CREATE (p:Service {id: 'service:pricing', name: 'pricing'}), "
        "(q:Service {id: 'service:other', name: 'other'}), "
        "(o:Operation {id: 'operation:o1'}), (o2:Operation {id: 'operation:o2'}), "
        "(p)-[:PROVIDES {evidence_ids: ['ev:1', 'ev:dangling']}]->(o), "
        "(q)-[:PROVIDES {evidence_ids: ['ev:2']}]->(o2), "
        "(:Evidence {id: 'ev:1', evidence_type: 'DECLARED'}), "
        "(:Evidence {id: 'ev:2', evidence_type: 'DECLARED'})"
    ).consume()

    owners = read_provider_owners(session, operation_ids=["operation:o1", "operation:o1"])

    assert [(row["operation_id"], row["provider_id"]) for row in owners.provides] == [
        ("operation:o1", "service:pricing")
    ]
    # The dangling id is reported absent, so the owner rule never counts it (D8).
    assert sorted(owners.evidence_rows) == ["ev:1"]
    assert read_provider_owners(session, operation_ids=[]).provides == ()
