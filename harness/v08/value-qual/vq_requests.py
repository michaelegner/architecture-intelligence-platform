"""v0.8 value qualification (spec §4.3): answers the requests of a T session from the frozen
catalogue. Matching is mechanical, by `kind` only; the free text is recorded and never read.

- `broker_consumer_groups` -> R1: the frozen capture `catalogue/R1.txt`, verbatim;
- `repository_access` naming a repository of `r2-list.json` -> R2: the clone is copied from
  RUN_HOME/src into the workspace `src/` (one grant per repository);
- anything else, an invalid request or a repository off the list -> R3: `not available`.

Each request id is answered once. The reply goes to SESSION/replies/<turn>.txt (the operator sends it
unchanged as the next message), and every request, entry and grant is appended to
SESSION/requests-record.json.

    vq_requests.py answer RUN_HOME SESSION
"""

import datetime
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import vq_format

CATALOGUE = vq_format.EVIDENCE / "catalogue"
R1 = CATALOGUE / "R1.txt"
R2_LIST = CATALOGUE / "r2-list.json"


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True)


def on_r2_list(repository: str | None, r2: list[str]) -> bool:
    """Only the R2 list decides: `ecommerce-infrastructure` is never on it (D5)."""
    return repository in r2


def entry_for(request: dict, r2: list[str]) -> str:
    if request["kind"] == "broker_consumer_groups":
        return "R1"
    if request["kind"] == "repository_access" and on_r2_list(request.get("repository"), r2):
        return "R2"
    return "R3"


def answer(text: str, task_card: Path, record: list[dict]) -> tuple[str, list[dict], list[str]]:
    """(reply, new record entries, repositories to grant) for the current `requests.json` text."""
    catalogue = json.loads(R2_LIST.read_text())
    r2, replies = catalogue["repositories"], catalogue["replies"]
    answered = {e["request"].get("id") for e in record if isinstance(e["request"], dict)}
    granted = {e["grant"] for e in record if e.get("grant")}
    valid, invalid = vq_format.load_requests(text, task_card)
    turn = 1 + max((e["turn"] for e in record), default=0)
    utc = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    parts, entries, grants = [], [], []
    for request in valid:
        if request["id"] in answered:
            continue
        entry = entry_for(request, r2)
        grant = None
        if entry == "R1":
            body = R1.read_text()
        elif entry == "R2":
            body = replies["R2"].format(repository=request["repository"])
            if request["repository"] not in granted | set(grants):
                grant = request["repository"]
                grants.append(grant)
        else:
            body = replies["R3"]
        parts.append(f"{request['id']}: {body}")
        entries.append(
            {"turn": turn, "utc": utc, "request": request, "entry": entry, "grant": grant}
        )
    seen_invalid = {_canonical(e["request"]) for e in record if e["entry"] == "R3"}
    for request in invalid:
        if _canonical(request) in seen_invalid:
            continue
        seen_invalid.add(_canonical(request))
        parts.append(f"(invalid request): {replies['R3']}")
        entries.append({"turn": turn, "utc": utc, "request": request, "entry": "R3", "grant": None})
    reply = "\n\n".join(parts) if parts else replies["R3"]
    return reply, entries, grants


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 3 or args[0] != "answer":
        print(__doc__, file=sys.stderr)
        return 2
    run_home, session_dir = Path(args[1]).resolve(), Path(args[1]).resolve() / "sessions" / args[2]
    session = json.loads((session_dir / "session.json").read_text())
    if not session["type"].startswith("T"):
        print("STOP: only T sessions have a request channel", file=sys.stderr)
        return 2
    workspace = session_dir / "workspace"
    requests_path = workspace / "requests.json"
    text = requests_path.read_text() if requests_path.exists() else ""
    record_path = session_dir / "requests-record.json"
    record = json.loads(record_path.read_text()) if record_path.exists() else []
    reply, entries, grants = answer(text, vq_format.card(session["type"]), record)
    for repository in grants:
        target = workspace / "src" / repository
        if target.exists():
            print(f"STOP: {target} already exists", file=sys.stderr)
            return 2
        shutil.copytree(run_home / "src" / repository, target, symlinks=True)
    replies = session_dir / "replies"
    replies.mkdir(exist_ok=True)
    turn = entries[0]["turn"] if entries else 1 + len(list(replies.iterdir()))
    reply_path = replies / f"{turn}.txt"
    reply_path.write_text(reply + "\n")
    for entry in entries:
        entry["reply_sha256"] = hashlib.sha256(reply_path.read_bytes()).hexdigest()
    record_path.write_text(json.dumps(record + entries, indent=2) + "\n")
    print(f"reply written to {reply_path} ({len(entries)} request(s), grants: {grants or 'none'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
