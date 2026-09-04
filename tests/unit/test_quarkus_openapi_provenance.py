"""Guards the verbatim, byte-identical OpenAPI copies against accidental local edits
(PR #40 review N1).

Each expected hash is the exact Git blob SHA GitHub's own API reports for that file at the pinned
commit `8ea03377bfe7a89c49e1ccc0e501bf5fafbc2cce` (`GET
/repos/quarkusio/quarkus-super-heroes/git/trees/<sha>?recursive=1`) - independently verifiable via
`git hash-object <file>` against a real checkout of that commit.
"""

import hashlib
from pathlib import Path

DECLARATIONS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "docs"
    / "real-world-validation"
    / "quarkus-super-heroes"
    / "runtime"
    / "declarations"
)

# service -> known upstream git blob SHA for src/main/resources/openapi/openapi.yml
EXPECTED_BLOB_SHA = {
    "rest-fights": "847ed5d03ae403930e2a2b59e45aa41dc2c3d9ea",
    "rest-heroes": "628919b5602b928ce23f718fce6df77cbb3fd946",
    "rest-villains": "422ceaa0dd48643db26422ddc3984a6cffe9540b",
    "rest-narration": "6c5f86e423398d035632554a216b8e7478ad11b6",
}


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode()
    return hashlib.sha1(header + content).hexdigest()


def test_copied_openapi_documents_are_byte_identical_to_the_pinned_commit():
    for service, expected_sha in EXPECTED_BLOB_SHA.items():
        content = (DECLARATIONS_DIR / service / "openapi.yml").read_bytes()
        assert _git_blob_sha(content) == expected_sha, (
            f"{service}/openapi.yml no longer matches the pinned upstream commit's blob"
        )
