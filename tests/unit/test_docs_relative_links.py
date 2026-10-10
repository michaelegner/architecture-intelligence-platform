"""Keep ordinary Markdown links bound to paths tracked by this repository.

Offline and read-only: `git ls-files` is the source of truth, so an untracked
local file cannot hide a broken link from a clean checkout.
"""

from __future__ import annotations

import posixpath
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
MARKDOWN_LINK = re.compile(
    r"""!?\[[^\]\n]*\]\(\s*(?P<target><[^>\n]+>|[^\s)]+)(?:\s+["'][^"']*["'])?\s*\)"""
)


def _indexed_files(root: Path) -> frozenset[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--full-name", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return frozenset(path for path in result.stdout.decode("utf-8").split("\0") if path)


def _sources(root: Path) -> list[Path]:
    return [root / "README.md", root / "CONTRIBUTING.md", *sorted((root / "docs").glob("*.md"))]


def _broken_links(root: Path, indexed: frozenset[str], sources: list[Path]) -> list[str]:
    errors: list[str] = []
    for source in sources:
        relative = source.relative_to(root).as_posix()
        text = source.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK.finditer(text):
            target = match.group("target").removeprefix("<").removesuffix(">")
            if target.startswith(("#", "//")):
                continue
            parsed = urlsplit(target)
            if parsed.scheme.lower() in {"http", "https", "mailto"}:
                continue
            if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
                continue  # not a relative filesystem link
            if not parsed.path:
                continue  # a fragment-only link
            normalized = posixpath.normpath(
                posixpath.join(posixpath.dirname(relative), unquote(parsed.path))
            )
            exists = normalized in indexed or any(
                item.startswith(normalized + "/") for item in indexed
            )
            if not exists:
                line = text.count("\n", 0, match.start()) + 1
                errors.append(f"{relative}:{line}: broken relative target {target!r}")
    return errors


def test_documentation_relative_links_resolve_from_git_index() -> None:
    broken = _broken_links(ROOT, _indexed_files(ROOT), _sources(ROOT))
    assert not broken, "\n".join(broken)


def test_deliberately_broken_link_fails_with_source_and_target(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    source.write_text("# Guide\nSee [missing](../missing.md#example).\n", encoding="utf-8")
    errors = _broken_links(tmp_path, frozenset({"docs/guide.md"}), [source])
    assert errors == ["docs/guide.md:2: broken relative target '../missing.md#example'"]


def test_indexed_directory_and_percent_encoded_target_are_valid(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    source.write_text(
        "[ADRs](adr/) [doc](document%20one.md#topic) [external](https://example.org/a) "
        "[email](mailto:maintainer@example.org) [anchor](#topic)\n",
        encoding="utf-8",
    )
    indexed = frozenset({"docs/guide.md", "docs/adr/0001.md", "docs/document one.md"})
    assert _broken_links(tmp_path, indexed, [source]) == []


def test_untracked_files_do_not_mask_broken_links(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("[not indexed](only-on-disk.md)\n", encoding="utf-8")
    (tmp_path / "only-on-disk.md").write_text("not added to git\n", encoding="utf-8")
    broken = _broken_links(tmp_path, frozenset({"README.md"}), [readme])
    assert len(broken) == 1
    assert "only-on-disk.md" in broken[0]
