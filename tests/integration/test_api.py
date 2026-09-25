from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.architecture_intelligence.contracts import Producer
from app.architecture_intelligence.service import ArchitectureIntelligenceService
from app.canonical import ids
from app.graph.importer import import_all_sources
from app.main import create_app
from app.settings import AppConfig, Secrets, Settings
from app.sources.model import FilesystemSourceConfig

_PRODUCER = Producer(
    name="architecture-intelligence-platform", version="0.5.0", build_revision="f" * 40
)

EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"
DATABASE = "neo4j"


@pytest.fixture(scope="module", autouse=True)
def populated_graph(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
    import_all_sources(
        driver,
        database=DATABASE,
        source_config=FilesystemSourceConfig(
            id="aip-bundled-examples-v0.5",
            root=EXAMPLES_DIR,
            stable_target_identity="urn:aip:logical-root:bundled-examples",
        ),
    )


def _queue_id(driver, name: str) -> str:
    """I1 spec §9: Queue identity is owner-scoped (broker+namespace+channel), not name-based - all
    bundled fixtures share one broker/namespace, so a queue name still resolves to exactly one id.
    """
    with driver.session(database=DATABASE) as session:
        return session.run("MATCH (q:Queue {name: $name}) RETURN q.id AS id", name=name).single()[
            "id"
        ]


def _message_id(driver, name: str) -> str:
    """I1 spec §9.1: Message identity is owner-scoped per declaring service - a name like
    "PaymentRequested" may resolve to more than one distinct Message node (one per declaring
    service) absent an explicit shared-identity mapping (not wired in this increment). Picks one
    deterministically; callers only need *a* real, round-trippable message id."""
    with driver.session(database=DATABASE) as session:
        return session.run(
            "MATCH (m:Message {name: $name}) RETURN m.id AS id ORDER BY m.id LIMIT 1", name=name
        ).single()["id"]


def _evidence_id(driver, *, source_type: str) -> str:
    with driver.session(database=DATABASE) as session:
        return session.run(
            "MATCH (e:Evidence {source_type: $source_type}) RETURN e.id AS id ORDER BY e.id LIMIT 1",
            source_type=source_type,
        ).single()["id"]


def _snapshot_id(driver) -> str:
    """v0.5.0 I3 slice 5a: `GET /api/evidence`/`GET /api/evidence/{id}` now require a real,
    current `snapshot_id` (spec §16.3) - fetched the same way a real caller would, from any other
    `ArchitectureIntelligenceService`-backed answer."""
    service = ArchitectureIntelligenceService(driver, database=DATABASE, producer=_PRODUCER)
    snapshot_id, _rows = service.list_public_evidence()
    return snapshot_id


class FakeProvider:
    """No real OpenAI calls: fixed Cypher, deterministic answer."""

    def __init__(self, cypher: str = "MATCH (s:Service) RETURN s.name AS name"):
        self.cypher = cypher

    def generate_cypher(self, *, question: str, schema_description: str) -> str:
        return self.cypher

    def compose_answer(self, *, question: str, cypher: str, rows: list[dict]) -> str:
        return f"Found {len(rows)} row(s)."


def _build_app(driver, *, llm_provider=None):
    app = create_app()
    app.state.driver = driver
    app.state.llm_provider = llm_provider
    app.state.architecture_intelligence_service = ArchitectureIntelligenceService(
        driver, database=DATABASE, producer=_PRODUCER
    )
    app.state.settings = Settings(
        config=AppConfig.model_validate(
            {
                "sources": {
                    "directories": [
                        {
                            "id": "aip-bundled-examples-v0.5",
                            "root": str(EXAMPLES_DIR),
                            "stable_target_identity": "urn:aip:logical-root:bundled-examples",
                        }
                    ]
                },
                "graph": {"uri": "bolt://ignored:7687", "database": DATABASE},
            }
        ),
        secrets=Secrets(neo4j_user="neo4j", neo4j_password="ignored", openai_api_key=None),
    )
    return app


@pytest.fixture
def client(driver):
    return TestClient(_build_app(driver))


@pytest.fixture
def client_with_llm(driver):
    return TestClient(_build_app(driver, llm_provider=FakeProvider()))


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_neo4j(client):
    response = client.get("/health/neo4j")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_services(client):
    response = client.get("/api/services")
    assert response.status_code == 200
    names = {s["name"] for s in response.json()}
    assert names == {"OrderService", "ProductService", "PaymentService", "InvoiceService"}


def test_get_service(client):
    response = client.get(f"/api/services/{ids.service_id('order-service')}")
    assert response.status_code == 200
    assert response.json()["name"] == "OrderService"


def test_get_service_not_found(client):
    response = client.get("/api/services/service:does-not-exist")
    assert response.status_code == 404


def test_list_queues(client):
    response = client.get("/api/queues")
    assert response.status_code == 200
    names = {q["name"] for q in response.json()}
    assert names == {"payment-q", "invoice-q", "unused-q", "unknown-producer-q", "payment-dlq"}


def test_get_queue(client, driver):
    response = client.get(f"/api/queues/{_queue_id(driver, 'payment-q')}")
    assert response.status_code == 200
    assert response.json()["name"] == "payment-q"


def test_get_queue_not_found(client):
    response = client.get("/api/queues/queue:does-not-exist")
    assert response.status_code == 404


def test_list_messages(client):
    response = client.get("/api/messages")
    assert response.status_code == 200
    names = {m["name"] for m in response.json()}
    assert names == {
        "PaymentRequested",
        "InvoiceCreated",
        "UnusedMessage",
        "UnknownProducerMessage",
    }


def test_get_message(client, driver):
    response = client.get(f"/api/messages/{_message_id(driver, 'PaymentRequested')}")
    assert response.status_code == 200
    assert response.json()["version"] == "v2"


def test_get_message_not_found(client):
    response = client.get("/api/messages/message:does-not-exist")
    assert response.status_code == 404


def test_list_evidence(client, driver):
    response = client.get("/api/evidence", params={"snapshot_id": _snapshot_id(driver)})
    assert response.status_code == 200
    # one per scanned source file: order-service has 3 (openapi/asyncapi/manifest),
    # product-service/payment-service/invoice-service have 1 each
    assert len(response.json()) == 6
    source_types = {e["source_type"] for e in response.json()}
    assert source_types == {"OPENAPI", "ASYNCAPI", "MANIFEST"}


def test_list_evidence_requires_snapshot_id(client):
    response = client.get("/api/evidence")
    assert response.status_code == 422


def test_list_evidence_rejects_stale_snapshot_id(client):
    stale_snapshot_id = "aip:snapshot:v1:" + "0" * 64
    response = client.get("/api/evidence", params={"snapshot_id": stale_snapshot_id})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SNAPSHOT_NOT_AVAILABLE"


def test_get_evidence(client, driver):
    response = client.get(
        f"/api/evidence/{_evidence_id(driver, source_type='MANIFEST')}",
        params={"snapshot_id": _snapshot_id(driver)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source_type"] == "MANIFEST"
    assert body["source_file"].endswith("examples/order-service/architecture.yaml")
    assert body["evidence_type"] == "DECLARED"


def test_get_evidence_not_found(client, driver):
    response = client.get(
        "/api/evidence/evidence:openapi:does-not-exist",
        params={"snapshot_id": _snapshot_id(driver)},
    )
    assert response.status_code == 404


def test_get_service_evidence(client):
    response = client.get(f"/api/services/{ids.service_id('order-service')}/evidence")
    assert response.status_code == 200
    source_types = {e["source_type"] for e in response.json()}
    # order-service PROVIDES (openapi), SENDS (asyncapi), and CALLS (manifest)
    assert source_types == {"OPENAPI", "ASYNCAPI", "MANIFEST"}


def test_get_service_evidence_not_found(client):
    response = client.get("/api/services/service:does-not-exist/evidence")
    assert response.status_code == 404


def test_get_queue_evidence(client, driver):
    response = client.get(f"/api/queues/{_queue_id(driver, 'payment-q')}/evidence")
    assert response.status_code == 200
    # payment-q's SENDS/CARRIES/RECEIVES_FROM/DEAD_LETTERS_TO relations are declared by
    # both order-service (sender) and payment-service (consumer + DLQ)
    assert len(response.json()) == 2
    assert all(e["source_type"] == "ASYNCAPI" for e in response.json())


def test_get_queue_evidence_not_found(client):
    response = client.get("/api/queues/queue:does-not-exist/evidence")
    assert response.status_code == 404


def test_a1_senders_endpoint(client, driver):
    response = client.get(f"/api/analysis/queues/{_queue_id(driver, 'payment-q')}/senders")
    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == [ids.service_id("order-service")]


def test_a2_consumers_endpoint(client, driver):
    response = client.get(f"/api/analysis/queues/{_queue_id(driver, 'payment-q')}/consumers")
    assert response.status_code == 200
    assert [s["id"] for s in response.json()] == [ids.service_id("payment-service")]


def test_a3_queues_without_consumers_endpoint(client, driver):
    response = client.get("/api/analysis/queues/without-consumers")
    assert response.status_code == 200
    assert [q["id"] for q in response.json()] == [_queue_id(driver, "unused-q")]


def test_a4_queues_without_senders_endpoint(client, driver):
    response = client.get("/api/analysis/queues/without-senders")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["queue_id"] == _queue_id(driver, "unknown-producer-q")


def test_a5_blast_radius_endpoint_default_depth(client):
    response = client.get(f"/api/analysis/services/{ids.service_id('order-service')}/blast-radius")
    assert response.status_code == 200
    reached = {e["service_id"] for e in response.json()}
    assert reached == {
        ids.service_id("product-service"),
        ids.service_id("payment-service"),
        ids.service_id("invoice-service"),
    }


def test_a5_blast_radius_endpoint_depth_param(client):
    response = client.get(
        f"/api/analysis/services/{ids.service_id('order-service')}/blast-radius",
        params={"depth": 1},
    )
    assert response.status_code == 200
    reached = {e["service_id"] for e in response.json()}
    assert reached == {ids.service_id("product-service"), ids.service_id("payment-service")}


def test_post_import_all(client):
    response = client.post("/api/import")
    assert response.status_code == 200
    body = response.json()
    assert "import_id" in body
    assert body["committed"] is True
    assert len(body["sources"]) == 6  # order-service (x3), product/payment/invoice-service
    # v0.5.0 I5 F2: the versioned I1 §10 report rides alongside the unchanged `sources`.
    assert body["report_version"] == "aip-import-report/1"
    [run] = body["runs"]
    assert run["inventory_status"] == "COMPLETE" and run["committed"] is True
    assert {r["source_instance_id"] for r in run["source_results"]} == set(body["sources"])


def test_post_import_service(client):
    response = client.post(f"/api/import/service/{ids.service_id('order-service')}")
    assert response.status_code == 200
    body = response.json()
    assert "import_id" in body
    assert body["service_id"] == ids.service_id("order-service")
    assert body["committed"] is True


def test_post_import_service_not_found(client):
    response = client.post("/api/import/service/service:does-not-exist")
    assert response.status_code == 404


def test_post_query_without_provider_configured_returns_503(client):
    response = client.post("/api/query", json={"question": "who sends payment-q?"})
    assert response.status_code == 503


def test_post_query_with_configured_provider_returns_real_answer(client_with_llm):
    response = client_with_llm.post("/api/query", json={"question": "who sends payment-q?"})
    assert response.status_code == 200
    body = response.json()
    assert body["question"] == "who sends payment-q?"
    assert body["cypher"] == "MATCH (s:Service) RETURN s.name AS name LIMIT 100"
    assert len(body["rows"]) == 4
    assert body["answer"] == "Found 4 row(s)."


def test_post_query_with_semantically_invalid_cypher_returns_422(driver):
    client = TestClient(
        _build_app(
            driver,
            llm_provider=FakeProvider(cypher="MATCH (q:Queue)-[:SENDS]->(s:Service) RETURN q.id"),
        )
    )
    response = client.post("/api/query", json={"question": "who sends to services?"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "SEMANTIC_QUERY_INVALID"
    assert body["relation"] == "SENDS"
    assert body["expectedSource"] == ["Service"]
    assert body["expectedTarget"] == ["Queue"]


def test_post_query_deterministic_intent_works_without_llm_configured(client):
    # Proves a known-intent question succeeds with zero LLM provider configured (H3) - unlike
    # the 503 above, which is only for genuinely UNKNOWN questions.
    response = client.post("/api/query", json={"question": "Which queues have no consumer?"})
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "DETERMINISTIC"
    assert body["intent"] == "A3_QUEUES_WITHOUT_CONSUMERS"
    assert body["cypher"] is None


def test_post_query_deterministic_rows_match_analysis_endpoint_a1(client, driver):
    query_response = client.post("/api/query", json={"question": "Who sends to payment-q?"})
    analysis_response = client.get(f"/api/analysis/queues/{_queue_id(driver, 'payment-q')}/senders")
    assert query_response.json()["rows"] == analysis_response.json()


def test_post_query_deterministic_rows_match_analysis_endpoint_a4(client):
    query_response = client.post(
        "/api/query", json={"question": "What queues have a consumer but no known sender?"}
    )
    analysis_response = client.get("/api/analysis/queues/without-senders")
    assert query_response.json()["rows"] == analysis_response.json()


def test_post_query_ac_h3_7_live_test_regression(client):
    response = client.post(
        "/api/query", json={"question": "What queues have a consumer but no known sender?"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_mode"] == "DETERMINISTIC"
    assert body["intent"] == "A4_QUEUES_WITHOUT_SENDERS"
    assert [row["queue_name"] for row in body["rows"]] == ["unknown-producer-q"]


def test_ui_index_lists_services_and_queues(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "OrderService" in response.text
    assert "payment-q" in response.text


def test_ui_service_explorer(client):
    response = client.get(f"/services/{ids.service_id('order-service')}")
    assert response.status_code == 200
    assert "OrderService" in response.text
    assert "ProductService / getProduct" in response.text
    assert "payment-q" in response.text
    # evidence rendered per relation (spec §4.11)
    assert "examples/order-service/openapi.yaml" in response.text
    assert "examples/order-service/asyncapi.yaml" in response.text
    assert "examples/order-service/architecture.yaml" in response.text
    assert "Evidence: DECLARED" in response.text


def test_ui_service_explorer_not_found(client):
    response = client.get("/services/service:does-not-exist")
    assert response.status_code == 404


def test_ui_queue_explorer(client, driver):
    response = client.get(f"/queues/{_queue_id(driver, 'payment-q')}")
    assert response.status_code == 200
    assert "OrderService" in response.text  # sender
    assert "PaymentService" in response.text  # consumer
    assert "PaymentRequested" in response.text
    assert "payment-dlq" in response.text  # DLQ
    # evidence rendered on the CARRIES relation (spec §4.11)
    assert "examples/order-service/asyncapi.yaml" in response.text
    assert "examples/payment-service/asyncapi.yaml" in response.text


def test_ui_queue_explorer_not_found(client):
    response = client.get("/queues/queue:does-not-exist")
    assert response.status_code == 404


def test_ui_query_page_empty_state(client):
    response = client.get("/query")
    assert response.status_code == 200
    assert "Natural Language Query" in response.text


def test_ui_query_page_with_question_and_no_provider_shows_not_configured(client):
    response = client.get("/query", params={"question": "who sends payment-q?"})
    assert response.status_code == 200
    assert "who sends payment-q?" in response.text
    assert "not configured" in response.text


def test_ui_query_page_with_question_and_provider_shows_real_answer(client_with_llm):
    response = client_with_llm.get("/query", params={"question": "who sends payment-q?"})
    assert response.status_code == 200
    assert "who sends payment-q?" in response.text
    assert "Found 4 row(s)." in response.text


def test_ui_query_page_deterministic_intent_shown_without_provider(client):
    response = client.get("/query", params={"question": "Which queues have no consumer?"})
    assert response.status_code == 200
    assert "Deterministic Analysis" in response.text
    assert "A3_QUEUES_WITHOUT_CONSUMERS" in response.text


def test_kubernetes_evidence_is_absent_from_the_public_evidence_surface(client, driver):
    """I2 Draft 0.2 §9 (as amended): a Kubernetes source's evidence supports only internal-only
    infrastructure facts, so it is not part of the public evidence surface - exposing it while
    hiding everything it supports would leak those facts' existence and attribution by the back
    door."""
    evidence_id = "evidence:kubernetes:surface-test"
    with driver.session(database=DATABASE) as session:
        session.run(
            "CREATE (e:Evidence {id: $id, source_type: 'KUBERNETES', source_file: 'snapshot.yaml', "
            "evidence_type: 'DECLARED'})",
            id=evidence_id,
        )
    try:
        snapshot_id = _snapshot_id(driver)
        listed = client.get("/api/evidence", params={"snapshot_id": snapshot_id})
        assert listed.status_code == 200
        assert evidence_id not in {e["id"] for e in listed.json()}
        assert "KUBERNETES" not in {e["source_type"] for e in listed.json()}

        assert (
            client.get(
                f"/api/evidence/{evidence_id}", params={"snapshot_id": snapshot_id}
            ).status_code
            == 404
        )
    finally:
        with driver.session(database=DATABASE) as session:
            session.run("MATCH (e:Evidence {id: $id}) DETACH DELETE e", id=evidence_id)
