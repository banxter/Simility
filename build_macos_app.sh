#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
APP_BUNDLE="$PROJECT_DIR/dist/Simility.app"

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

echo "Built: $APP_BUNDLE"
