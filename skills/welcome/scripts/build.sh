#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# welcome skill build phase.
set -euo pipefail
: "${UV_INDEX_URL:=https://pypi.tuna.tsinghua.edu.cn/simple}"
: "${PIP_INDEX_URL:=https://pypi.tuna.tsinghua.edu.cn/simple}"
export UV_INDEX_URL PIP_INDEX_URL

PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

BUILD="rbnx-build"
VENV="$BUILD/venv"
mkdir -p "$BUILD/data"

# ── uv venv + sync ──────────────────────────────────────────────────────────
if ! command -v uv >/dev/null 2>&1; then
    echo "[welcome/build] ERR: 'uv' not on PATH" >&2
    exit 1
fi
if [[ ! -d "$VENV" ]]; then
    echo "[welcome/build] uv venv → $VENV"
    uv venv "$VENV"
fi
echo "[welcome/build] uv sync"
VIRTUAL_ENV="$PKG/$VENV" uv sync --active --no-managed-python

# ── Codegen: --mcp 才会生成 welcome_mcp.py + grpc stubs ─────────────────────
echo "[welcome/build] rbnx codegen --mcp"
rbnx codegen -p "$PKG" --mcp

echo "[welcome/build] done."
