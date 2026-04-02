#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="${ROOT_DIR}/dist/macos"
BUILD_DIR="${ROOT_DIR}/build/pyinstaller-macos"
PYTHON_BIN="python3"

cd "${ROOT_DIR}"

if [[ -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  # Prefer the project venv when it exists.
  source ".venv/bin/activate"
  PYTHON_BIN="python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "Python is required but was not found in PATH."
  exit 1
fi

if ! "${PYTHON_BIN}" -m pip --version >/dev/null 2>&1; then
  "${PYTHON_BIN}" -m ensurepip --upgrade
fi

"${PYTHON_BIN}" -m pip install -U pyinstaller

rm -rf "${DIST_DIR}" "${BUILD_DIR}"

"${PYTHON_BIN}" -m PyInstaller \
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
