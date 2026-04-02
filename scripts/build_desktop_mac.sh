#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist/macos"
BUILD_DIR="${ROOT_DIR}/build/pyinstaller-macos"

cd "${ROOT_DIR}"

if [[ ! -d ".venv" ]]; then
  echo "Missing .venv. Create a virtualenv first."
  exit 1
fi

source ".venv/bin/activate"

if ! python -m pip --version >/dev/null 2>&1; then
  python -m ensurepip --upgrade
fi

python -m pip install -U pyinstaller

rm -rf "${DIST_DIR}" "${BUILD_DIR}"

python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name TradingAgentsDesktop \
  --distpath "${DIST_DIR}" \
  --workpath "${BUILD_DIR}" \
  --specpath "${BUILD_DIR}" \
  --paths "${ROOT_DIR}" \
  --collect-all tradingagents \
  --collect-all cli \
  --collect-all akshare \
  --collect-all stockstats \
  --hidden-import tradingagents.desktop.app \
  --add-data "${ROOT_DIR}/assets:assets" \
  tradingagents/desktop/app.py

echo
echo "Build complete:"
echo "  ${DIST_DIR}/TradingAgentsDesktop.app"
echo "  ${DIST_DIR}/TradingAgentsDesktop/"
