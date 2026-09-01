"""Protects the frozen Apache Airflow expected.yaml against schema drift, and guards the PR #44
re-review F1 fix: `service:airflow-apiserver` must not appear in `scope.entities`, or a full
official OpenAPI import's extra PROVIDES facts for unselected operations would fall in comparison
scope and be misclassified as INCORRECT_SUPPORTED.

This is not a qualifying I3 comparison - it only proves the committed dossier still loads under the
current real_world_validation schema, independent of any AIP run.
"""

from pathlib import Path

from real_world_validation.comparator import compare
from real_world_validation.loader import load_expected
from real_world_validation.model import RelationFact

EXPECTED_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "real-world-validation"
    / "apache-airflow"
    / "expected.yaml"
)


def test_airflow_expected_dossier_loads():
    doc = load_expected(EXPECTED_PATH)

    assert doc.system == "apache-airflow"
    assert doc.upstream_revision == "3adbbe1c58e4532df1964cb7794805e763816ee8"
    assert doc.scope.entities == (
        "operation:service:airflow-apiserver:GET:/api/v2/monitor/health",
        "operation:service:airflow-apiserver:GET:/api/v2/dags",
        "operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}",
        "operation:service:airflow-apiserver:POST:/api/v2/dags/{dag_id}/dagRuns",
        "operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns",
        "operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}",
        "operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances",
        "operation:service:airflow-apiserver:GET:/api/v2/dags/{dag_id}/dagRuns/{dag_run_id}/taskInstances/{task_id}",
        "operation:service:airflow-apiserver:GET:/api/v2/variables",
        "queue:default",
    )
    assert doc.scope.relation_types == ("PROVIDES", "SENDS", "RECEIVES_FROM")

    provides = [r for r in doc.expected_relations if r.fact.type == "PROVIDES"]
    assert len(provides) == 9

    assert {u.id for u in doc.unsupported} == {
        "airflow-scheduler-postgres-dependency",
        "airflow-apiserver-postgres-dependency",
        "airflow-celery-result-backend-postgres-dependency",
    }
    assert {u.id for u in doc.unresolved_identity} == {
        "airflow-execution-api-boundary",
        "airflow-runtime-role-identity",
    }
    assert {u.id for u in doc.insufficient_evidence} == {"airflow-celery-messaging-runtime-status"}


def test_airflow_scope_excludes_unselected_provider_operations():
    """PR #44 re-review F1: a full official OpenAPI import legitimately yields PROVIDES facts for
    many more airflow-apiserver operations than the 9 this dossier selects. With the provider
    Service itself removed from `scope.entities`, an extra PROVIDES fact touching an unselected
    operation must fall entirely outside comparison scope - not surface as a false
    INCORRECT_SUPPORTED finding."""
    doc = load_expected(EXPECTED_PATH)

    extra_unselected_provides = RelationFact(
        type="PROVIDES",
        source="service:airflow-apiserver",
        target="operation:service:airflow-apiserver:GET:/api/v2/connections",
    )
    assert not doc.scope.contains(extra_unselected_provides)

    expected_facts = [relation.fact for relation in doc.expected_relations]
    findings = compare(doc, expected_facts + [extra_unselected_provides])

    assert all(finding.actual != extra_unselected_provides for finding in findings)
    assert {f.classification for f in findings} == {
        "CORRECT",
        "UNSUPPORTED",
        "UNRESOLVED_IDENTITY",
        "INSUFFICIENT_EVIDENCE",
    }
