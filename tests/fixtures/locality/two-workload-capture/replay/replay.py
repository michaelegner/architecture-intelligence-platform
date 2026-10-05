"""Line-by-line replay driver (v0.6.0 I2.6a; I1 capture runbook §6).

Posts each `otlp.jsonl` line, in file order, unmodified, to the replay Collector's OTLP/HTTP JSON
receiver. Requires HTTP 200 for every line and aborts on the first other status. Between lines it
waits for AIP's revision fence to settle (two equal consecutive reads), the golden-path pattern
(`examples/release-golden-path/golden_path.py` `_wait_for_revision_to_settle`), read over Bolt.

Usage: uv run python harness/locality-capture/replay/replay.py OTLP_JSONL
Environment: COLLECTOR_URL (default http://localhost:14318/v1/traces), NEO4J_URI (default
bolt://localhost:17687), NEO4J_USER, NEO4J_PASSWORD.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

import neo4j

COLLECTOR_URL = os.environ.get("COLLECTOR_URL", "http://localhost:14318/v1/traces")
FENCE_QUERY = "MATCH (s:AipInternalState {id: 'architecture'}) RETURN s.revision AS revision"


def _fence(session: neo4j.Session) -> int | None:
    record = session.run(FENCE_QUERY).single()
    return None if record is None else record["revision"]


def _settle(session: neo4j.Session, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last = _fence(session)
    while time.monotonic() < deadline:
        time.sleep(0.2)
        current = _fence(session)
        if current == last:
            return
        last = current
    raise SystemExit("the revision fence did not settle")


def main(path: str) -> None:
    driver = neo4j.GraphDatabase.driver(
        os.environ.get("NEO4J_URI", "bolt://localhost:17687"),
        auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]),
    )
    posted = 0
    with open(path, "rb") as recording, driver.session() as session:
        for number, line in enumerate(recording, start=1):
            if not line.strip():
                continue
            request = urllib.request.Request(
                COLLECTOR_URL,
                data=line.rstrip(b"\n"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    status = response.status
            except urllib.error.HTTPError as error:
                status = error.code
            if status != 200:
                raise SystemExit(f"line {number}: the replay Collector answered {status}; aborted")
            posted += 1
            _settle(session)
    driver.close()
    print(json.dumps({"lines_posted": posted}))


if __name__ == "__main__":
    main(sys.argv[1])
