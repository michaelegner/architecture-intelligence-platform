#!/usr/bin/env bash
# v0.5.0 I6 §7.4: the only entry point of the release golden path.
#
#   RELEASE_CANDIDATE_SHA=<40-hex> examples/release-golden-path/run.sh <IMAGE_REF> <OUT_DIR>
#
# IMAGE_REF is the local candidate image or ghcr.io/...@sha256:<digest>, and it must already be
# present locally (pull it first). RELEASE_CANDIDATE_SHA is the explicit identity every answer's
# producer.build_revision must carry. It is never derived from the checkout. OUT_DIR must be absent
# or empty. The harness runs from the checkout that contains this script. For published-image
# verification (I6 §20, §21) that checkout is the tagged-source clone.
set -euo pipefail

usage() {
  echo "usage: RELEASE_CANDIDATE_SHA=<40-hex> $0 <IMAGE_REF> <OUT_DIR>" >&2
  exit 2
}

[[ $# -eq 2 ]] || usage
[[ "${RELEASE_CANDIDATE_SHA:-}" =~ ^[0-9a-f]{40}$ ]] || usage

for tool in docker uv; do
  command -v "$tool" >/dev/null || { echo "error: '$tool' is required" >&2; exit 2; }
done
docker image inspect "$1" >/dev/null 2>&1 || { echo "error: image not present locally: $1" >&2; exit 2; }

if [[ -e "$2" ]] && [[ -n "$(ls -A "$2")" ]]; then
  echo "error: OUT_DIR is not empty: $2" >&2
  exit 2
fi
mkdir -p "$2"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
exec uv run --locked python examples/release-golden-path/golden_path.py "$1" "$2"
