#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
APP_BUNDLE="$PROJECT_DIR/dist/Simility.app"
DMG_FILE="$PROJECT_DIR/dist/Simility.dmg"
ICON_FILE="$PROJECT_DIR/assets/Simility.icns"

if [[ ! -x "$PYTHON" ]]; then
  echo "Virtual environment not found. Create it first with: python3 -m venv .venv"
  exit 1
fi

if [[ ! -f "$ICON_FILE" ]]; then
  echo "App icon not found: $ICON_FILE"
  exit 1
fi

if ! "$PYTHON" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller is required to build the macOS app."
  echo "Install it with: $PYTHON -m pip install pyinstaller"
  exit 1
fi

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name Simility \
  --icon "$ICON_FILE" \
  --osx-bundle-identifier com.simility.desktop \
  "$PROJECT_DIR/Simility.py"

# Remove macOS metadata that prevents ad-hoc signing on some installations.
# Framework bundles can carry Finder metadata on nested paths, so clear it
# recursively before signing the completed app bundle.
xattr -cr "$APP_BUNDLE"
codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

# Build a Finder-ready installer image: users drag Simility.app to the
# Applications alias shown when they open the disk image.
mkdir -p "$PROJECT_DIR/build"
DMG_STAGING_DIR="$(mktemp -d "$PROJECT_DIR/build/simility-dmg.XXXXXX")"
RW_DMG_FILE="$PROJECT_DIR/build/Simility-rw.dmg"
MOUNT_POINT="$PROJECT_DIR/build/Simility-volume"
cleanup_dmg_build() {
  hdiutil detach "$MOUNT_POINT" -quiet 2>/dev/null || true
  rm -rf "$DMG_STAGING_DIR" "$MOUNT_POINT"
  rm -f "$RW_DMG_FILE"
}
trap cleanup_dmg_build EXIT
ditto "$APP_BUNDLE" "$DMG_STAGING_DIR/Simility.app"
ln -s /Applications "$DMG_STAGING_DIR/Applications"
ditto "$ICON_FILE" "$DMG_STAGING_DIR/.VolumeIcon.icns"
SetFile -a V "$DMG_STAGING_DIR/.VolumeIcon.icns"
hdiutil create \
  -volname "Simility" \
  -srcfolder "$DMG_STAGING_DIR" \
  -ov \
  -format UDRW \
  "$RW_DMG_FILE"
mkdir -p "$MOUNT_POINT"
hdiutil attach "$RW_DMG_FILE" -nobrowse -mountpoint "$MOUNT_POINT"
SetFile -a C "$MOUNT_POINT"
hdiutil detach "$MOUNT_POINT" -quiet
hdiutil convert "$RW_DMG_FILE" -format UDZO -ov -o "$DMG_FILE"
hdiutil verify "$DMG_FILE"

echo "Built app: $APP_BUNDLE"
echo "Built installer: $DMG_FILE"
