"""Two independent pytest workers and a raw-byte comparator (I4 revision 0.2 §4)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from app.architecture_intelligence.canonical_json import canonical_json_bytes
from benchmarks.snapshot_read_cost import resolve_candidate_sha
from evaluation.i4.profiles import BASELINE_ANCESTOR, DEFAULT_PROFILE, PROFILES, V06, Profile

ROOT = Path(__file__).resolve().parents[2]

# The pre-profile module-level names stay importable (tests, the pytest capture plugin and the
# benchmarks use them) and are the v0.6 profile's values.
REGISTER = V06.register
REQUIRED_CASES = set(V06.required_cases)
REQUIRED_CI_CHECKS = V06.required_ci_checks


def ci_blockers(
    check_runs: list[dict], candidate_sha: str, required: frozenset[str] = REQUIRED_CI_CHECKS
) -> list[str]:
    """Require every mandatory gate to succeed on the candidate, even for partial API results."""
    blockers = []
    missing = required - {c["name"] for c in check_runs}
    if missing:
        blockers.append(f"missing mandatory CI checks: {sorted(missing)}")
    for check in check_runs:
        if check["head_sha"] != candidate_sha:
            blockers.append(f"CI candidate identity mismatch: {check['name']}/{check['id']}")
        allowed = {"success"} if check["name"] in required else {"success", "skipped", "neutral"}
        if check["status"] != "completed" or check["conclusion"] not in allowed:
            blockers.append(f"CI check not successful: {check['name']}/{check['id']}")
    return sorted(set(blockers))


def worker_tests(profile: Profile = V06) -> list[str]:
    """The pytest worker list of a profile (the v0.6 list by default)."""
    return profile.worker_tests()


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
            BASELINE_ANCESTOR,
            candidate,
        ],
        check=True,
    )
    return head


def compare_runs(root: Path, profile: Profile = V06) -> dict:
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
        missing = profile.required_cases - {record["case_id"] for record in run["records"]}
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
                not record["case_id"].startswith(profile.rejection_prefix)
                and record["surface"] not in profile.producer_exempt_surfaces
                and record["producer_build_revision"] != run["candidate_sha"]
            ):
                blockers.append(f"producer identity mismatch: {record['key']}")
            grouped.setdefault(record["comparison_key"], {})[record["surface"]] = record
        for key, group in grouped.items():
            # Invalid requests (the profile's rejection prefix) compare rejection gates, not transport bodies.
            if next(iter(group.values()))["case_id"].startswith(profile.rejection_prefix):
                if not {"rest", "mcp"} <= group.keys():
                    blockers.append(f"missing adapter rejection: {run['run']}/{key}")
                continue
            if next(iter(group.values()))["surface"].startswith(profile.derived_surface_prefixes):
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


def run_commands(
    profile: Profile, candidate_sha: str, run: str, destination: Path
) -> list[list[str]]:
    """The commands that perform one run of a profile into `destination`."""
    if profile.runner_module is None:
        return [
            [
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "evaluation.i4.pytest_plugin",
                *profile.worker_tests(),
                "--i4-candidate-sha",
                candidate_sha,
                "--i4-run",
                run,
                "--i4-out",
                str(destination),
            ]
        ]
    return [
        [
            sys.executable,
            "-m",
            profile.runner_module,
            "--candidate-sha",
            candidate_sha,
            "--run",
            run,
            "--out",
            str(destination),
        ],
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "evaluation.i4.test_outcomes",
            *profile.worker_tests(),
            "--i4-out",
            str(destination),
        ],
    ]


def merge_test_outcomes(destination: Path) -> None:
    """Fold the worker tests' outcomes into the run's ledger (profiles with a runner module)."""
    outcomes = destination / "tests.json"
    if not outcomes.exists():
        return
    ledger_path = destination / "ledger.json"
    ledger = json.loads(ledger_path.read_text())
    recorded = json.loads(outcomes.read_text())
    ledger["tests"] = [*ledger.get("tests", []), *recorded["tests"]]
    ledger["exit_code"] = max(int(ledger.get("exit_code", 0)), int(recorded["exit_code"]))
    ledger_path.write_bytes(canonical_json_bytes(ledger) + b"\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--profile", choices=sorted(PROFILES), default=DEFAULT_PROFILE)
    args = parser.parse_args()
    profile = PROFILES[args.profile]
    verify_candidate(args.candidate_sha)
    root = args.out.resolve()
    root.mkdir(parents=True, exist_ok=False)
    for run in ("A", "B"):
        destination = root / run
        destination.mkdir()
        with (destination / "pytest.txt").open("w") as log:
            for command in run_commands(profile, args.candidate_sha, run, destination):
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
        merge_test_outcomes(destination)
    result = compare_runs(root, profile)
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
        result["profile"] = profile.name
        result["required_ci_checks"] = sorted(profile.required_ci_checks)
        result["blockers"].extend(
            ci_blockers(check_runs, args.candidate_sha, profile.required_ci_checks)
        )
    result["status"] = "PASS" if not result["blockers"] else "BLOCKED"
    result["known_debt"] = list(profile.known_debt)
    result["remaining"] = list(profile.remaining)
    (root / "report.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return int(bool(result["blockers"]))


if __name__ == "__main__":
    raise SystemExit(main())
