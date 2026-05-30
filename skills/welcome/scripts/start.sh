#!/usr/bin/env bash
# SPDX-License-Identifier: MulanPSL-2.0
# welcome skill start phase. rbnx boot 在 RegisterCapability 后 exec 此脚本。
set -euo pipefail
PKG="${RBNX_PACKAGE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$PKG"

VENV="rbnx-build/venv"
CODEGEN="rbnx-build/codegen"
if [[ ! -d "$VENV" ]]; then
    echo "[welcome/start] ERR: $VENV 不存在 — 先跑 scripts/build.sh" >&2
    exit 2
fi
if [[ ! -d "$CODEGEN/proto_gen" ]] || [[ ! -d "$CODEGEN/robonix_mcp_types" ]]; then
    echo "[welcome/start] ERR: $CODEGEN/proto_gen|robonix_mcp_types 缺失 — 跑 scripts/build.sh" >&2
    exit 2
fi

# proto_gen 提供 robonix_contracts_pb2 + grpc stubs;
# robonix_mcp_types 提供 welcome_mcp / speech_pb2 / std_msgs_pb2 数据类。
export PYTHONPATH="$PKG/$CODEGEN/proto_gen:$PKG/$CODEGEN/robonix_mcp_types:${PYTHONPATH:-}"
exec "$PKG/$VENV/bin/python" -m welcome_skill.atlas_bridge
