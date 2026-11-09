"""Materialize the GT 0.8.0 participant corpus from the frozen I1 inputs.

The corpus holds only the members of i1-freeze/participant/MANIFEST.md. Every file is read from git at
fixed revisions and checked against the frozen digests; any mismatch stops the run.

    python3 materialize_corpus.py --repo <aip checkout> --out <empty dir> [--gt] [--skip-repos]
    python3 materialize_corpus.py --repo <aip checkout> --check

--gt adds contracts.json (the GT-only structured rendering of the four YAML contracts).
--check verifies that the committed contracts.json equals the frozen YAML and exits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

FREEZE_COMMIT = "38fd1b18c566203c2ba90ec44a90f07a4084812b"  # #683, I1 frozen
PACKAGE_TAG = "v0.8.0"
# sha256 of the package SHA256SUMS, recorded in i1-freeze/README.md
PACKAGE_SUMS_SHA256 = "0cc5259a7501b20d6b9ca2d5dc6f8194d7fcbe2c5129a74876f25af017fbf450"
GT = "docs/reference-integrations/glamorous-toolkit/0.8.0"
FREEZE = f"{GT}/i1-freeze"
PACKAGE = "docs/specifications/0.8.0/i1-evidence"
REPO_PINS = "docs/specifications/0.7.2/i2-evidence/sokol111/freeze.md"
YAML_CONTRACTS = (
    "catalog/product-change-events.yaml",
    "image/image-promotion-information.yaml",
    "product-query/catalog-change-acceptance.yaml",
    "product-query/product-reads.yaml",
)
CONTRACTS = (*YAML_CONTRACTS, "marketplace-withdrawal-contract.md")
# I1 package members of the common corpus (MANIFEST); sokol111-kafka and the
# operator files (README, config, mapping review) are excluded.
PACKAGE_PREFIXES = (
    "c1/",
    "declarations/sokol111-local/",
    "mapping/sokol111-local/",
    "upstream/",
    "catalog/",
    "event-topic-lookup.json",
)


class Stop(SystemExit):
    def __init__(self, message: str):
        super().__init__(f"STOP: {message}")


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True).stdout


def show(repo: Path, rev: str, path: str) -> bytes:
    return git(repo, "show", f"{rev}:{path}")


def sums(text: bytes) -> dict[str, str]:
    return {line.split()[1]: line.split()[0] for line in text.decode().splitlines() if line.strip()}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(out: Path, rel: str, data: bytes, expected: str, digests: dict[str, str]) -> None:
    if sha256(data) != expected:
        raise Stop(f"{rel}: digest {sha256(data)} != frozen {expected}")
    target = out / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    digests[rel] = expected


def render_contracts(repo: Path) -> bytes:
    rendered = {
        path: yaml.safe_load(show(repo, FREEZE_COMMIT, f"{GT}/demo-promises/{path}"))
        for path in YAML_CONTRACTS
    }
    return (json.dumps(rendered, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def check_rendering(repo: Path) -> bytes:
    committed = (Path(__file__).parent / "contracts.json").read_bytes()
    rendered = render_contracts(repo)
    if committed != rendered:
        raise Stop("contracts.json differs from the rendering of the frozen YAML contracts")
    return committed


def repo_pins(repo: Path) -> dict[str, str]:
    table = show(repo, FREEZE_COMMIT, REPO_PINS).decode()
    pins = dict(re.findall(r"\| `Sokol111/([\w-]+)` \| `([0-9a-f]{40})` \|", table))
    if len(pins) != 16:
        raise Stop(f"expected 16 pinned repositories, found {len(pins)}")
    return pins


def clone(name: str, sha: str, target: Path) -> None:
    """Fetch exactly one commit by URL: no remote, no branches, no tags."""
    target.mkdir(parents=True)
    git(target, "init", "-q")
    git(target, "fetch", "-q", "--depth", "1", f"https://github.com/Sokol111/{name}", sha)
    git(target, "checkout", "-q", "--detach", sha)
    (target / ".git" / "FETCH_HEAD").unlink(missing_ok=True)
    head = git(target, "rev-parse", "HEAD").decode().strip()
    if head != sha or git(target, "remote").strip() or git(target, "for-each-ref").strip():
        raise Stop(f"{name}: clone is not exactly {sha} without remotes or refs")


def materialize(repo: Path, out: Path, gt: bool, skip_repos: bool) -> None:
    if out.exists() and any(out.iterdir()):
        raise Stop(f"{out} is not empty")
    out.mkdir(parents=True, exist_ok=True)
    digests: dict[str, str] = {}

    frozen = sums(show(repo, FREEZE_COMMIT, f"{FREEZE}/SHA256SUMS"))
    write(
        out,
        "task.md",
        show(repo, FREEZE_COMMIT, f"{FREEZE}/participant/task.md"),
        frozen["participant/task.md"],
        digests,
    )
    for path in CONTRACTS:
        data = show(repo, FREEZE_COMMIT, f"{GT}/demo-promises/{path}")
        write(out, f"contracts/{path}", data, frozen[f"../demo-promises/{path}"], digests)

    package_sums = show(repo, PACKAGE_TAG, f"{PACKAGE}/SHA256SUMS")
    if sha256(package_sums) != PACKAGE_SUMS_SHA256:
        raise Stop("the I1 package SHA256SUMS differs from the I1 freeze record")
    package = sums(package_sums)
    members = sorted(p for p in package if p.startswith(PACKAGE_PREFIXES))
    for path in members:
        write(
            out,
            f"inputs/{path}",
            show(repo, PACKAGE_TAG, f"{PACKAGE}/{path}"),
            package[path],
            digests,
        )

    if gt:
        data = check_rendering(repo)
        write(out, "contracts.json", data, sha256(data), digests)

    lines = [f"{digest}  {path}\n" for path, digest in sorted(digests.items())]
    (out / "SHA256SUMS").write_text("".join(lines))

    if not skip_repos:
        pins = repo_pins(repo)
        for name, sha in sorted(pins.items()):
            clone(name, sha, out / "sokol111" / name)
        (out / "REPOS.txt").write_text(
            "".join(f"{sha}  {name}\n" for name, sha in sorted(pins.items()))
        )
    print(f"corpus: {len(digests)} files{'' if skip_repos else ' + 16 repositories'} in {out}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the GT 0.8.0 participant corpus.")
    parser.add_argument(
        "--repo", type=Path, required=True, help="an AIP checkout containing the frozen commit"
    )
    parser.add_argument("--out", type=Path, help="an empty directory for the corpus")
    parser.add_argument(
        "--gt", action="store_true", help="add contracts.json for the GT conditions"
    )
    parser.add_argument(
        "--skip-repos", action="store_true", help="do not clone the Sokol111 repositories"
    )
    parser.add_argument(
        "--check", action="store_true", help="only verify contracts.json against the YAML"
    )
    args = parser.parse_args(argv)
    if args.check:
        check_rendering(args.repo)
        print("contracts.json equals the frozen YAML contracts")
        return 0
    if args.out is None:
        parser.error("--out is required unless --check is given")
    materialize(args.repo, args.out, args.gt, args.skip_repos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
