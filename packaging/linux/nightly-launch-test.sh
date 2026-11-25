#!/usr/bin/env bash
# Validate the nightly launcher in every Linux placement without building or opening DeckZ:
# the flat nightly tar (`deckz` + `deckz-bin`), the AppImage (`AppRun` + `usr/bin/deckz`),
# the distro tree (`bin/deckz-nightly` + `bin/deckz-bin`) and the /usr/bin rule that reaches
# the fixed /usr/lib copy. A recorder binary stands in for the GUI and prints its argv.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
launcher="$HERE/nightly-launch.sh"
export HOME="$work/home"
mkdir -p "$HOME"
export XDG_CONFIG_HOME="$HOME/.config" XDG_DATA_HOME="$HOME/.local/share"
profile="$XDG_DATA_HOME/deckz-nightly/launcher/profiles/deckz"

recorder() {
  mkdir -p "$(dirname "$1")"
  cat >"$1" <<'RECORDER'
#!/bin/sh
printf '<%s>\n' "$@"
RECORDER
  chmod 755 "$1"
}

expect() {
  binary="$1"
  expected="$2"
  shift 2
  actual=$("$binary" "$@")
  if [[ "$actual" != "$expected" ]]; then
    printf '%s\nexpected:\n%s\nactual:\n%s\n' "$binary" "$expected" "$actual" >&2
    exit 1
  fi
}
nightly_argv() {
  printf '<%s>\n' --launch-profile nightly-v1 --profile-root "$profile" --
}

# ---- the flat nightly tar: `deckz` launcher, `deckz-bin` GUI ----
flat="$work/flat"
recorder "$flat/deckz-bin"
cp "$launcher" "$flat/deckz"
chmod 755 "$flat/deckz"
expect "$flat/deckz" "$(nightly_argv)"
expect "$flat/deckz" "$(nightly_argv; printf '<%s>\n' 'deck with spaces.pptx' '--other-name.pptx')" \
  'deck with spaces.pptx' '--other-name.pptx'
expect "$flat/deckz" "$(nightly_argv; printf '<%s>\n' 'deck.pptx')" -- deck.pptx
expect "$flat/deckz" '<--version>' --version
expect "$flat/deckz" '<-V>' -V
expect "$flat/deckz" '<--help>' --help
expect "$flat/deckz" "$(printf '<%s>\n' --launch-profile nightly-v1 --profile-root "$work/launcher" -- 'deck.pptx')" \
  --launch-profile nightly-v1 --profile-root "$work/launcher" -- 'deck.pptx'
test ! -e "$profile"

# ---- the AppImage: AppRun at the mount root, the GUI and the entry's copy in usr/bin ----
appdir="$work/DeckZ.AppDir"
recorder "$appdir/usr/bin/deckz-bin"
cp "$launcher" "$appdir/AppRun"
chmod 755 "$appdir/AppRun"
expect "$appdir/AppRun" "$(nightly_argv; printf '<%s>\n' book.pptx)" book.pptx
cp "$launcher" "$appdir/usr/bin/deckz-nightly"
chmod 755 "$appdir/usr/bin/deckz-nightly"
expect "$appdir/usr/bin/deckz-nightly" "$(nightly_argv; printf '<%s>\n' book.pptx)" book.pptx
test ! -e "$profile"

# ---- the distro tree tarball: bin/deckz-nightly beside bin/deckz-bin ----
tree="$work/tree/bin"
recorder "$tree/deckz-bin"
cp "$launcher" "$tree/deckz-nightly"
chmod 755 "$tree/deckz-nightly"
actual=$(PATH="$tree:$PATH" deckz-nightly book.pptx)
[[ "$actual" == "$(nightly_argv; printf '<%s>\n' book.pptx)" ]] || { printf 'a PATH invocation printed:\n%s\n' "$actual" >&2; exit 1; }
test ! -e "$profile"

# ---- a missing GUI fails closed, and so does a tree with no data folder ----
empty="$work/empty"
mkdir -p "$empty"
cp "$launcher" "$empty/deckz"
chmod 755 "$empty/deckz"
status=0
"$empty/deckz" book.pptx >/dev/null 2>&1 || status=$?
[[ "$status" -eq 2 ]] || { printf 'a launcher with no GUI must exit 2, got %s\n' "$status" >&2; exit 1; }
recorder "$work/nodata/deckz-bin"
cp "$launcher" "$work/nodata/deckz"
chmod 755 "$work/nodata/deckz"
status=0
env -u XDG_DATA_HOME -u HOME "$work/nodata/deckz" book.pptx >/dev/null 2>&1 || status=$?
[[ "$status" -eq 2 ]] || { printf 'a launcher with no data folder must exit 2, got %s\n' "$status" >&2; exit 1; }
# A query is not a launch: it answers without a data folder instead of becoming that error.
actual=$(env -u XDG_DATA_HOME -u HOME "$work/nodata/deckz" --version) \
  || { printf 'a no-data-folder --version must still answer\n' >&2; exit 1; }
[[ "$actual" == '<--version>' ]] || { printf 'a no-data-folder --version printed:\n%s\n' "$actual" >&2; exit 1; }

# ---- the /usr/bin rule: the fixed /usr/lib copy is named, and no parent path is ever used ----
# The launcher's text is searched literally, so `$here` must not expand here.
# shellcheck disable=SC2016
grep -Fq '[ "$here" = /usr/bin ]' "$launcher"
grep -Fq '/usr/lib/deckz-nightly/deckz' "$launcher"
if grep -q '\.\.' "$launcher"; then
  echo "the launcher must not reach outside its own folder or the fixed /usr/lib path" >&2
  exit 1
fi

echo "PASS: nightly launcher starts the GUI with the profile in every layout and refuses the rest"
