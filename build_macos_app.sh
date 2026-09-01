#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
APP_BUNDLE="$PROJECT_DIR/dist/Simility.app"
DMG_FILE="$PROJECT_DIR/dist/Simility.dmg"

if [[ ! -x "$PYTHON" ]]; then
  echo "Virtual environment not found. Create it first with: python3 -m venv .venv"
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
  --osx-bundle-identifier com.simility.desktop \
  "$PROJECT_DIR/Simility.py"

# Remove macOS metadata that prevents ad-hoc signing on some installations.
xattr -r -d com.apple.FinderInfo "$APP_BUNDLE" 2>/dev/null || true
xattr -r -d 'com.apple.fileprovider.fpfs#P' "$APP_BUNDLE" 2>/dev/null || true
codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

# Build a Finder-ready installer image: users drag Simility.app to the
# Applications alias shown when they open the disk image.
mkdir -p "$PROJECT_DIR/build"
DMG_STAGING_DIR="$(mktemp -d "$PROJECT_DIR/build/simility-dmg.XXXXXX")"
trap 'rm -rf "$DMG_STAGING_DIR"' EXIT
ditto "$APP_BUNDLE" "$DMG_STAGING_DIR/Simility.app"
ln -s /Applications "$DMG_STAGING_DIR/Applications"
hdiutil create \
  -volname "Simility" \
  -srcfolder "$DMG_STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_FILE"
hdiutil verify "$DMG_FILE"

echo "Built app: $APP_BUNDLE"
echo "Built installer: $DMG_FILE"
