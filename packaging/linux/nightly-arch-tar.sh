#!/usr/bin/env bash
# Stage the DeckZ Nightly-only handoff for the Arch packager.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
source_tree="$1"
work="$2"
destination="$3"
basename="$4"
stage="$work/$basename"

mkdir -p "$work"
cp -R "$source_tree" "$stage"
mkdir "$stage/bin/.deckz-nightly"
mv "$stage/bin/deckz" "$stage/bin/.deckz-nightly/deckz-bin"
cp "$here/nightly-launch.sh" "$stage/bin/deckz"
chmod 755 "$stage/bin/deckz"
tar -C "$work" -czf "$destination/$basename.tar.gz" "$basename"
echo "wrote $destination/$basename.tar.gz"
