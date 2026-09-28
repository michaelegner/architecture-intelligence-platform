"""Container images outside `docs/` are pinned by digest, so a dev stack, test run, demo or release
build can't silently change underneath us when an upstream tag moves.

What this checks, in tracked files outside `docs/`:
- every `services.<name>.image` in any YAML file with a top-level `services:` key (Compose files,
  including overlays), parsed as YAML so comments, anchors and quoting don't matter; a
  `${VAR:-default}` counts as its default, while a caller-supplied `${VAR}`/`${VAR:?...}` is pinned
  by that caller;
- every `jobs.<id>.services.<name>.image` and `jobs.<id>.container` in `.github/workflows/`;
- every `FROM`, `COPY/ADD --from=` and `RUN --mount=...,from=` image in files named like
  `Dockerfile` (instructions are case-insensitive, continuation lines are joined, flags may come in
  any order, and earlier build stages are recognized);
- every image string passed to a class imported from `testcontainers`, positionally or as
  `image=`, in either quote style.
A reference this module can't interpret (a parameterized `FROM $BASE`, an image held in a Python
constant) fails loudly rather than passing.

`docs/` is excluded because its compose files are historical real-world-validation evidence with
their own frozen conventions. Dependabot bumps the Dockerfile and compose pins; the testcontainers
Neo4j literals aren't visible to it, so they must match `docker-compose.yml`'s pin - a Dependabot
bump of that pin fails here until the literals follow.

Files that a frozen release profile checksums can't change without invalidating that profile, so
they stay unpinned until the profile is next re-frozen (`_FROZEN_UNPINNED`).
"""

from __future__ import annotations

import ast
import re
import shlex
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]

_DIGEST_PINNED = re.compile(r"^[^\s@]+:[^\s@]+@sha256:[0-9a-f]{64}$")
_VAR_WITH_DEFAULT = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*:?-(?P<default>.+)\}$")
_STRING_ARG = re.compile(r"""^\s*(?:image\s*=\s*)?(['"])(?P<image>[^'"]+)\1""")
_IMAGE_KWARG = re.compile(r"""\bimage\s*=\s*(['"])(?P<image>[^'"]+)\1""")
_NEO4J_CONTAINER = re.compile(r"""Neo4jContainer\(\s*(['"])(?P<image>[^'"]+)\1""")

_GOLDEN_PATH_SHA256SUMS = REPO_ROOT / "examples" / "release-golden-path" / "SHA256SUMS"
# Component files of the frozen v0.5.0 release golden-path profile: pin them when that profile is
# re-frozen, not before.
_FROZEN_UNPINNED = {"examples/runtime-demo/Dockerfile"}


def _tracked(*patterns: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--", *patterns],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [
        REPO_ROOT / line
        for line in result.stdout.splitlines()
        if line and not line.startswith("docs/")
    ]


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _compose_image(image: str) -> str | None:
    """The image a Compose `image:` value resolves to, or None when a caller supplies it."""
    if not image.startswith("${"):
        return image
    default = _VAR_WITH_DEFAULT.match(image)
    return default.group("default") if default else None


def _compose_refs() -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for path in _tracked("*.yml", "*.yaml"):
        if path.parts[len(REPO_ROOT.parts)] == ".github":
            continue
        text = path.read_text()
        if not re.search(r"^services:", text, re.MULTILINE):
            continue
        for document in yaml.safe_load_all(text):
            services = document.get("services") if isinstance(document, dict) else None
            if not isinstance(services, dict):
                continue  # e.g. an architecture manifest's `services:` list
            for service in services.values():
                if isinstance(service, dict) and "image" in service:
                    image = _compose_image(str(service["image"]))
                    if image is not None:
                        refs.append((_rel(path), image))
    return refs


def _workflow_refs() -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for path in _tracked(".github/workflows/*.yml", ".github/workflows/*.yaml"):
        workflow = yaml.safe_load(path.read_text()) or {}
        for job in (workflow.get("jobs") or {}).values():
            container = job.get("container")
            if isinstance(container, dict):
                container = container.get("image")
            if container:
                refs.append((_rel(path), str(container)))
            for service in (job.get("services") or {}).values():
                if isinstance(service, dict) and service.get("image"):
                    refs.append((_rel(path), str(service["image"])))
    return refs


def _dockerfile_instructions(text: str) -> list[list[str]]:
    joined = re.sub(r"\\\n", " ", text)
    instructions = []
    for line in joined.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            instructions.append(shlex.split(stripped, comments=False))
    return instructions


def _dockerfile_refs() -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for path in _tracked("*Dockerfile*", "*dockerfile*"):
        source = _rel(path)
        stages: set[str] = set()
        for words in _dockerfile_instructions(path.read_text()):
            instruction, args = words[0].upper(), words[1:]
            if instruction == "FROM":
                positional = [arg for arg in args if not arg.startswith("--")]
                image = positional[0]
                assert "$" not in image, f"{source}: parameterized FROM {image} isn't supported"
                if len(positional) >= 3 and positional[1].upper() == "AS":
                    stages.add(positional[2].lower())
                if image.lower() not in stages:
                    refs.append((source, image))
            elif instruction in {"COPY", "ADD", "RUN"}:
                for arg in args:
                    if not arg.startswith("--"):
                        break
                    if arg.startswith("--from="):
                        image = arg.removeprefix("--from=")
                    elif arg.startswith("--mount=") and "from=" in arg:
                        image = arg.split("from=", 1)[1].split(",", 1)[0]
                    else:
                        continue
                    if image.lower() not in stages and not image.isdigit():
                        refs.append((source, image))
    return refs


def _testcontainers_names(tree: ast.Module) -> set[str]:
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("testcontainers")
        for alias in node.names
    }


def _testcontainer_refs() -> list[tuple[str, str]]:
    """Calls of any class a module imports from `testcontainers`, whatever its name."""
    refs: list[tuple[str, str]] = []
    for path in _tracked("*.py"):
        text = path.read_text()
        if "testcontainers" not in text:
            continue
        names = _testcontainers_names(ast.parse(text))
        for call in re.finditer(r"\b(\w+)\(", text):
            if call.group(1) not in names:
                continue
            arguments = text[call.end() : call.end() + 400]
            match = _STRING_ARG.match(arguments) or _IMAGE_KWARG.search(
                arguments[: arguments.find(")")]
            )
            assert match, (
                f"{_rel(path)}: {call.group(0)} has no string-literal image argument this guard "
                "can read - pass the image as a literal"
            )
            refs.append((_rel(path), match.group("image")))
    return refs


def _image_refs() -> list[tuple[str, str]]:
    return _compose_refs() + _workflow_refs() + _dockerfile_refs() + _testcontainer_refs()


def _dev_compose_neo4j_ref() -> str:
    services = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text())["services"]
    [neo4j_ref] = [
        service["image"]
        for service in services.values()
        if str(service.get("image", "")).startswith("neo4j:")
    ]
    return neo4j_ref


def test_image_references_are_found():
    sources = {source for source, _ in _image_refs()}
    assert {
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.demo.yml",
        "examples/runtime-demo/Dockerfile",
        "examples/release-golden-path/compose/docker-compose.base.yml",
        "tests/integration/conftest.py",
    } <= sources


@pytest.mark.parametrize(
    ("source", "image"),
    [(source, image) for source, image in _image_refs() if source not in _FROZEN_UNPINNED],
)
def test_image_is_pinned_by_digest(source, image):
    assert _DIGEST_PINNED.match(image), f"{source}: {image} is not pinned by digest"


def test_frozen_unpinned_exceptions_are_still_frozen():
    frozen = {
        line.split(maxsplit=1)[1] for line in _GOLDEN_PATH_SHA256SUMS.read_text().splitlines()
    }
    for source in _FROZEN_UNPINNED:
        assert source in frozen, f"{source} is no longer frozen - pin it and drop the exception"


def test_testcontainers_neo4j_matches_the_dev_compose_pin():
    expected = _dev_compose_neo4j_ref()
    for path in _tracked("*.py"):
        for match in _NEO4J_CONTAINER.finditer(path.read_text()):
            image = match.group("image")
            assert image == expected, f"{_rel(path)}: {image} != {expected}"
    demo_images = [
        image for source, image in _compose_refs() if source == "docker-compose.demo.yml"
    ]
    assert expected in demo_images
