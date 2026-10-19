"""v0.7.1 I4 A/B replay (I4 spec §2): two clean runs of the frozen real-Kafka replay on one SHA.

Runs `tests/integration/test_v071_i4_kafka_replay.py` in two separate pytest processes, each with
its own session-scoped Neo4j container, so both start from a clean state. Each run writes the full
answers of every step (snapshot ids, sorted answers, evidence refs and payloads) as canonical JSON;
the two files must be byte-identical. No normalization is applied.

    uv run python docs/specifications/0.7.1/i4-evidence/kafka/ab_replay.py --out <new directory>

Writes `run-a.json`, `run-b.json` and `ab-result.json` (HEAD, worktree state, input digests, the
digest of each run and the verdict). Exits 1 on any mismatch or test failure.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TEST = "tests/integration/test_v071_i4_kafka_replay.py"


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout.strip()


def _run(out: Path) -> int:
    env = {**os.environ, "AIP_I4_REPLAY_OUT": str(out)}
    command = ["uv", "run", "pytest", TEST, "-q", "-p", "no:cacheprovider", "-m", "qualification"]
    return subprocess.run(command, check=False, cwd=REPO, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)

    sums = subprocess.run(
        ["sha256sum", "-c", "--quiet", "SHA256SUMS"],
        check=False,
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    runs = {name: args.out / f"run-{name}.json" for name in ("a", "b")}
    codes = {name: _run(path) for name, path in runs.items()}
    digests = {
        name: hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        for name, path in runs.items()
    }
    identical = (
        all(code == 0 for code in codes.values())
        and None not in digests.values()
        and runs["a"].read_bytes() == runs["b"].read_bytes()
    )
    result = {
        "head": _git("rev-parse", "HEAD"),
        "worktree_clean": _git("status", "--porcelain") == "",
        "inputs_sha256sums": (HERE / "SHA256SUMS").read_text().splitlines(),
        "inputs_verified": sums.returncode == 0,
        "pytest_exit_codes": codes,
        "run_sha256": digests,
        "verdict": "IDENTICAL" if identical and sums.returncode == 0 else "MISMATCH",
    }
    (args.out / "ab-result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["verdict"] == "IDENTICAL" else 1


if __name__ == "__main__":
    sys.exit(main())
