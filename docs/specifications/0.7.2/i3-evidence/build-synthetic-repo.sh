#!/usr/bin/env bash
# Builds the I3 synthetic Sokol111 repository that both arms work in (README.md, "Synthetic repository").
# One commit: the ecommerce-workspace tree with the seven other frozen repositories nested in it, at the
# I2 freeze commits, plus the C1-time stock rpk outputs. Needs gh (public tarballs) and git.
set -euo pipefail

OUT=${1:?usage: build-synthetic-repo.sh <new-directory>}
HERE=$(cd "$(dirname "$0")" && pwd)
PKG=$HERE/../i2-evidence/sokol111
[ ! -e "$OUT" ] || { echo "STOP: $OUT already exists" >&2; exit 1; }

REPOS="ecommerce-workspace ecommerce-infrastructure ecommerce-commons ecommerce-catalog-service
ecommerce-catalog-service-api ecommerce-product-query-service ecommerce-image-service
ecommerce-category-query-service"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$OUT"
for repo in $REPOS; do
  sha=$(grep "\`Sokol111/$repo\`" "$PKG/freeze.md" | grep -o '[0-9a-f]\{40\}')
  gh api "repos/Sokol111/$repo/tarball/$sha" > "$TMP/$repo.tgz"
  dest=$OUT/$repo
  [ "$repo" != ecommerce-workspace ] || dest=$OUT
  mkdir -p "$dest"
  tar -xzf "$TMP/$repo.tgz" -C "$dest" --strip-components=1
  echo "$repo $sha"
done

# The workspace ignores its nested repositories (each has its own git upstream). Here they are part of
# the one commit, and ignored paths would be invisible to the agents' search tools.
sed -i '/^ecommerce-[a-z-]*\/$/d' "$OUT/.gitignore"

# Raw broker evidence for both arms: stock rpk output around C1 only (G1, topic, versions, G1').
EVIDENCE=$OUT/ops-evidence/kafka-local-2026-10-21T17-53Z
mkdir -p "$EVIDENCE"
cp "$PKG"/raw/0[1-8]-*.txt "$PKG"/raw/0[1-8]-*.meta "$PKG"/raw/1[1-4]-*.txt "$PKG"/raw/1[1-4]-*.meta "$EVIDENCE/"
cat > "$EVIDENCE/README.md" <<'EOF'
# Kafka consumer-group state, local environment, 2026-10-21 ~17:53Z

Stock `rpk` output from the Redpanda broker of the documented local environment
(`ecommerce-infrastructure/environments/local`), taken while the services ran. Each `.txt` is the
command's stdout; its `.meta` holds the UTC time, the command and the exit code. Files 01-08 and 11-14
are two passes around the same moment. This environment is no longer running.
EOF

git -C "$OUT" init -q -b main
git -C "$OUT" add -A
# Fixed identity and dates, so a rebuild reproduces the same commit id.
GIT_AUTHOR_DATE=2026-10-21T00:00:00Z GIT_COMMITTER_DATE=2026-10-21T00:00:00Z \
  git -C "$OUT" -c user.name=aip-i3 -c user.email=aip-i3@localhost -c commit.gpgsign=false \
  commit -q -m "Sokol111 frozen workspace (v0.7.2 I3 synthetic repository)"
git -C "$OUT" rev-parse HEAD
