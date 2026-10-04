"""Two independent pytest workers and a raw-byte comparator (I4 revision 0.2 §4)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from benchmarks.snapshot_read_cost import resolve_candidate_sha

ROOT = Path(__file__).resolve().parents[2]
REGISTER = ROOT / "docs/specifications/0.6.0/i4-coverage-register.md"
REQUIRED_CASES = {
    *(f"X{i:02}" for i in range(1, 29)),
    *(f"P{i:02}" for i in range(1, 10)),
    *(f"Q{i:02}" for i in range(1, 9)),
    "B01a",
    "B01b",
    *(f"B{i:02}" for i in range(2, 7)),
}

# Required jobs in .github/workflows/ci.yml and codeql.yml, plus their aggregate checks.
REQUIRED_CI_CHECKS = frozenset(
    {
        "quality",
        "integration-core (heavy)",
        "integration-core (oracle)",
        "integration-core (rest)",
        "demo-e2e",
        "lint + test",
        "dependency security scan (pip-audit, spec §29)",
        "static analysis (semgrep)",
        "analyze (python)",
        "analyze (actions)",
        "CodeQL",
    }
)


def ci_blockers(check_runs: list[dict], candidate_sha: str) -> list[str]:
    """Require every mandatory gate to succeed on the candidate, even for partial API results."""
    blockers = []
    missing = REQUIRED_CI_CHECKS - {c["name"] for c in check_runs}
    if missing:
        blockers.append(f"missing mandatory CI checks: {sorted(missing)}")
    for check in check_runs:
        if check["head_sha"] != candidate_sha:
            blockers.append(f"CI candidate identity mismatch: {check['name']}/{check['id']}")
        allowed = (
            {"success"}
            if check["name"] in REQUIRED_CI_CHECKS
            else {"success", "skipped", "neutral"}
        )
        if check["status"] != "completed" or check["conclusion"] not in allowed:
            blockers.append(f"CI check not successful: {check['name']}/{check['id']}")
    return sorted(set(blockers))


def worker_tests() -> list[str]:
    """Every register anchor plus the specified end-to-end gates; full regression runs once."""
    anchors = set(re.findall(r"`(tests/[^`]+?\.py)::", REGISTER.read_text()))
    return sorted(
        anchors
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


def verify_candidate(candidate: str, *, development: bool = False) -> str:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert resolve_candidate_sha(candidate) == head, "checkout identity unavailable or mismatched"
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], text=True
    )
    if status and not development:
        raise ValueError(
            "qualification requires a clean committed checkout; uncommitted code cannot qualify HEAD"
        )
    subprocess.run(
        [
            "git",
            "merge-base",
            "--is-ancestor",
            "efe2fc301d9dc8e8a5a4eaf2afceb9f48f38772a",
            candidate,
        ],
        check=True,
    )
    return head


def compare_runs(root: Path) -> dict:
    runs = [json.loads((root / run / "ledger.json").read_text()) for run in ("A", "B")]
    blockers = []
    if runs[0]["candidate_sha"] != runs[1]["candidate_sha"]:
        blockers.append("candidate identities differ")
    if (
        runs[0]["process_id"] == runs[1]["process_id"]
        or runs[0]["container_id"] == runs[1]["container_id"]
    ):
        blockers.append("runs must have distinct process and container identities")
    if not all(r["container_id"] and r["resets"] for r in runs):
        blockers.append("fresh-container/reset evidence missing")
    records = [{r["key"]: r for r in run["records"]} for run in runs]
    if not records[0] or records[0].keys() != records[1].keys():
        blockers.append("missing or differing semantic artifact inventory")
    differences = []
    for key in sorted(records[0].keys() & records[1].keys()):
        left, right = [
            root / name / table[key]["bytes_ref"]
            for name, table in zip(("A", "B"), records, strict=True)
        ]
        a, b = left.read_bytes(), right.read_bytes()
        if a != b:
            differences.append({"key": key, "A": str(left), "B": str(right)})
        for raw, record in zip((a, b), (records[0][key], records[1][key]), strict=True):
            if hashlib.sha256(raw).hexdigest() != record["canonical_digest"]:
                blockers.append(f"artifact digest mismatch: {key}")
    if differences:
        blockers.append("raw canonical A/B differences")
    for run in runs:
        if not run.get("qualification_eligible", False):
            blockers.append(f"run {run['run']} is development evidence only")
        missing = REQUIRED_CASES - {record["case_id"] for record in run["records"]}
        if missing:
            blockers.append(f"run {run['run']} missing required cases: {sorted(missing)}")
        if run["exit_code"] != 0:
            blockers.append(f"run {run['run']} failed")
        if any(t["outcome"] != "passed" for t in run["tests"]):
            blockers.append(f"run {run['run']} has failed/skipped tests")
        if not all(r["oracle_match"] is True for r in run["records"]):
            blockers.append(f"run {run['run']} has unverified or failing oracle checks")
        client_records = [r for r in run["records"] if r["surface"] == "mcp-independent-client"]
        client_modes = [r["request"].get("mode") for r in client_records]
        if client_modes.count("query") < 2 or client_modes.count("evidence") < 1:
            blockers.append(f"run {run['run']} missing independent-client query/evidence/reconnect")
        grouped = {}
        for record in run["records"]:
            if (
                record["candidate_sha"] != run["candidate_sha"]
                or record["head"] != run["candidate_sha"]
            ):
                blockers.append(f"record identity mismatch: {record['key']}")
            if (
                not record["case_id"].startswith("Q")
                and record["surface"] != "legacy-relations"
                and record["producer_build_revision"] != run["candidate_sha"]
            ):
                blockers.append(f"producer identity mismatch: {record['key']}")
            grouped.setdefault(record["comparison_key"], {})[record["surface"]] = record
        for key, group in grouped.items():
            # Invalid Q requests compare rejection gates, not different transport error bodies.
            if next(iter(group.values()))["case_id"].startswith("Q"):
                if not {"rest", "mcp"} <= group.keys():
                    blockers.append(f"missing adapter rejection: {run['run']}/{key}")
                continue
            if next(iter(group.values()))["surface"].startswith("legacy-"):
                continue
            if not {"service", "rest", "mcp"} <= group.keys():
                blockers.append(f"missing parity surface: {run['run']}/{key}")
                continue
            values = [
                (root / run["run"] / group[s]["bytes_ref"]).read_bytes()
                for s in ("service", "rest", "mcp")
            ]
            if not values[0] == values[1] == values[2]:
                blockers.append(f"cross-surface mismatch: {run['run']}/{key}")
            if "mcp-independent-client" in group:
                independent = (
                    root / run["run"] / group["mcp-independent-client"]["bytes_ref"]
                ).read_bytes()
                if independent != values[0]:
                    blockers.append(f"independent-client mismatch: {run['run']}/{key}")
    return {
        "candidate_sha": runs[0]["candidate_sha"],
        "ab_equal": not differences and bool(records[0]) and records[0].keys() == records[1].keys(),
        "differences": differences,
        "blockers": sorted(set(blockers)),
        "runs": [str(root / r / "ledger.json") for r in ("A", "B")],
        "cross_surface_equal": not any(
            "surface" in blocker or "parity" in blocker or "independent-client" in blocker
            for blocker in blockers
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    verify_candidate(args.candidate_sha)
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for run in ("A", "B"):
        destination = root / run
        destination.mkdir()
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "evaluation.i4.pytest_plugin",
            *worker_tests(),
            "--i4-candidate-sha",
            args.candidate_sha,
            "--i4-run",
            run,
            "--i4-out",
            str(destination),
        ]
        with (destination / "pytest.txt").open("w") as log:
            subprocess.run(
                command,
                env={
                    **os.environ,
                    "I4_CANDIDATE_SHA": args.candidate_sha,
                    "AIP_BUILD_REVISION": args.candidate_sha,
                },
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
            )
        if not (destination / "ledger.json").exists():
            raise RuntimeError(
                f"run {run} failed before producing its ledger; inspect {destination / 'pytest.txt'}"
            )
    result = compare_runs(root)
    checks = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/michaelegner/architecture-intelligence-platform/commits/{args.candidate_sha}/check-runs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    (root / "ci-check-runs.json").write_text(
        checks.stdout if checks.returncode == 0 else json.dumps({"error": checks.stderr})
    )
    if checks.returncode:
        result["blockers"].append("exact-SHA CI query failed")
    else:
        check_runs = [check for page in json.loads(checks.stdout) for check in page["check_runs"]]
        result["ci_checks"] = [
            {
                "id": c["id"],
                "name": c["name"],
                "status": c["status"],
                "conclusion": c["conclusion"],
                "details_url": c["details_url"],
                "head_sha": c["head_sha"],
            }
            for c in check_runs
        ]
        result["required_ci_checks"] = sorted(REQUIRED_CI_CHECKS)
        result["blockers"].extend(ci_blockers(check_runs, args.candidate_sha))
    result["status"] = "PASS" if not result["blockers"] else "BLOCKED"
    result["known_debt"] = [
        "#323 remains open; I4 does not correct legacy NL/Kubernetes evidence exposure"
    ]
    result["remaining"] = [
        "I4.3 growth evidence and capacity disposition",
        "I6 exact-final-candidate requalification",
    ]
    (root / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(bool(result["blockers"]))


if __name__ == "__main__":
    raise SystemExit(main())
