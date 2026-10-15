"""Per-release qualification profiles (v0.7.0 I4.1b; I4 spec §3, decision record D8).

A profile holds everything that differs between releases: the coverage register, the required case
ids, the worker test list, the capture implementation and the adapter-rejection case prefix. The CI
check names and the baseline ancestor are the same for every release. The `v0.6` profile holds the
constants and the worker-test list that `evaluation/i4/__main__.py` carried before profiles
existed, verbatim, so the v0.6 I4 record stays reproducible; it is the default of every entry point.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The first v0.6 qualification commit; every candidate descends from it.
BASELINE_ANCESTOR = "efe2fc301d9dc8e8a5a4eaf2afceb9f48f38772a"

# Required jobs in ci.yml and codeql.yml, including CI's emitted "lint + test" aggregate. A release
# candidate is a main commit, so the qualification tier (skipped on unrelated PRs) always ran.
# "CodeQL" is a workflow title, not an emitted check; both analysis jobs remain mandatory.
REQUIRED_CI_CHECKS = frozenset(
    {
        "quality",
        "changes",
        "integration-core (heavy)",
        "integration-core (rest)",
        "integration-qualification (heavy)",
        "integration-qualification (oracle)",
        "integration-qualification (other)",
        "demo-e2e",
        "lint + test",
        "dependency security scan (pip-audit, spec §29)",
        "static analysis (semgrep)",
        "analyze (python)",
        "analyze (actions)",
    }
)

_ANCHOR = re.compile(r"`(tests/[^`]+?\.py)::")


@dataclass(frozen=True)
class Profile:
    name: str
    register: Path
    required_cases: frozenset[str]
    required_ci_checks: frozenset[str]
    # Case ids with this prefix are adapter-rejection cases: only REST and MCP must reject them.
    rejection_prefix: str
    # Surfaces whose records are not compared across service, REST and MCP.
    derived_surface_prefixes: tuple[str, ...]
    # Surfaces whose payload carries no producer envelope to check against the candidate.
    producer_exempt_surfaces: frozenset[str]
    worker_tests: Callable[[], list[str]]
    known_debt: tuple[str, ...]
    remaining: tuple[str, ...]
    # The classification each case must carry, derived from the independently frozen expectation
    # (None for a profile that does not validate classifications, as v0.6 never did).
    expected_classification: Callable[[str], str | None] | None = None
    # A module run once per A/B run to capture the semantic records (`python -m <module>
    # --candidate-sha S --run R --out DIR`); None selects the pytest capture plugin.
    runner_module: str | None = None


def _register_anchors(register: Path) -> set[str]:
    return set(_ANCHOR.findall(register.read_text()))


# --- v0.6 (verbatim from the pre-profile evaluation/i4/__main__.py) -----------------------------

_V06_REGISTER = ROOT / "docs/specifications/0.6.0/i4-coverage-register.md"
_V06_REQUIRED_CASES = frozenset(
    {
        *(f"X{i:02}" for i in range(1, 29)),
        *(f"P{i:02}" for i in range(1, 10)),
        *(f"Q{i:02}" for i in range(1, 9)),
        "B01a",
        "B01b",
        *(f"B{i:02}" for i in range(2, 7)),
    }
)


def _v06_worker_tests() -> list[str]:
    """Every register anchor plus the specified end-to-end gates; full regression runs once."""
    return sorted(
        _register_anchors(_V06_REGISTER)
        | {
            "tests/integration/test_v060_i4_bridges.py",
            "tests/integration/test_locality_surface_parity.py",
            "tests/integration/test_scoped_evidence_persistence.py",
            "tests/integration/test_scoped_evidence_ledger.py",
            "tests/integration/test_locality_rehearsal_replay.py",
            "tests/integration/test_mcp_independent_client_golden_path.py",
            "tests/integration/test_evaluation_architecture_answers.py::test_every_bundled_scenario_passes_with_identical_two_pass_output",
            "tests/integration/test_i4_pubsub_qualification.py",
            "tests/unit/test_mcp_locality_contract_parity.py",
            "tests/unit/test_locality_contracts_schema_frozen.py",
            "tests/unit/test_architecture_intelligence_schema_frozen.py",
        }
    )


V06 = Profile(
    name="v0.6",
    register=_V06_REGISTER,
    required_cases=_V06_REQUIRED_CASES,
    required_ci_checks=REQUIRED_CI_CHECKS,
    rejection_prefix="Q",
    derived_surface_prefixes=("legacy-",),
    producer_exempt_surfaces=frozenset({"legacy-relations"}),
    worker_tests=_v06_worker_tests,
    known_debt=("#323 remains open; I4 does not correct legacy NL/Kubernetes evidence exposure",),
    remaining=(
        "I4.3 growth evidence and capacity disposition",
        "I6 exact-final-candidate requalification",
    ),
)

# --- v0.7 ---------------------------------------------------------------------------------------

# The I4-only result vocabulary of I4 spec §10; it never becomes public API vocabulary.
I4_VOCABULARY = frozenset(
    {
        "I4_CORRECT",
        "I4_EXPECTED_NEGATIVE",
        "I4_SEMANTIC_DEFECT",
        "I4_REPLAY_DEFECT",
        "I4_SURFACE_MISMATCH",
        "I4_MODEL_GAP",
        "I4_PRODUCT_VALUE_FAIL",
        "I4_NOT_RUN",
    }
)

_V07_SPEC = ROOT / "docs/specifications/0.7.0"
_V07_REGISTER = _V07_SPEC / "i4-coverage-register.md"


# The structural questions of the replay's revision step: fences, not readings of captured data.
_REPLAY_STRUCTURAL_CASES = ("EV", "REVd", "REVe")


def _v07_required_cases() -> frozenset[str]:
    """The 57 frozen I3 cases, the I4 bridge cases and the APISIX replay cases."""
    ids: set[str] = set(_REPLAY_STRUCTURAL_CASES)
    for vectors in (
        "i3-vectors/expected-answers.json",
        "i4-vectors/expected-i4.json",
        "i4-replay/expected-replay.json",
    ):
        document = json.loads((_V07_SPEC / vectors).read_text(encoding="utf-8"))
        ids.update(case["id"] for case in document["cases"])
    return frozenset(ids)


@cache
def _v07_classes() -> dict[str, str]:
    """The hand-authored class of every required case and of the runner's real-import questions
    (`i4-vectors/expected-i4.json`, written by `author_i4_expected.py`): the label is a property of
    the case's frozen purpose, never of an answer or a run."""
    document = json.loads((_V07_SPEC / "i4-vectors/expected-i4.json").read_text(encoding="utf-8"))
    return dict(document["classifications"])


def _v07_expected_classification(case_id: str) -> str | None:
    return _v07_classes().get(case_id)


def _v07_worker_tests() -> list[str]:
    """Every register anchor plus the end-to-end and frozen-contract gates; the full unit and
    integration tiers run once on the candidate (I4 spec §4.3)."""
    return sorted(
        _register_anchors(_V07_REGISTER)
        | {
            "tests/unit/test_v070_i3_projection_oracle.py",
            "tests/unit/test_v070_i3_adapter_oracle.py",
            "tests/unit/test_v070_i3_expected_answers.py",
            "tests/unit/test_v070_i4_register.py",
            "tests/unit/test_api_usage_contracts_schema_frozen.py",
            "tests/unit/test_mcp_api_usage_contract_parity.py",
            "tests/unit/test_locality_contracts_schema_frozen.py",
            "tests/unit/test_architecture_intelligence_schema_frozen.py",
            "tests/unit/test_mcp_locality_contract_parity.py",
            "tests/integration/test_api_usage_surface_parity.py",
            "tests/integration/test_api_usage_repeatability.py",
            "tests/integration/test_mcp_independent_client_golden_path.py",
            "tests/integration/test_v070_i2_qualification.py",
            "tests/integration/test_v070_i2_reconciliation.py",
            "tests/integration/test_v070_i2_measurement_source.py",
            "tests/integration/test_locality_surface_parity.py",
            "tests/integration/test_i4_pubsub_qualification.py",
            "tests/integration/test_snapshot_scoped_keys.py",
            "tests/integration/test_evaluation_architecture_answers.py::test_every_bundled_scenario_passes_with_identical_two_pass_output",
        }
    )


V07 = Profile(
    name="v0.7",
    register=_V07_REGISTER,
    required_cases=_v07_required_cases(),
    required_ci_checks=REQUIRED_CI_CHECKS,
    rejection_prefix="V",
    derived_surface_prefixes=("legacy-", "derived-"),
    producer_exempt_surfaces=frozenset({"legacy-relations", "derived-properties"}),
    worker_tests=_v07_worker_tests,
    known_debt=(
        "I3 F1: the projection builds the whole selection before paging (deferred past the candidate)",
        "I3 F2/F3: every request reads the whole canonical state; the evidence ref map is rebuilt per call",
        "#323 remains open; I4 does not correct legacy NL/Kubernetes evidence exposure",
    ),
    remaining=(
        "I4.3 Tyk dossier, product-value pilot and disposition",
        "I5 release candidate, release-content re-freeze, publication and verification",
    ),
    runner_module="evaluation.i4.api_usage_runner",
    expected_classification=_v07_expected_classification,
)

PROFILES = {profile.name: profile for profile in (V06, V07)}
DEFAULT_PROFILE = V06.name
