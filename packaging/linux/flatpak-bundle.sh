#!/usr/bin/env bash
# Repackage a DeckZ Linux tarball as a single-file Flatpak bundle:
#
#   $DIST/deckz-<version>-linux-<arch>.flatpak
#
# Usage: packaging/linux/flatpak-bundle.sh [--no-test] [TARBALL]
#
# TARBALL defaults to $DIST/deckz-<version>-linux-<arch>.tar.gz from package.sh. The bundle
# is built for the host architecture (x86_64 or aarch64), which must match the tarball's.
# Needs flatpak, flatpak-builder and the SVG pixbuf loader (librsvg2-common) for the host's
# `appstreamcli compose`; the freedesktop runtime and SDK named in the manifest are
# installed per-user from Flathub. Unless --no-test, the bundle is then installed per-user and
# `deckz-cli --version` is run inside the sandbox as a smoke test.
# Manifest: packaging/linux/flatpak/com.pintaz.deckz.bundle.yml.
set -euo pipefail
# shellcheck source=../common.sh
. "$(dirname "${BASH_SOURCE[0]}")/../common.sh"
HERE="$ROOT/packaging/linux"
APP_ID=com.pintaz.deckz
FLATPAK_ID="$APP_ID"
# The remote indexes both app IDs on the stable ref branch; IDs isolate installations.
FLATPAK_BRANCH=stable
if [[ "${DECKZ_BUILD_CHANNEL:-}" == nightly-v1 || "$VERSION" == *-nightly* ]]; then
  FLATPAK_ID="$APP_ID.nightly"
fi
FLATHUB=https://dl.flathub.org/repo/flathub.flatpakrepo

TEST=1
OCI=0
TARBALL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-test) TEST=0; shift ;;
    --oci) OCI=1; shift ;;
    -h | --help) sed -n '2,14p' "$0"; exit 0 ;;
    -*) echo "unknown argument: $1" >&2; exit 2 ;;
    *) TARBALL="$1"; shift ;;
  esac
done

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64) ;;
  aarch64 | arm64) ARCH=aarch64 ;;
  *) echo "unsupported architecture $ARCH" >&2; exit 2 ;;
esac
BASENAME="deckz-$VERSION-linux-$ARCH"
TARBALL="${TARBALL:-$DIST/$BASENAME.tar.gz}"
[[ -f "$TARBALL" ]] || { echo "error: $TARBALL not found (run packaging/linux/package.sh --formats tar first)" >&2; exit 1; }
for tool in flatpak flatpak-builder; do
  command -v "$tool" >/dev/null || { echo "error: $tool not found (apt install flatpak flatpak-builder librsvg2-common)" >&2; exit 1; }
done

echo "==> DeckZ $VERSION Flatpak bundle for $ARCH from $(basename "$TARBALL")"

WORK="$CARGO_TARGET_DIR/flatpak-bundle"
rm -rf "$WORK"
mkdir -p "$WORK/stage"
tar -xzf "$TARBALL" -C "$WORK/stage" --strip-components=1
if [[ "$FLATPAK_ID" != "$APP_ID" ]]; then
  # The nightly tarball already carries its launcher and a GUI named for it, so the bundle
  # installs both rather than generating a sixth wrapper.
  [[ -x "$WORK/stage/bin/deckz-bin" && -x "$WORK/stage/bin/deckz-nightly" ]] \
    || { echo "error: the nightly $TARBALL has no bin/deckz-bin and bin/deckz-nightly" >&2; exit 1; }
  NIGHTLY_ICON="$ROOT/assets/app-icon/deckz-nightly.png"
  [[ -f "$NIGHTLY_ICON" ]] || NIGHTLY_ICON="$ROOT/assets/app-icon/hicolor/256x256/apps/$APP_ID.png"
  # Two ids meet here on purpose. The bundle id is the Flatpak app id (`$APP_ID.nightly`), so the
  # exported desktop entry, its basename and the icon carry it. The window keeps the flavor id
  # (`$APP_ID.nightly-v1`) that every other Linux format's desktop entry is renamed to, so
  # StartupWMClass names the window id: that is what ties this launcher to the running window.
  sed -e "s|^Icon=$APP_ID$|Icon=$FLATPAK_ID|" \
      -e "s|^Name=DeckZ$|Name=DeckZ Nightly|" \
      -e "s#^Exec=deckz\\([[:space:]]\\|$\\)#Exec=deckz-nightly\\1#" \
      -e "s|^TryExec=deckz$|TryExec=deckz-nightly|" \
      -e 's|^StartupWMClass=.*|StartupWMClass=com.pintaz.deckz.nightly-v1|' \
      -e '/^MimeType=/d' \
      "$WORK/stage/share/applications/$APP_ID.desktop" >"$WORK/stage/share/applications/$FLATPAK_ID.desktop"
  rm -f "$WORK/stage/share/applications/$APP_ID.desktop"
  sed -e "s|<id>$APP_ID</id>|<id>$FLATPAK_ID</id>|g" \
      -e "s|<name>DeckZ</name>|<name>DeckZ Nightly</name>|g" \
      -e "s|<launchable type=\"desktop-id\">$APP_ID.desktop</launchable>|<launchable type=\"desktop-id\">$FLATPAK_ID.desktop</launchable>|g" \
      -e "s|<icon type=\"stock\">$APP_ID</icon>|<icon type=\"stock\">$FLATPAK_ID</icon>|g" \
      -e '/<mediatype>/d' \
      "$WORK/stage/share/metainfo/$APP_ID.metainfo.xml" >"$WORK/stage/share/metainfo/$FLATPAK_ID.metainfo.xml"
  rm -f "$WORK/stage/share/metainfo/$APP_ID.metainfo.xml"
  mv "$WORK/stage/share/mime/packages/$APP_ID.xml" "$WORK/stage/share/mime/packages/$FLATPAK_ID.xml"
  rm -rf "$WORK/stage/share/icons/hicolor"
  install -Dm644 "$NIGHTLY_ICON" \
    "$WORK/stage/share/icons/hicolor/256x256/apps/$FLATPAK_ID.png"
  # Flatpak starts `command`, and the desktop entry's Exec names the same launcher; the GUI sits
  # beside it in /app/bin, where the launcher looks first.
  sed -e "s|ai\.storyteller\.deckz|$FLATPAK_ID|g" \
      -e 's|^command: deckz$|command: deckz-nightly|' \
      -e 's|^      - install -Dm755 bin/deckz /app/bin/deckz$|      - install -Dm755 bin/deckz-bin /app/bin/deckz-bin\n      - install -Dm755 bin/deckz-nightly /app/bin/deckz-nightly|' \
      -e 's|<binary>deckz</binary>|<binary>deckz-nightly</binary>|' \
      "$HERE/flatpak/$APP_ID.bundle.yml" >"$WORK/$FLATPAK_ID.yml"
  # A template change must fail here, not as a bundle whose menu entry cannot find a program.
  for expected in 'command: deckz-nightly' \
    '      - install -Dm755 bin/deckz-bin /app/bin/deckz-bin' \
    '      - install -Dm755 bin/deckz-nightly /app/bin/deckz-nightly'; do
    grep -qxF "$expected" "$WORK/$FLATPAK_ID.yml" || {
      echo "error: the nightly Flatpak manifest lost \"$expected\"" >&2
      exit 1
    }
  done
else
  [[ -x "$WORK/stage/bin/deckz" ]] || { echo "error: $TARBALL has no bin/deckz" >&2; exit 1; }
  cp "$HERE/flatpak/$APP_ID.bundle.yml" "$WORK/$FLATPAK_ID.yml"
fi

flatpak remote-add --user --if-not-exists flathub "$FLATHUB"
# --disable-rofiles-fuse: no FUSE in containers and CI runners.
flatpak-builder --user --install-deps-from=flathub --disable-rofiles-fuse --force-clean \
  --default-branch="$FLATPAK_BRANCH" --repo="$WORK/repo" --state-dir="$WORK/state" "$WORK/build" "$WORK/$FLATPAK_ID.yml"

OUT="$DIST/$BASENAME.flatpak"
# --runtime-repo lets `flatpak install` fetch the freedesktop runtime from Flathub if missing.
flatpak build-bundle --runtime-repo="$FLATHUB" "$WORK/repo" "$OUT" "$FLATPAK_ID" "$FLATPAK_BRANCH"
echo "wrote $OUT"
if [[ "$OCI" = 1 ]]; then
  OUT_OCI="$DIST/$BASENAME-oci"
  rm -rf "$OUT_OCI"
  flatpak build-bundle --oci "$WORK/repo" "$OUT_OCI" "$FLATPAK_ID" "$FLATPAK_BRANCH"
  echo "wrote OCI layout to $OUT_OCI"
fi

if [[ "$TEST" = 1 ]]; then
  flatpak install --user -y --noninteractive --reinstall "$OUT"
  flatpak info --user "$FLATPAK_ID"
  flatpak run --command=deckz-cli "$FLATPAK_ID" --version
  flatpak run --command=sh "$FLATPAK_ID" -c 'ls /app/share/applications /app/share/metainfo /app/share/mime/packages /app/share/icons/hicolor/*/apps'
fi
echo "==> done"
ls -lh "$OUT"
