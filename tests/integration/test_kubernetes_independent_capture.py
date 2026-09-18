"""I2 Draft 0.2 §11: "At least one independently captured, frozen resource bundle must qualify the
owner-chain handoff; authored fixtures alone do not justify a claim of captured-resource
interoperability." Every other Kubernetes fixture in this repo (`tests/fixtures/kubernetes/i2/` and
every dynamically-written bundle in `tests/integration/test_importer.py`) is author-fabricated.

`tests/fixtures/kubernetes/i2-independent-capture/` is a real `kubectl get -o yaml` capture from a
real (throwaway) `kind` cluster running this repo's own real `examples/runtime-demo/` app - see that
directory's own `PROVENANCE.md` for the exact capture procedure, upstream system/revision, and
temporal-atomicity disclosure §11 requires recorded. No live cluster access is needed to run this
test - only the frozen files are read.
"""

import re
from pathlib import Path

from app.canonical.infrastructure import KubernetesEvidenceMode
from app.graph.importer import import_kubernetes_source
from app.graph.schema import ensure_schema
from app.sources.model import KubernetesSourceConfig

DATABASE = "neo4j"
FIXTURE_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "kubernetes" / "i2-independent-capture"
)

# Real, API-server-assigned UUIDs are visibly distinct in shape from this repo's hand-typed fixture
# identifiers (e.g. "deploy-uid-1") - a lowercase-hex-with-dashes UUID4-shaped string.
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _config() -> KubernetesSourceConfig:
    return KubernetesSourceConfig(
        id="aip-i2-independent-capture",
        root=FIXTURE_DIR,
        envelope_relative_path="envelope.yaml",
        configured_scope_id="aip-i2-independent-capture-scope",
        cluster_uid="599e90a5-7ab8-426f-807f-92a65dcc8822",
        evidence_mode=KubernetesEvidenceMode.CAPTURED_RESOURCE,
        authorized_producer="aip-i2-independent-capture-runbook",
        authority_record="aip-i2-independent-capture-self-declared-authority",
    )


def test_independent_capture_commits_cleanly_with_no_diagnostics(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)

    stats = import_kubernetes_source(driver, database=DATABASE, source_config=_config())

    assert stats.committed is True
    assert stats.diagnostics == ()
    [source_stats] = list(stats.per_source.values())
    # ACCEPTED, not ACCEPTED_WITH_LIMITATIONS - every field the real capture carries is either
    # allowlisted or correctly outside the allowlist (never a limitation-triggering shape).
    assert source_stats.result == "ACCEPTED"


def test_independent_capture_resolves_the_real_owner_chain_with_genuine_uids(driver):
    """The mandatory bar per §11: real owner-chain resolution against genuine, API-server-assigned
    UIDs - not hand-typed fixture strings."""
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=_config())
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        workload = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_WORKLOAD'}) "
            "RETURN e.id AS id, e.name AS name"
        ).single()
        pod = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_POD'}) "
            "RETURN e.id AS id, e.name AS name"
        ).single()
        ownership = session.run(
            "MATCH (c:InfrastructureClaim {kind: 'WORKLOAD_OWNS_POD'}) "
            "RETURN c.subject_id AS subject_id, c.object_id AS object_id, "
            "c.evidence_refs AS evidence_refs"
        ).single()
        pod_contribution = session.run(
            "MATCH (c:InfrastructureContribution {entity_id: $id}) "
            "RETURN c.captured_resource_uid AS uid",
            id=pod["id"],
        ).single()

    assert workload["name"] == "runtime-demo"
    assert pod["name"] == "runtime-demo-6dc89f5656-8xxrv"
    assert ownership["subject_id"] == workload["id"]
    assert ownership["object_id"] == pod["id"]
    # A resolved chain's evidence covers the Pod, the Workload, and the bridging ReplicaSet (never
    # promoted to an entity of its own, per §7.1) - three source pointers, mirroring the checked-in
    # authored fixture's own end-to-end assertion.
    assert len(ownership["evidence_refs"]) == 3
    # The real captured Pod UID - genuinely UUID-shaped, not a hand-typed fixture string.
    assert pod_contribution["uid"] == "658bd464-c78f-4ca2-b7e4-2b04e158f4ee"
    assert _UUID_RE.match(pod_contribution["uid"])


def test_independent_capture_resolves_service_selection_and_ingress_routing(driver):
    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=_config())
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        workload_id = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_WORKLOAD'}) RETURN e.id AS id"
        ).single()["id"]
        service = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_NETWORK_SERVICE'}) "
            "RETURN e.id AS id, e.service_type AS service_type, e.ports AS ports"
        ).single()
        ingress_id = session.run(
            "MATCH (e:InfrastructureEntity {entity_kind: 'KUBERNETES_INGRESS'}) RETURN e.id AS id"
        ).single()["id"]
        selection = session.run(
            "MATCH (c:InfrastructureClaim {kind: 'NETWORK_SERVICE_SELECTS_WORKLOAD'}) "
            "RETURN c.subject_id AS subject_id, c.object_id AS object_id"
        ).single()
        routing = session.run(
            "MATCH (c:InfrastructureClaim {kind: 'INGRESS_ROUTES_TO_NETWORK_SERVICE'}) "
            "RETURN c.subject_id AS subject_id, c.object_id AS object_id"
        ).single()
        workload_contribution = session.run(
            "MATCH (c:InfrastructureContribution {entity_id: $id}) "
            "RETURN c.service_id_annotation AS annotation",
            id=workload_id,
        ).single()

    assert service["service_type"] == "ClusterIP"
    assert service["ports"] == ['{"name":"http","port":8080,"protocol":"TCP"}']
    assert selection["subject_id"] == service["id"]
    assert selection["object_id"] == workload_id
    assert routing["subject_id"] == ingress_id
    assert routing["object_id"] == service["id"]
    # The real Deployment's real `architecture-intelligence.io/service-id` annotation, genuinely
    # queryable post-persistence (I2 §12 slice 6's own fix), not just folded into a digest.
    assert workload_contribution["annotation"] == "service:runtime-demo"


def test_independent_capture_ignores_real_kubectl_injected_noise_fields(driver):
    """§5: "Status, managedFields, timestamps embedded in resources, arbitrary annotations,
    container commands, environment values, volumes, credentials, and Secret contents are not
    architecture evidence." A hand-authored fixture never exercises this allowlist boundary against
    real noise - this real capture genuinely carries `pod-template-hash` (injected by the real
    Deployment controller) and `kubectl.kubernetes.io/last-applied-configuration` (injected by real
    `kubectl apply`), proving they're correctly ignored rather than merely never having been present
    to test against.
    """
    raw_bytes = (FIXTURE_DIR / "resources.yaml").read_bytes()
    assert b"pod-template-hash" in raw_bytes
    assert b"kubectl.kubernetes.io/last-applied-configuration" in raw_bytes
    assert b"containerStatuses" in raw_bytes

    with driver.session(database=DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        ensure_schema(session)
    stats = import_kubernetes_source(driver, database=DATABASE, source_config=_config())
    assert stats.committed is True

    with driver.session(database=DATABASE) as session:
        all_props = session.run(
            "MATCH (n) WHERE n:InfrastructureEntity OR n:InfrastructureContribution "
            "OR n:InfrastructureClaim RETURN properties(n) AS props"
        ).value()
    serialized = repr(all_props)
    assert "pod-template-hash" not in serialized
    assert "last-applied-configuration" not in serialized
    assert "containerStatuses" not in serialized
    assert "podIP" not in serialized
