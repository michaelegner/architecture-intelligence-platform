"""Pins the deployment reconciliation rule identity.

`contracts.DEPLOYMENT_RECONCILIATION_RULE_VERSION` stamps every `DeploymentResolution` (and so feeds
`resolution_id`/`claim_id`) and is bound into the snapshot fingerprint (and so every `snapshot_id`).
A bump - a reviewed spec change - must fail loudly here and change the snapshot id.

If the rule version is bumped on purpose, update `PINNED_RULE_VERSION` here in the same PR.
"""

import inspect

from app.architecture_intelligence import repository as repo
from app.architecture_intelligence.contracts import (
    DEPLOYMENT_RECONCILIATION_RULE_ID,
    DEPLOYMENT_RECONCILIATION_RULE_VERSION,
)
from app.architecture_intelligence.deployment_projection import compute_deployment_resolution_id

PINNED_RULE_ID = "service-workload-reconciliation"
PINNED_RULE_VERSION = 1


class _EmptySession:
    def run(self, _query: str, **_params):
        return []


def _state():
    return repo.canonical_snapshot_state(_EmptySession(), coverage_qualification_enabled=True)


def test_rule_version_and_id_are_pinned():
    assert DEPLOYMENT_RECONCILIATION_RULE_VERSION == PINNED_RULE_VERSION
    assert DEPLOYMENT_RECONCILIATION_RULE_ID == PINNED_RULE_ID


def test_resolution_ids_default_to_the_pinned_rule_version():
    default = inspect.signature(compute_deployment_resolution_id).parameters[
        "reconciliation_rule_version"
    ]
    assert default.default == PINNED_RULE_VERSION


def test_snapshot_state_binds_the_rule_id_and_version():
    assert _state()["deployment_reconciliation_rule"] == {
        "rule_id": PINNED_RULE_ID,
        "rule_version": PINNED_RULE_VERSION,
    }


def test_bumping_the_rule_version_changes_the_snapshot_id(monkeypatch):
    before, _ = repo.snapshot_fingerprint(_state())
    monkeypatch.setattr(repo, "DEPLOYMENT_RECONCILIATION_RULE_VERSION", PINNED_RULE_VERSION + 1)
    after, _ = repo.snapshot_fingerprint(_state())
    assert before != after
