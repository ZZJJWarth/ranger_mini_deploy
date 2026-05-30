# SPDX-License-Identifier: MulanPSL-2.0
"""welcome_rbnx atlas bridge — 一个 MCP 工具 (welcome) 的 skill 包。

流程:
  Trigger (chat 里说"介绍学院" / "欢迎大家" etc., LLM 调本工具)
    ↓
  1. VLM (可选, gpt-5.5 via OpenAI-compat,与 pilot 同款 endpoint)
     prompt = 官方介绍文本 + "≤80 字现场化欢迎,必须提到运行 Robonix OS"
    ↓
  2. atlas → robonix/system/speech/speak (MCP, 合成 + 播放, 单步)

设计取舍:
  - 暂不使用相机画面:car 上 realsense_camera 只 declare 了 ROS rgb/depth
    topic,没有 camera/snapshot MCP/gRPC contract。要拿图得在 skill 内
    起 rclpy 订阅,demo 前一晚增添复杂度 → 弃。文本欢迎已经够用。
  - speech.speak 是 MCP(@speech.mcp),通过 fastmcp.Client 调用 ——
    曾错写 transport="grpc" → atlas 0 命中 → 60s 超时。本文件已修正。
  - VLM 失败 / 没配 VLM env → 退到 FALLBACK 固定文本,skill 仍然成功播报。
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from robonix_api import ATLAS, Skill, Ok, Err

from .intro_text import OFFICIAL_INTRO

logging.basicConfig(level=logging.INFO,
                    format="[welcome] %(levelname)s %(message)s")
log = logging.getLogger("welcome_rbnx")

welcome_skill = Skill(id="welcome", namespace="robonix/skill/welcome")

# Atlas-resolved upstream (cached after on_activate).
_speech_endpoint: str | None = None

# OpenAI client (lazy, built once after on_activate).
_vlm_client = None
_vlm_model: str = ""

# 兜底文本: VLM 不可用时直接播这一段。必须包含"运行 Robonix 具身智能操作系统",
# 用户硬性要求 demo 中机器人自报家门。
FALLBACK_TEXT = (
    "欢迎各位老师与同学来到北京大学计算机学院!我是 Robonix 机器人,"
    "运行的是具身智能操作系统 Robonix。学院于 2021 年成立,"
    "前身是 1978 年的计算机系,现有 4 个本科专业、8 个研究所,欢迎参观。"
)

# Atlas 解析等待上限。skill 不应该把上游不在线"扛"得过久——演示场景下
# 30s 还连不上意味着 speech 真的挂了,fast-fail 优于挂死。
RESOLVE_DEADLINE_S = 30.0


def _resolve_speech_endpoint() -> str:
    """Find speech/speak MCP endpoint via atlas. Required."""
    deadline = time.time() + RESOLVE_DEADLINE_S
    last_err: str = ""
    while time.time() < deadline:
        try:
            v = ATLAS.find_unique_capability(
                contract_id="robonix/system/speech/speak",
                transport="mcp",
            )
            ch = welcome_skill.connect_capability(
                v, "robonix/system/speech/speak", "mcp",
            )
            ep = ch.endpoint
            ch.close()
            log.info("resolved speech/speak (MCP) endpoint=%s", ep)
            return ep
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            time.sleep(2.0)
    raise RuntimeError(
        f"welcome: cannot resolve robonix/system/speech/speak (mcp) "
        f"after {RESOLVE_DEADLINE_S}s — last err: {last_err}",
    )


def _build_vlm_client():
    """Construct OpenAI-compat client from VLM_* env. Same env names as
    pilot's VLM config — set them in the deploy manifest env block."""
    base = os.environ.get("VLM_BASE_URL", "").strip()
    key = os.environ.get("VLM_API_KEY", "").strip()
    model = os.environ.get("VLM_MODEL", "").strip()
    if not (base and key and model):
        log.warning(
            "VLM env not fully set (VLM_BASE_URL/VLM_API_KEY/VLM_MODEL); "
            "welcome will fall back to fixed text.",
        )
        return None, ""
    try:
        from openai import OpenAI
        return OpenAI(base_url=base, api_key=key), model
    except Exception as exc:  # noqa: BLE001
        log.warning("openai client init failed: %s — fallback only", exc)
        return None, ""


def _compose_welcome_text(audience_hint: str) -> str:
    """Ask VLM for a ≤80 字 spoken intro. Falls back to FALLBACK_TEXT
    if VLM unavailable / fails. Always returns a non-empty string."""
    if _vlm_client is None:
        return FALLBACK_TEXT
    system = (
        "你是部署在北京大学计算机学院、运行 Robonix 具身智能操作系统的迎宾机器人。"
        "你要根据下面这段【官方介绍】(事实严格保留),"
        "生成一段供你直接念出来的中文欢迎词。\n"
        "约束:\n"
        "  - 长度 ≤ 80 字 (口播约 25 秒);\n"
        "  - 必须自报家门、说明自己是运行 Robonix 具身智能操作系统的机器人;\n"
        "  - 然后挑一两条来自官方介绍的事实(成立年份 / 学科数 / 研究所数等);\n"
        "  - 不要 markdown、不要项目符号、不要解释你在做什么;\n"
        "  - 直接输出可念的文本,不带引号。\n\n"
        f"【官方介绍】{OFFICIAL_INTRO.strip()}"
    )
    user_text = (
        (f"现场提示:{audience_hint}\n" if audience_hint else "")
        + "请生成欢迎词。"
    )
    try:
        resp = _vlm_client.chat.completions.create(
            model=_vlm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            max_tokens=200,
            temperature=0.7,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            log.warning("VLM returned empty text — using fallback")
            return FALLBACK_TEXT
        return text
    except Exception as exc:  # noqa: BLE001
        log.warning("VLM call failed: %s — using fallback", exc)
        return FALLBACK_TEXT


async def _mcp_call(url: str, tool: str, args: dict) -> dict:
    """Single MCP tool round-trip via fastmcp.Client."""
    from fastmcp import Client
    async with Client(url) as c:
        result = await c.call_tool(tool, args)
        if not result.content:
            return {}
        import json
        txt = result.content[0].text
        try:
            return json.loads(txt)
        except Exception:  # noqa: BLE001
            return {"raw": txt}


def _play_speech(text: str) -> tuple[bool, str]:
    """Call speech/speak MCP tool. Returns (ok, detail).

    The welcome MCP handler runs inside FastMCP's event loop, so
    asyncio.run() here would error ("loop already running"). Same
    pattern as speech.speak: run the async call on a worker thread
    that owns its own loop.
    """
    if _speech_endpoint is None:
        return False, "speech endpoint not resolved"
    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            result = ex.submit(
                lambda: asyncio.run(
                    _mcp_call(_speech_endpoint, "speak", {"text": text, "target": ""})
                )
            ).result(timeout=60.0)
        ok = bool(result.get("ok", False))
        detail = str(result.get("detail", ""))
        return ok, detail
    except Exception as exc:  # noqa: BLE001
        log.warning("speech/speak MCP call failed: %s", exc)
        return False, str(exc)


# ── MCP tool ────────────────────────────────────────────────────────────────
from welcome_mcp import Welcome_Request, Welcome_Response  # noqa: E402


@welcome_skill.mcp("robonix/skill/welcome/welcome")
def welcome(req: Welcome_Request) -> Welcome_Response:
    """欢迎参观者、播报学院介绍 (≤80 字)。

    用户喊"介绍一下学院" / "欢迎大家" / "做个迎宾" 等时 LLM 应优先调本
    工具,而不是自己拼接介绍文字 + 调 speech.speak。本工具内置了官方介绍
    的事实地基,会自动让 VLM 改写成现场化欢迎并自报家门(运行 Robonix OS)。

    输入:
      audience_hint: 可选,描述当前场景 (例如 "评审组三人")。

    返回:
      success:      True = 播放成功
      spoken_text:  实际念出来的那段中文,便于 chat 显示
      error:        非空 = 失败原因
    """
    if _speech_endpoint is None:
        return Welcome_Response(
            success=False, spoken_text="",
            error="speech upstream not resolved (CMD_ACTIVATE failed?)",
        )
    text = _compose_welcome_text((req.audience_hint or "").strip())
    log.info("will speak (%d 字): %s", len(text), text)
    ok, detail = _play_speech(text)
    return Welcome_Response(
        success=ok, spoken_text=text,
        error="" if ok else f"speech.speak failed: {detail}",
    )


# ── Lifecycle ───────────────────────────────────────────────────────────────
@welcome_skill.on_init
def init(cfg):
    """CMD_INIT: light. 上游 (speech) 在 on_activate 才 resolve。"""
    log.info("CMD_INIT ok")
    return Ok()


@welcome_skill.on_activate
def activate():
    """CMD_ACTIVATE: heavy. Resolve speech endpoint + build VLM client."""
    global _speech_endpoint, _vlm_client, _vlm_model
    if _speech_endpoint:
        log.info("CMD_ACTIVATE — already active")
        return Ok()
    try:
        _speech_endpoint = _resolve_speech_endpoint()
    except RuntimeError as exc:
        return Err(str(exc))
    _vlm_client, _vlm_model = _build_vlm_client()
    log.info("CMD_ACTIVATE ok — vlm=%s",
             "configured" if _vlm_client else "FALLBACK mode (no env)")
    return Ok()


if __name__ == "__main__":
    welcome_skill.run()
