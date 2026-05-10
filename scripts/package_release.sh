#!/bin/zsh
set -euo pipefail

VERSION="${1:-1.6.1}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RELEASE_DIR="$ROOT_DIR/release"
APP_NAME="Codex History Sync Tool.app"

make_dmg() {
  local source_app="$1"
  local output_name="$2"
  local staging_dir="$RELEASE_DIR/staging/$output_name"
  local output_path="$RELEASE_DIR/$output_name.dmg"

  rm -rf "$staging_dir" "$output_path"
  mkdir -p "$staging_dir"
  /usr/bin/ditto "$source_app" "$staging_dir/$APP_NAME"
  ln -s /Applications "$staging_dir/Applications"
  /usr/bin/hdiutil create \
    -volname "Codex History Sync Tool" \
    -srcfolder "$staging_dir" \
    -ov \
    -format UDZO \
    "$output_path"
  /usr/bin/hdiutil verify "$output_path"
}

copy_runtime_scripts() {
  local app_path="$1"
  mkdir -p "$app_path/Contents/Resources"
  /bin/cp "$ROOT_DIR/sync_backend.py" "$app_path/Contents/Resources/"
  /bin/cp "$ROOT_DIR/auto_sync_watcher.py" "$app_path/Contents/Resources/"
  if [[ -f "$app_path/Contents/Resources/launch_ui_mac.py" ]]; then
    /bin/cp "$ROOT_DIR/launch_ui_mac.py" "$app_path/Contents/Resources/"
  fi
}

rm -rf "$RELEASE_DIR/staging"
mkdir -p "$RELEASE_DIR"

copy_runtime_scripts "$ROOT_DIR/$APP_NAME"
copy_runtime_scripts "$ROOT_DIR/dist/pyinstaller-arm64/$APP_NAME"
copy_runtime_scripts "$ROOT_DIR/dist/pyinstaller-x86_64/$APP_NAME"

make_dmg "$ROOT_DIR/$APP_NAME" "Codex-History-Sync-Tool-v$VERSION-Lite"
make_dmg "$ROOT_DIR/dist/pyinstaller-arm64/$APP_NAME" "Codex-History-Sync-Tool-v$VERSION-Apple-Silicon"
make_dmg "$ROOT_DIR/dist/pyinstaller-x86_64/$APP_NAME" "Codex-History-Sync-Tool-v$VERSION-Intel"

/usr/bin/shasum -a 256 "$RELEASE_DIR"/Codex-History-Sync-Tool-v"$VERSION"-*.dmg > "$RELEASE_DIR/SHA256SUMS-v$VERSION.txt"
rm -rf "$RELEASE_DIR/staging"

echo "Release artifacts:"
ls -lh "$RELEASE_DIR"/Codex-History-Sync-Tool-v"$VERSION"-*.dmg "$RELEASE_DIR/SHA256SUMS-v$VERSION.txt"
