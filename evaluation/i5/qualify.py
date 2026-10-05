"""Two-process, clean-container I5.2 qualification on one explicit committed candidate.

Run: uv run python -m evaluation.i5.qualify run --candidate SHA --expectation-commit SHA --output /tmp/i5-results
The oracle must be independently adopted and committed before this command is allowed to ingest.
"""

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

from evaluation.i5.checks import canonical_bytes, facts_from_dossier

REPO = Path(__file__).resolve().parents[2]
ARTIFACT = REPO / "tests/fixtures/locality/two-workload-capture"
TOOLS = REPO / "harness/locality-capture/replay"
DOSSIER_RELATIVE = "tests/fixtures/locality/two-workload-capture/expected.md"
NEO4J_IMAGE = (
    "neo4j:5.26.31@sha256:5eb12ad77fa46ab73e23df9ea1f43f5c0f2a79523435577648e046be042b9b93"
)
COLLECTOR_IMAGE = "otel/opentelemetry-collector:0.161.0-386@sha256:ef477727d76320c53fa5c3eab269d98468bbe471173b93828b8032090df42de1"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def verify_inputs(candidate: str, expectation_commit: str) -> dict:
    assert len(candidate) == 40 and all(c in "0123456789abcdef" for c in candidate)
    assert git("rev-parse", "HEAD") == candidate, "candidate must equal checkout HEAD"
    assert not git("status", "--porcelain"), "qualification requires a clean checkout"
    assert candidate != expectation_commit, "expectations must be frozen in an earlier commit"
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", expectation_commit, candidate], cwd=REPO, check=True
    )
    committed = subprocess.check_output(
        ["git", "show", f"{expectation_commit}:{DOSSIER_RELATIVE}"], cwd=REPO
    )
    assert committed == (ARTIFACT / "expected.md").read_bytes(), "expectations changed after freeze"
    facts = facts_from_dossier(ARTIFACT / "expected.md")
    # The source-only helper has no AIP imports; keep identity/checksum logic in one place.
    sys.path.insert(0, str(TOOLS))
    from expected_actual import source_facts

    assert source_facts(ARTIFACT) == facts, "raw sources differ from the adopted dossier"
    return facts


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def write_json(path: Path, value: dict) -> None:
    path.write_bytes(canonical_bytes(value))


def command(args: list[str], output: Path, *, env: dict | None = None) -> None:
    with (output / "commands.jsonl").open("a") as log:
        log.write(json.dumps(args) + "\n")
    with (output / "execution.txt").open("ab") as log:
        subprocess.run(args, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


def worker(candidate: str, expectation_commit: str, output: Path) -> None:
    facts = verify_inputs(candidate, expectation_commit)
    output.mkdir(parents=True, exist_ok=False)
    output.chmod(0o777)
    ledger = {
        "candidate_sha": candidate,
        "expectation_commit": expectation_commit,
        "expectation_sha256": hashlib.sha256((ARTIFACT / "expected.md").read_bytes()).hexdigest(),
        "original_hashes": facts["original_hashes"],
        "worker_pid": os.getpid(),
        "neo4j_image": NEO4J_IMAGE,
        "collector_image": COLLECTOR_IMAGE,
        "status": "FAILED",
    }
    with tempfile.TemporaryDirectory(prefix="aip-i5-stage-") as directory:
        staging = Path(directory)
        staging.chmod(0o755)
        shutil.copytree(ARTIFACT / "c1", staging / "capture")
        shutil.copytree(ARTIFACT / "declarations", staging / "declarations")
        registration = json.loads((ARTIFACT / "source-registration.json").read_text())
        config = yaml.safe_load((TOOLS / "config.template.yaml").read_text())[
            "architecture_intelligence"
        ]
        config["sources"] = {
            "directories": [{"id": "aip-locality-i5-declarations", "root": "declarations"}],
            "clusters": [registration],
        }
        config["telemetry"]["scoped-evidence"] = {"enabled": True, "stream-id": registration["id"]}
        (staging / "config.yaml").write_text(yaml.safe_dump({"architecture_intelligence": config}))
        shutil.copyfile(staging / "config.yaml", output / "config.yaml")
        api_port, bolt_port, collector_port = (free_port() for _ in range(3))
        project = f"aip-i5-{os.getpid()}-{output.name.lower()}"
        image = f"aip-i5:{candidate}"
        compose = {
            "services": {
                "architecture-intelligence": {
                    "image": image,
                    "ports": [f"127.0.0.1:{api_port}:8000"],
                    "environment": {
                        "NEO4J_URI": "bolt://neo4j:7687",
                        "NEO4J_USER": "neo4j",
                        "NEO4J_PASSWORD": "i5-disposable",
                        "OPENAI_API_KEY": "",
                        "CONFIG_PATH": "/app/config.yaml",
                    },
                    "volumes": [
                        f"{staging}/config.yaml:/app/config.yaml:ro",
                        f"{staging}/capture:/app/capture:ro",
                        f"{staging}/declarations:/app/declarations:ro",
                        f"{REPO}/evaluation/i5:/app/i5-tools:ro",
                        f"{REPO}/tests/support/negotiated_mcp_client.py:/app/i5-tools/negotiated_mcp_client.py:ro",
                        f"{ARTIFACT}/expected.md:/app/i5-expected.md:ro",
                        f"{output}:/app/i5-results",
                    ],
                    "depends_on": {"neo4j": {"condition": "service_healthy"}},
                    "healthcheck": {"interval": "1s"},
                },
                "neo4j": {
                    "image": NEO4J_IMAGE,
                    "ports": [f"127.0.0.1:{bolt_port}:7687"],
                    "environment": {"NEO4J_AUTH": "neo4j/i5-disposable"},
                    "healthcheck": {
                        "test": ["CMD-SHELL", "wget -q --spider http://localhost:7474 || exit 1"],
                        "interval": "1s",
                        "timeout": "5s",
                        "retries": 30,
                        "start_period": "60s",
                        "start_interval": "1s",
                    },
                },
                "replay-collector": {
                    "image": COLLECTOR_IMAGE,
                    "ports": [f"127.0.0.1:{collector_port}:4318"],
                    "command": ["--config=/etc/otelcol/collector-replay.yaml"],
                    "volumes": [
                        f"{ARTIFACT}/replay/collector-replay.yaml:/etc/otelcol/collector-replay.yaml:ro"
                    ],
                    "depends_on": {"architecture-intelligence": {"condition": "service_healthy"}},
                },
            }
        }
        compose_file = staging / "compose.yaml"
        compose_file.write_text(yaml.safe_dump(compose))
        shutil.copyfile(compose_file, output / "compose.yaml")
        ledger.update(
            {
                "compose_project": project,
                "ports": [api_port, bolt_port, collector_port],
                "config_sha256": hashlib.sha256((staging / "config.yaml").read_bytes()).hexdigest(),
                "collector_config_sha256": hashlib.sha256(
                    (ARTIFACT / "replay/collector-replay.yaml").read_bytes()
                ).hexdigest(),
            }
        )
        base = ["docker", "compose", "-p", project, "-f", str(compose_file)]
        try:
            command([*base, "up", "-d", "--wait"], output)
            container_ids = subprocess.check_output([*base, "ps", "-q"], text=True).splitlines()
            ledger["containers"] = [
                json.loads(
                    subprocess.check_output(
                        ["docker", "inspect", "--format", "{{json .}}", cid], text=True
                    )
                )
                for cid in container_ids
            ]
            # Retain IDs/image/build identity, not unrelated container environment or host metadata.
            ledger["containers"] = [
                {
                    "id": c["Id"],
                    "image_id": c["Image"],
                    "host_pid": c["State"]["Pid"],
                    "service": c["Config"]["Labels"]["com.docker.compose.service"],
                }
                for c in ledger["containers"]
            ]
            image_env = json.loads(
                subprocess.check_output(["docker", "image", "inspect", image], text=True)
            )[0]["Config"]["Env"]
            assert f"AIP_BUILD_REVISION={candidate}" in image_env, (
                "image does not attest candidate SHA"
            )
            import httpx
            import neo4j

            with (
                neo4j.GraphDatabase.driver(
                    f"bolt://localhost:{bolt_port}", auth=("neo4j", "i5-disposable")
                ) as driver,
                driver.session() as session,
            ):
                assert session.run("MATCH (n) RETURN count(n) AS n").single()["n"] == 0
            ledger["fresh_graph_node_count"] = 0
            with httpx.Client(base_url=f"http://localhost:{api_port}", timeout=120) as client:
                for state in ("c1", "c2"):
                    print(f"{output.name}: importing and qualifying {state}", flush=True)
                    if state == "c2":
                        for child in (staging / "capture").iterdir():
                            child.unlink()
                        for child in (ARTIFACT / "c2").iterdir():
                            shutil.copyfile(child, staging / "capture" / child.name)
                    response = client.post("/api/import")
                    (output / f"import-{state}.json").write_bytes(response.content)
                    assert response.status_code == 200 and response.json().get("committed") is True
                    assert response.json()["inventory_status"] == "COMPLETE", response.text
                    if state == "c1":
                        deadline = time.monotonic() + 30
                        while True:
                            try:
                                with socket.create_connection(
                                    ("localhost", collector_port), timeout=1
                                ):
                                    break
                            except OSError:
                                if time.monotonic() >= deadline:
                                    raise RuntimeError("Collector receiver did not start") from None
                                time.sleep(0.2)
                        env = os.environ | {
                            "COLLECTOR_URL": f"http://localhost:{collector_port}/v1/traces",
                            "NEO4J_URI": f"bolt://localhost:{bolt_port}",
                            "NEO4J_USER": "neo4j",
                            "NEO4J_PASSWORD": "i5-disposable",
                        }
                        with (output / "replay.json").open("wb") as replay_out:
                            replay_cmd = [
                                sys.executable,
                                str(TOOLS / "replay.py"),
                                str(ARTIFACT / "otlp.jsonl"),
                            ]
                            with (output / "commands.jsonl").open("a") as log:
                                log.write(json.dumps(replay_cmd) + "\n")
                            subprocess.run(
                                replay_cmd, cwd=REPO, env=env, stdout=replay_out, check=True
                            )
                        assert (
                            json.loads((output / "replay.json").read_bytes())["lines_posted"]
                            == facts["recorded_requests"]
                        )
                    command(
                        [
                            *base,
                            "exec",
                            "-T",
                            "-e",
                            "PYTHONPATH=/app",
                            "architecture-intelligence",
                            "python",
                            "/app/i5-tools/evaluate.py",
                            state,
                            f"/app/i5-results/{state}",
                            "/app/i5-expected.md",
                        ],
                        output,
                    )
            logs = subprocess.check_output(
                [*base, "logs", "--no-color"], text=True, stderr=subprocess.STDOUT
            )
            (output / "containers.txt").write_text(logs)
            trace_lines = [
                line for line in logs.splitlines() if '"POST /v1/traces HTTP/1.1"' in line
            ]
            assert len(trace_lines) == facts["recorded_requests"] and all(
                '" 200' in line for line in trace_lines
            )
            assert (output / "c1/accounting.json").read_bytes() != b""
            c1, c2 = [
                json.loads((output / f"{s}/accounting.json").read_bytes()) for s in ("c1", "c2")
            ]
            assert c1["v1"] == c2["v1"], "C2 import changed observation accounting"
            ledger.update(
                {
                    "wire": {
                        "recorded_requests": facts["recorded_requests"],
                        "collector_200": facts["recorded_requests"],
                        "aip_200": len(trace_lines),
                    },
                    "status": "CORRECT",
                }
            )
        except BaseException as error:
            ledger["failure"] = f"{type(error).__name__}: {error}"
            try:
                (output / "containers.txt").write_bytes(
                    subprocess.check_output([*base, "logs", "--no-color"], stderr=subprocess.STDOUT)
                )
            except subprocess.CalledProcessError:
                pass
            raise
        finally:
            write_json(output / "ledger.json", ledger)
            command([*base, "down", "-v", "--remove-orphans"], output)


def compare(output: Path) -> None:
    a, b = output / "A", output / "B"
    ledgers = [json.loads((p / "ledger.json").read_bytes()) for p in (a, b)]
    assert all(l["status"] == "CORRECT" for l in ledgers)
    assert ledgers[0]["worker_pid"] != ledgers[1]["worker_pid"]
    for key in (
        "candidate_sha",
        "expectation_commit",
        "expectation_sha256",
        "original_hashes",
        "config_sha256",
        "collector_config_sha256",
    ):
        assert ledgers[0][key] == ledgers[1][key], key
    assert {c["id"] for c in ledgers[0]["containers"]}.isdisjoint(
        c["id"] for c in ledgers[1]["containers"]
    )
    required = set()
    for state in ("c1", "c2"):
        cases = [
            "inventory",
            "comparison",
            "evidence",
            "wrong-caller",
            "unauthorized-ref",
            "wrong-operation",
            "wrong-environment",
        ]
        if state == "c2":
            cases += ["stale-evidence", "stale-query", "stale-cursor"]
        required.update(
            Path(state) / f"{case}.{surface}.json"
            for case in cases
            for surface in ("request", "service", "rest", "mcp")
        )
        required.add(Path(state) / "snapshot-state.json")
    paths_a = {
        p.relative_to(a)
        for s in ("c1", "c2")
        for p in (a / s).glob("*.json")
        if not p.name.endswith("transport.json")
        and p.name not in ("result.json", "accounting.json")
    }
    paths_b = {
        p.relative_to(b)
        for s in ("c1", "c2")
        for p in (b / s).glob("*.json")
        if not p.name.endswith("transport.json")
        and p.name not in ("result.json", "accounting.json")
    }
    assert paths_a == paths_b == required, "missing or unexpected A/B canonical artifacts"
    digests = {}
    for path in sorted(paths_a):
        raw = (a / path).read_bytes()
        assert raw == (b / path).read_bytes(), f"raw canonical byte mismatch: {path}"
        digests[str(path)] = hashlib.sha256(raw).hexdigest()
    write_json(
        output / "comparison.json",
        {
            "status": "CORRECT",
            "candidate_sha": ledgers[0]["candidate_sha"],
            "expectation_commit": ledgers[0]["expectation_commit"],
            "canonical_sha256": digests,
        },
    )
    print(f"A/B raw canonical comparison: CORRECT ({len(digests)} artifacts)", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "worker", "compare"))
    parser.add_argument("--candidate")
    parser.add_argument("--expectation-commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.mode == "compare":
        compare(output)
        return
    verify_inputs(args.candidate, args.expectation_commit)
    if args.mode == "worker":
        worker(args.candidate, args.expectation_commit, output)
        return
    output.mkdir(parents=True, exist_ok=False)
    command(
        [
            "docker",
            "build",
            "--build-arg",
            f"AIP_BUILD_REVISION={args.candidate}",
            "-t",
            f"aip-i5:{args.candidate}",
            ".",
        ],
        output,
    )
    for run in ("A", "B"):
        subprocess.run(
            [
                sys.executable,
                "-m",
                "evaluation.i5.qualify",
                "worker",
                "--candidate",
                args.candidate,
                "--expectation-commit",
                args.expectation_commit,
                "--output",
                str(output / run),
            ],
            cwd=REPO,
            check=True,
        )
    compare(output)


if __name__ == "__main__":
    main()
