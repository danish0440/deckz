#!/usr/bin/env bash
# Validate the staged Arch launcher without building or opening DeckZ.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/source"
dst="$work/dist"
base=deckz-0.0.1-nightly.1-linux-x86_64
mkdir -p "$stage/bin" "$dst" "$work/extract"

# A local argv recorder stands in for the compiled binaries. It never opens a UI.
cat >"$stage/bin/deckz" <<'RECORDER'
#!/bin/sh
printf '<%s>\n' "$@"
RECORDER
chmod 755 "$stage/bin/deckz"
cp "$stage/bin/deckz" "$stage/bin/deckz-cli"

bash "$HERE/nightly-arch-tar.sh" "$stage" "$work/stage" "$dst" "$base"
tar -xzf "$dst/$base.tar.gz" -C "$work/extract"
bin="$work/extract/$base/bin"
# Simulate the existing Arch bin-tree copy and public launcher rename.
mkdir -p "$work/installed"
cp -R "$bin" "$work/installed/bin"
bin="$work/installed/bin"
mv "$bin/deckz" "$bin/deckz-nightly"
mv "$bin/deckz-cli" "$bin/deckz-nightly-cli"

[[ ! -e "$stage/bin/.deckz-nightly" ]]
cmp "$stage/bin/deckz" "$bin/.deckz-nightly/deckz-bin"
cmp "$stage/bin/deckz-cli" "$bin/deckz-nightly-cli"
export HOME="$work/home"
mkdir -p "$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share"
expect() {
  expected="$1"
  shift
  actual=$(PATH="$bin:$PATH" deckz-nightly "$@")
  if [[ "$actual" != "$expected" ]]; then
    printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2
    exit 1
  fi
}
profile="$XDG_DATA_HOME/deckz-nightly/launcher/profiles/deckz"
nightly_argv() {
  printf '<%s>\n' --launch-profile nightly-v1 --profile-root "$profile" --
}
expect "$(nightly_argv)"
expect "$(nightly_argv; printf '<%s>\n' 'deck with spaces.pptx' '--other-name.deckz')" \
  'deck with spaces.pptx' '--other-name.deckz'
# A caller-written `--` is the launcher's own separator: it is never passed on as a file name.
expect "$(nightly_argv; printf '<%s>\n' 'deck.pptx')" -- deck.pptx
# A bare version query stays a version query, not a file name, and creates no profile.
expect '<--version>' --version
expect '<-V>' -V
# The Launcher's own protocol is passed through untouched, never wrapped a second time.
expect "$(printf '<%s>\n' --launch-profile nightly-v1 --profile-root "$work/launcher" -- 'deck.pptx')" \
  --launch-profile nightly-v1 --profile-root "$work/launcher" -- 'deck.pptx'
test ! -e "$profile"
# A profile needs a data folder: the launcher refuses instead of writing into /.
status=0
env -u XDG_DATA_HOME -u HOME PATH="$bin:$PATH" deckz-nightly deck.pptx >/dev/null 2>&1 || status=$?
[[ "$status" -eq 2 ]] || { printf 'expected exit 2 without XDG_DATA_HOME/HOME, got %s\n' "$status" >&2; exit 1; }
test ! -e "$work/home/.local/share/deckz-nightly"

echo "PASS: Arch Nightly handoff stages the hidden GUI, the shared launcher and the launch arguments"
