"""v0.6.0 I2.6a: offline replay of the committed capture REHEARSAL (I1 capture runbook §§6-7, 9).

`tests/fixtures/locality/rehearsal/` is a real, labelled REHEARSAL recording - NOT I5 evidence
(runbook §8/§9) - taken by `harness/locality-capture/rehearse.sh` on a throwaway kind cluster. This
test replays it with no cluster: the declarations and the C1 (or C2) envelope go through the real
importer, and every recorded `otlp.jsonl` line goes through the real `POST /v1/traces` as one
protobuf request, in file order.

The runbook's pinned wire path is JSON line -> replay Collector -> protobuf -> AIP (run by
`harness/locality-capture/replay/run-replay.sh`, its result in `RUN-RECORD.md`). Here the
JSON -> protobuf step is done in the test, as the Collector's OTLP-JSON unmarshaller does it: OTLP
JSON writes trace/span ids as hex, protobuf's canonical JSON as base64, so only those id fields are
converted before `json_format.Parse`. Nothing else in the recording is touched.
"""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from google.protobuf import json_format
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.scoped_applicability import LocalityRequest
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.graph.importer import import_all_sources, import_kubernetes_source
from app.graph.schema import ensure_schema
from app.main import create_app
from app.qualification.declared_observed import CONFIRMED, OBSERVED_ONLY
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig, KubernetesSourceConfig
from app.telemetry.correlation_buffer import HttpCorrelationBuffer
from app.telemetry.scoped_attribution import LocalityDisposition

DATABASE = "neo4j"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "locality" / "rehearsal"
IDS = dict(
    line.split("=", 1)
    for line in (FIXTURE / "identities.env").read_text(encoding="utf-8").splitlines()
    if "=" in line
)
ANALYSIS = json.loads((FIXTURE / "analysis.json").read_text(encoding="utf-8"))
ENVIRONMENT = "locality-capture"
O1 = "operation:service:pricing:GET:/prices"
O2 = "operation:service:legacy-pricing:GET:/prices"
PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.6.0", build_revision="f" * 40
)
_ID_FIELDS = ("traceId", "spanId", "parentSpanId")

pytestmark = pytest.mark.skipif(
    not (FIXTURE / "otlp.jsonl").exists(), reason="the rehearsal fixture is not present"
)


def test_the_fixture_is_intact_and_labelled():
    sums = (FIXTURE / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    for line in sums:
        digest, name = line.split(maxsplit=1)
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == digest, name
    assert "REHEARSAL - NOT I5" in (FIXTURE / "RUN-RECORD.md").read_text(encoding="utf-8")


def _hex_ids_to_base64(node):
    if isinstance(node, dict):
        return {
            key: (
                base64.b64encode(bytes.fromhex(value)).decode()
                if key in _ID_FIELDS and isinstance(value, str) and value
                else _hex_ids_to_base64(value)
            )
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_hex_ids_to_base64(item) for item in node]
    return node


def _requests(recording: Path = FIXTURE / "otlp.jsonl") -> list[bytes]:
    requests = []
    for line in recording.read_text(encoding="utf-8").splitlines():
        if line.strip():
            message = ExportTraceServiceRequest()
            json_format.Parse(json.dumps(_hex_ids_to_base64(json.loads(line))), message)
            requests.append(message.SerializeToString())
    return requests


def _kubernetes(capture: str) -> KubernetesSourceConfig:
    return KubernetesSourceConfig(
        id="aip-locality-rehearsal",
        root=FIXTURE / capture,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="aip-locality-rehearsal-scope",
        cluster_uid=IDS["CLUSTER_UID"],
        evidence_mode="CAPTURED_RESOURCE",
        authorized_producer="aip-locality-rehearsal",
        authority_record="aip-locality-rehearsal-self-declared-authority",
    )


def _replay(
    driver, capture: str | None, *, scoped: bool = True, recording: Path = FIXTURE / "otlp.jsonl"
):
    """One clean state: declarations, one capture (if any), then every recorded line through
    /v1/traces."""
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n").consume()
        ensure_schema(session)
    declarations = FilesystemSourceConfig(
        id="aip-locality-rehearsal-declarations", root=FIXTURE / "declarations"
    )
    assert import_all_sources(driver, database=DATABASE, source_config=declarations).committed
    if capture is not None:
        assert import_kubernetes_source(
            driver, database=DATABASE, source_config=_kubernetes(capture)
        ).committed
    app = create_app()
    app.state.driver = driver
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {
                "graph": {"uri": "bolt://ignored:7687", "database": DATABASE},
                "telemetry": {
                    "http-correlation": {"enabled": True},
                    "scoped-evidence": {"enabled": scoped, "stream-id": "aip-locality-rehearsal"},
                },
            }
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored"),
    )
    app.state.http_correlation_buffer = HttpCorrelationBuffer(
        ttl_seconds=60, max_pending_spans=10000
    )
    client = TestClient(app)
    for body in _requests(recording):
        response = client.post(
            "/v1/traces", content=body, headers={"Content-Type": "application/x-protobuf"}
        )
        assert response.status_code == 200, response.text
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=PRODUCER)
    request = LocalityRequest(
        subject_service_id="service:orders",
        environment=ENVIRONMENT,
        first_day=IDS["DAY"],
        last_day=IDS["DAY"],
    )
    with driver.session(database=DATABASE) as session:
        v1 = {
            row["operation"]: row["count"]
            for row in session.run(
                "MATCH (:Service {id: 'service:orders'})-[r:CALLS]->(o:Operation) "
                "UNWIND r.evidence_ids AS eid MATCH (e:Evidence {id: eid}) "
                "WHERE e.evidence_type = 'OBSERVED' "
                "RETURN o.id AS operation, e.observation_count AS count"
            )
        }
        v2 = {
            (row["pod"], row["operation"]): row["count"]
            for row in session.run(
                "MATCH (v:ScopedObservedCallV2) RETURN v.caller_pod_uid AS pod, "
                "v.object_id AS operation, v.observation_count AS count"
            )
        }
    return service.assess_local_calls(request), v1, v2


# `_replay` starts from an empty graph, so its result depends only on its arguments: each distinct
# replay runs once per session. Only tests that read the returned values may reuse it - a test that
# reads the graph itself loads the state it needs (see `test_locality_query.py`).
_RESULTS: dict[tuple, tuple] = {}


def _replay_and_remember(
    driver, capture: str | None, *, scoped: bool = True, recording: Path = FIXTURE / "otlp.jsonl"
):
    result = _replay(driver, capture, scoped=scoped, recording=recording)
    _RESULTS[(capture, scoped, recording)] = result
    return result


def _replayed(
    driver, capture: str | None, *, scoped: bool = True, recording: Path = FIXTURE / "otlp.jsonl"
):
    key = (capture, scoped, recording)
    if key not in _RESULTS:
        _replay_and_remember(driver, capture, scoped=scoped, recording=recording)
    return _RESULTS[key]


def _by_workload(result):
    return {
        (a.caller_workload.name, a.object_operation_id): a.qualification for a in result.assertions
    }


def test_c1_yields_the_two_workload_answer_and_every_call_keeps_its_client_identity(driver):
    """E1-E3 and E6; gate 4: every recorded CLIENT span, whatever its arrival order relative to
    its SERVER (in-batch, CLIENT-first, SERVER-first), is counted in its own Pod's v2 record."""
    result, v1, v2 = _replayed(driver, "c1")
    assert _by_workload(result) == {("orders", O1): CONFIRMED, ("orders-canary", O2): OBSERVED_ONLY}
    assert result.candidate_limitations == ()
    assert {a.caller_workload.uid for a in result.assertions} and len(
        {a.caller_workload.uid for a in result.assertions}
    ) == 2
    assert all(a.target_runtime_scope == "UNKNOWN" for a in result.assertions)
    clients = ANALYSIS["client_spans"]
    assert v2[(IDS["P1_UID"], O1)] == clients["P1 -> pricing"]
    assert v2[(IDS["P2_UID"], O2)] == clients["P2 -> legacy-pricing"]
    assert set(v2) == {(IDS["P1_UID"], O1), (IDS["P2_UID"], O2)}
    assert v1 == {O1: clients["P1 -> pricing"], O2: clients["P2 -> legacy-pricing"]}


def test_c2_keeps_p1_s_record_and_unresolves_it(driver):
    """E4, E5, E7: P1's v2 record is retained and still P1's, but its Workload is UNRESOLVED."""
    c1, _, _ = _replayed(driver, "c1")
    result, _, v2 = _replayed(driver, "c2")
    assert _by_workload(result) == {("orders-canary", O2): OBSERVED_ONLY}
    [limitation] = result.candidate_limitations
    assert limitation.disposition is LocalityDisposition.UNRESOLVED
    assert limitation.reasons == ("LOCALITY_CAPTURE_MISSING_POD",)
    assert (IDS["P1_UID"], O1) in v2
    assert result.snapshot_id != c1.snapshot_id


def test_v1_is_unchanged_by_scoped_evidence(driver):
    """E6: the flag-off replay yields exactly the same v1 counts."""
    _, v1_on, _ = _replayed(driver, "c1")
    _, v1_off, v2_off = _replayed(driver, "c1", scoped=False)
    assert v1_off == v1_on
    assert v2_off == {}


def test_attempt_1_keeps_client_identity_in_the_client_first_order(driver):
    """Gate 4, the CLIENT-first half: attempt 1's unmodified recording (1 s batch) has 644
    CLIENT-first and 224 SERVER-first pairs, and no in-batch pair. Its C1/C2 were invalid and are
    not committed, so no capture is imported: v2 identity needs none. Every recorded CLIENT span
    is counted in its own Pod's v2 record."""
    attempt1 = FIXTURE / "attempt1"
    ids = dict(
        line.split("=", 1)
        for line in (attempt1 / "identities.env").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    analysis = json.loads((attempt1 / "analysis.json").read_text(encoding="utf-8"))
    assert analysis["arrival_orders"]["client_first"] > 0
    _, v1, v2 = _replayed(driver, None, recording=attempt1 / "otlp.jsonl")
    clients = analysis["client_spans"]
    assert v2 == {
        (ids["P1_UID"], O1): clients["P1 -> pricing"],
        (ids["P2_UID"], O2): clients["P2 -> legacy-pricing"],
    }
    assert v1 == {O1: clients["P1 -> pricing"], O2: clients["P2 -> legacy-pricing"]}
