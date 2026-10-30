"""Operator: copy the run evidence into the repo, sanitized (v0.8 S5 pattern).
    python3 freeze.py OUT_DIR
Excluded: workspace/src (the clones), claude/ (config dir with the login), stream-*.jsonl."""

import hashlib
import json
import shutil
import sys
from pathlib import Path

RH = Path.home() / "aip-v08-vq-run"
OUT = Path(sys.argv[1])
SUBS = [
    (str(RH), "<run home>"),
    (str(Path.home() / "code/aip-value-run"), "<AIP checkout>"),
    ("<operator tmp>", "<operator tmp>"),
    (str(Path.home()), "<home>"),
    (str(RH).replace("/", "-"), "-<run home>"),
    ("-<home>-", "-<home>-"),
    ("<owner email>", "<owner email>"),
]
SESSIONS = [f"{t}_r{r}" for t in ("T-", "T+", "F-", "F+") for r in (1, 2, 3)]
WORKSPACE_OUT = ("plan.json", "plan.md", "answers.json", "requests.json")
SESSION_FILES = (
    "session.json",
    "preflight.json",
    "broker-check.json",
    "agent-requests.json",
    "requests-record.json",
    "audit.json",
    "scoring.json",
)


def clean(text: str) -> str:
    for old, new in SUBS:
        text = text.replace(old, new)
    return text


def name(rel: str) -> str:
    return clean(rel).replace("<", "").replace(">", "").replace(" ", "-")


def put(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        dst.write_text(clean(src.read_text()))
    except UnicodeDecodeError:
        shutil.copyfile(src, dst)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if OUT.exists():
    sys.exit(f"STOP: {OUT} exists")
for s in SESSIONS:
    sd, od = RH / "sessions" / s, OUT / "sessions" / s
    for f in SESSION_FILES:
        if (sd / f).exists():
            put(sd / f, od / f)
    for f in WORKSPACE_OUT:
        if (sd / "workspace" / f).exists():
            put(sd / "workspace" / f, od / "workspace" / f)
    for sub in ("replies", "superseded"):
        for p in sorted((sd / sub).rglob("*")) if (sd / sub).exists() else []:
            if p.is_file():
                put(p, od / sub / name(str(p.relative_to(sd / sub))))
    pre, post = [], []
    for p in sorted((sd / "transcripts").rglob("*")):
        if p.is_file():
            rel = name(str(p.relative_to(sd / "transcripts")))
            put(p, od / "transcripts" / rel)
            pre.append(f"{sha(p)}  {rel}")
            post.append(f"{sha(od / 'transcripts' / rel)}  {rel}")
    (od / "transcripts.pre-sanitize.sha256").write_text("\n".join(pre) + "\n")
    (od / "transcripts.sha256").write_text("\n".join(post) + "\n")
for attempt in sorted((RH / "package/ops/preflight-failed").rglob("session.json")):
    rel = attempt.parent.relative_to(RH / "package/ops/preflight-failed")
    for f in ("session.json", "preflight.json"):
        if (attempt.parent / f).exists():
            put(attempt.parent / f, OUT / "preflight-failed" / rel / f)
pkg = RH / "package"
for f in (
    "waivers.json",
    "sensitivity-row5.json",
    "compare-mechanical.json",
    "compare-final.json",
    "adaptations.diff",
):
    put(pkg / f, OUT / f)
for d in ("owner-review", "owner-verdicts", "raw", "images"):
    for p in sorted((pkg / d).rglob("*")):
        if p.is_file():
            put(p, OUT / d / p.relative_to(pkg / d))
put(pkg / "ops/sessions.log", OUT / "environment/sessions.log")
put(pkg / "ops/created.txt", OUT / "environment/created.txt")
put(RH / "aip-snapshot.txt", OUT / "environment/aip-snapshot.txt")
print(json.dumps({"files": sum(1 for p in OUT.rglob("*") if p.is_file())}))
