# welcome — PKU CS 学院迎宾 skill

LLM-facing 用法手册。`rbnx caps` 不读这个文件,**pilot 读** —
pilot 在每次组装 prompt 时会把这段塞进 LLM 的工具描述里。

---

## 何时调本工具

用户输入下列含义之一时,**优先**调 `robonix/skill/welcome/welcome`:

- "介绍一下学院 / 计算机学院 / 北大计院 / 我们这"
- "欢迎一下大家 / 来人了 / 客人到了 / 参观开始"
- "做个迎宾 / 当一下迎宾"
- 含义对等的口语化变体(任何场合明显是"对着访客致欢迎词")

**不要**自己拼介绍文字然后调 `speech.speak` — 本 skill 内置了官方介绍
的事实地基(`welcome_skill/intro_text.py`),自由发挥会出错信息。

## 不要调本工具的场合

- 用户问"你叫什么" / "你能做什么" → 用普通 chat 回答,不要触发实际播报
- 用户问"学院在哪" / "学院的招生 / 邮箱"等检索类问题 → 不在本 skill 范围
- 调试 / 测试 speech 路径 → 直接调 `robonix/system/speech/speak`

## 输入

```
audience_hint: string  # 可选。从对话上下文 inferred,例如:
                      #   "评审组三人"
                      #   "约二十名访客"
                      #   "" = 不提示 (LLM 看图自由发挥)
```

## 返回

```
success:     bool    # 全链路 (snapshot + VLM + speech) 都成功
spoken_text: string  # 实际念出来的那段中文,展示给用户看
error:       string  # 非空 = 失败原因
```

## 内部流程

1. 抓一帧 chassis 前置相机 (realsense_camera /
   `robonix/primitive/camera/snapshot`)
2. 用 VLM (与 pilot 同款 endpoint,通过 deploy manifest 的
   `VLM_BASE_URL / VLM_API_KEY / VLM_MODEL` env 注入) 看图 + 引用
   `intro_text.py` 的官方介绍,生成 ≤80 字现场化欢迎词
3. 调 `robonix/system/speech/speak` 合成并播放
4. 返回播报文本

VLM 不可用 → 退到固定 fallback 文本,skill 仍然 success=True 完成
播报。这是为了 demo 不会因 GFW / api key 失效而完全哑火。

## 失败模式

| 错误 | 含义 | 修复 |
|---|---|---|
| `upstream camera/speech not resolved` | on_activate 60s 内没找到 atlas 里的 camera/snapshot 或 speech/speak | 确认这两个 cap 是 ACTIVE 状态 (`rbnx caps`) |
| `speech.speak failed` | TTS 合成或 ALSA 播放失败 | 看 `service_speech.log` |
| (没明显报错,但听到的是 fallback 文本) | VLM 环境变量没设 / api 不通 | 看 skill 启动日志里 `VLM env not fully set` 警告;在 manifest env 里补 `VLM_*` |
