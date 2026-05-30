# robonix demo 交接文档 — 2026-05-20 (wheatfox → lhw)

> 接 HANDOFF.md。今天主要打通了**语音交互 + 语音播报**，并给 realsense/speech 加了 MCP。

---

## 一、demo 目标（周一汇报）

robonix 当「具身 OS」:**同一个任务，仿真和实机 ranger 跑同一套流程** ——「移动到盆栽 + 语音播报」。

- 说话下命令 → pilot(VLM) 规划 → executor 调度
- 看：scene 语义建图 + realsense rgb（MCP，代码完成、**待实机验证**）
- 定位：mapping（rtabmap SLAM 出 pose）。**约束：pose 只能来自 SLAM**。底盘 demo 时会开（导航用），今天没开只是还用不到。
- 说话/播报：liaison（对 mac 说）+ 车 USB 喇叭（speech `speak`）

---

## 二、现在能跑什么

| 能力 | 状态 | 备注 |
|---|---|---|
| scene 语义建图 | ✅ | native GPU,web viz `:50107` |
| realsense rgb 流 | ✅ | USB2 降配 15Hz |
| realsense rgb **MCP** | 🟡 | 代码完成，**未实机验证、未推** |
| 语音交互（liaison/mac） | ✅ | 文字+语音都通 |
| pilot VLM | ✅ | `gpt-5.5` via ofox.io |
| speech **speak/list_speakers MCP** | ✅ | 实测出声（mac+USB 都验过） |
| 车 USB 喇叭播报 | ✅ | audio_driver 起来了，`speak(target=audio_driver)` 出声 |
| mid360 雷达点流 | ⚠️ | rmem 已修，**待重测** |
| mapping SLAM pose | ⚠️ | 迁移完，差雷达点云喂入 |
| nav2 / sim 同任务 | ❓ | 待整合 |

---

## 三、今天做了什么（4 件）

### 1. VLM 网络：换 ofox.io 入口
`api.ofox.ai` 在大陆 DNS 被污染、CDN 不可达。改用大陆入口 `api.ofox.io`（同 key/服务），直连免代理。manifest 已改。

### 2. 修了语音 ASR 永远识别成「嗯」的 bug（最关键）
- **根因**:FunASR 流式要 600ms（9600 样本）固定帧，但 liaison 按 100ms 小帧送，speech 直接转手喂 → 流式状态崩。
- **修复**:`speech_service/service.py` 的 RecognizeStream 重新缓冲成 9600 样本帧再喂。
- 排查时加了两个工具（保留）:`INPUT_GAIN`（软件增益，现 1.0）、`ROBONIX_ASR_DUMP_DIR`（把收到的音频存 WAV，以后 ASR 出问题设上它就能抓）。

### 3. realsense 加 rgb MCP（pilot 的眼睛）
`@primitive_intel_realsense.provides_mcp("…/snapshot")` 返回 JPEG。顺手修了 realsense `build.sh`（缺 `--mcp`，之前不生成 MCP 类型）。**未实机验证、未推 enkerewpo。**

### 4. speech 加 speak / list_speakers MCP（让 agent 主动播报）
按手册做：新 IDL(`Speak.srv`/`ListSpeakers.srv`)+ 新 contract toml + `@speech.mcp(...)`。speech 变成 audio/speaker 的消费者（find → connect → 流式发 AudioChunk）。
- `list_speakers()` → 列出所有 speaker 原语
- `speak(target, text)` → TTS 后播到指定 speaker;`target` 空 = 第一个（注意会选到 mac）
- **实测**:`speak(target="audio_driver")` → 车 USB 喇叭出声 ✅。pilot 也已能在规划里调它。

---

## 四、今天碰过的文件 + push 状态

| 改动 | 状态 |
|---|---|
| **speech**：service.py / audio_utils.py / package_manifest.yaml / build.sh + 新 IDL(`Speak.srv`/`ListSpeakers.srv`) + 新 contract(`speak`/`list_speakers`.v1.toml) | ✅ **已 push `origin/dev`**（commit `71b6416`） |
| **realsense_camera_rbnx**：main.py(rgb/depth MCP) / build.sh(--mcp) | 🟡 **已在车 commit `07d1c37`，push 待你做**：`cd rbnx-boot/cache/realsense_camera && git push origin HEAD:main` |
| **scene native 脚本**：`system/scene/scripts/` 的 start.sh（改） / start_native.sh / setup_native.sh | ❌ **未提交**（只在车上 `~/wheatfox/robonix` clone）→ commit + push `origin/dev` |
| `robonix_manifest.voice.yaml`（ofox.io / gpt-5.5 / audio_driver / 音频 env） | deploy 仓本地 |

> ⚠️ realsense 在车 cache、scene 脚本在车 clone——**这俩都得你推，别丢**。speech 已经推好了。

## 五、你接着做（按优先级）

1. **雷达 → mapping → pose**（demo 主干）
   - rmem 已修（见坑 ①），重测雷达出点 → mapping 拿到数据 → scene 显示地图+pose。
   - 看 rviz2 前先 `unset CYCLONEDDS_URI`（否则 .bashrc 写死的 eno1 cyclonedds 配置会崩）。
   - 漂移调参：`Icp/VoxelSize`、`Icp/MaxCorrespondenceDistance`、`Odom/ScanKeyFrameThr`。fastlio2 暂不碰。

2. **整合 demo manifest**:scene + speech + 两个 audio + realsense + mapping 一把启；realsense rgb MCP 实机验证。

3. **底盘 + nav2**：接上能力接口，导航到盆栽。

4. **sim 侧**：跑同一任务流对齐实机。

**最终效果**：对车说「去盆栽那边」→ SLAM 定位导航过去 → 到达后车 USB 喇叭播报「已到达」→ 仿真同步演示同一套流程。

---

## 六、踩过的坑（省得重踩）

**① 雷达「连得上不出点 / 开一会停」** = 内核 UDP 缓冲太小（208KB）,MID-360 点太多溢出丢包。已修（持久化 `/etc/sysctl.d/10-livox.conf`）:`rmem_max=2GB`、`rmem_default=256MB`。理想还应把雷达挪到千兆板载网口（别走 USB2 dongle）。**rmem 修复后没重测，你验。**

**② 包加载报 `AtlasStub has no attribute DeclareCapability`** = 该包的 codegen atlas stub 和当前 robonix_api 对不上。今天 audio_driver 中招：车上 clone 的 `rbnx codegen` 生成的是 `DeclareInterface/RegisterCapability`，但 robonix_api + atlas server 用的是 `DeclareCapability/RegisterPrimitive`。**临时**把能跑的 audio_macos_bridge 的 atlas stub 拷过去绕过了。**根因是 clone 的 proto 和 python 不同步，得正经对齐**（否则任何新 codegen 的包都会中招）。

**③ USB 喇叭采样率** = 这个卡只吃 48000Hz/立体声；speech TTS 出 16kHz。靠 `plughw:2,0` + manifest 里 `AUDIO_SPEAKER_SAMPLE_RATE=16000` 让 aplay 转换。USB 卡的 `PCM Playback Volume` 默认低，要 `amixer -c <card> sset PCM 80%~100%`。

**④ realsense ABI** = `realsense2-camera` 和 `-msgs` 版本要一致（都 4.57.7），否则崩 `undefined symbol HardwareMonitorCommandSend`。USB2 下相机降到 rgb 640x480@15 + depth 480x270@15。

---

## 七、小车 native 构建（不用 docker）——重要

**小车一律 native，不用 docker**。原因：Jetson Orin 是 aarch64，系统里已有 NVIDIA 编的 CUDA torch 2.10 + ROS2 humble；docker 镜像是 x86/cu128 那套，Jetson 上用不了。所以每个重 Python 的包用 **overlay venv**（`python3 -m venv --system-site-packages` 继承系统 torch/ROS），**绝不 pip 重装 torch**（一装就把系统的 NVIDIA aarch64 torch 覆盖坏）。

**native/docker 切换 = 全靠 manifest 的 env 变量配**（不是改代码）。scene/mapping 的 `start.sh` 读这些 env 决定走 `start_native.sh` 还是 docker：

```yaml
env:
  ROBONIX_SCENE_FORCE: native          # scene 强制 native（或 ROBONIX_SCENE_PLATFORM 命中白名单 jetson_orin）
  SCENE_NATIVE_PYTHON: /home/syswonder/wheatfox/robonix/system/scene/rbnx-build/venv/bin/python  # native 模式用哪个 python（指 overlay venv）
  ROBONIX_MAPPING_FORCE: native        # mapping 强制 native
  HF_ENDPOINT: https://hf-mirror.com
  HF_HUB_OFFLINE: "1"
```

机制：`ROBONIX_<PKG>_FORCE=native|docker` 硬选模式，缺省时按 `ROBONIX_<PKG>_PLATFORM` 对白名单 `NATIVE_PLATFORMS=(jetson_orin)`；native → `exec start_native.sh`。scene 额外用 `SCENE_NATIVE_PYTHON` 指定 venv python。

> ⚠️ **scene 的 native 脚本还没进仓**：车上 `system/scene/scripts/` 有未提交的 `start.sh`（改） + `start_native.sh` + `setup_native.sh`（仓里 scene start.sh 仍是 docker-only）。**这套 native 分发只在车上，记得提交+推 dev，别丢。**

各包 native 搭法：
- **scene**：overlay venv `system/scene/rbnx-build/venv`，继承系统 torch 2.10(CUDA)，只补 open_clip/faiss/supervision/concept-graphs，constraints 钉死 torch/torchvision/numpy。CLIP 权重 `HF_ENDPOINT=hf-mirror.com` 预热（manifest 里 `HF_HUB_OFFLINE=1`）。
- **speech**：overlay venv `system/speech/rbnx-build/venv`，FunASR 1.3 + edge-tts + `robonix-api -e`，系统 torch CUDA（FunASR 走 GPU）。建了 `.rbnx-built` 标记**让 boot 跳过 uv-sync 重建**（否则会把 overlay 的系统 torch 冲掉）。
- **mapping**：native rtabmap（`apt install ros-humble-rtabmap`），不进 docker；`start_native.sh` + `ROBONIX_MAPPING_FORCE=native`。
- **realsense / mid360 / audio_driver**：原生 ROS2 / ALSA 节点，系统 python3 + `rbnx path robonix-api`，codegen 进 `rbnx-build/codegen`（robonix_api 自动加 sys.path）。

> 共性：**继承系统 torch/ROS，别动 torch；codegen 出 rbnx-build/codegen；HF 走 hf-mirror。**

## 七b、native/docker 分发的设计债（v0.2 讨论，代码先不动）

现状（env 变量配）有点丑，讨论过更干净的形态，记下结论：

**关键认知**：native/docker + 用哪个 python，是 **launch 期（build/start / rbnx spawn）** 的事，**不是 `Driver(CMD_INIT)` 的 config_json**——init 时 python 进程早起来了、解释器都选完了，config 拿到也晚了。所以这俩**不能走包的 init config 字段**。
- 分层：**build 期**造 overlay venv（`<pkg>/rbnx-build/venv`）；**start 期**选模式 + exec 哪个解释器。`SCENE_NATIVE_PYTHON` 显式写路径最丑，本可走约定 `<pkg>/rbnx-build/venv/bin/python`。

**v0.2 方案：单 manifest + build/start 按 profile 分键**（不是整两份 manifest——那样 caps/contract 会抄两遍、drift、把包身份和启动方式混了）：
```yaml
package: {...}
capabilities: [...]          # 同一套，不重复
profiles:
  native: { build: bash scripts/build_native.sh, start: bash scripts/start_native.sh }
  docker: { build: bash scripts/build_docker.sh,  start: bash scripts/start_docker.sh }
default_profile: native      # 或平台自动探测 jetson_orin
```
boot 时选：`rbnx boot --profile native` 或顶层 manifest per-package `runtime: {profile: docker}` override；rbnx 在 build/start 路由到该 profile 的脚本，**干掉 start.sh 里的 env if/else 分支**。`native_python` 走约定、常态不用写。

> 这是 rbnx boot 的 manifest schema 改动，v0.2 正式定 schema 再动。今天保持 env 变量配法。

## 八、manifest 一览 + 怎么启动
- `scene_min`：scene + realsense
- `scene_map`：scene + mid360_lidar + mid360_imu + realsense + mapping
- `voice`：atlas + executor + pilot + liaison + speech + audio_macos_bridge + audio_driver（语音交互+播报）

**启动都要带 env**（native 开关见 §七；voice 还要 VLM 凭据）：
```bash
# 感知+SLAM(scene_map)：native 开关
ROBONIX_SCENE_FORCE=native ROBONIX_MAPPING_FORCE=native \
SCENE_NATIVE_PYTHON=$HOME/wheatfox/robonix/system/scene/rbnx-build/venv/bin/python \
HF_ENDPOINT=https://hf-mirror.com HF_HUB_OFFLINE=1 \
rbnx boot -f robonix_manifest.scene_map.yaml

# 语音(voice)：带 VLM 凭据(凭据问 wheatfox)
env VLM_BASE_URL=https://api.ofox.io/v1 VLM_API_KEY=… VLM_MODEL=gpt-5.5 \
rbnx boot -f robonix_manifest.voice.yaml
# 然后 chat 把对话钉在 mac、播报走 USB：
ROBONIX_CHAT_MIC_NODE=audio_macos_bridge ROBONIX_CHAT_SPEAKER_NODE=audio_macos_bridge rbnx chat
```
> 这些 env 其实都已经写进对应 manifest 的 `env:` 块；上面 inline 是保险写法（rbnx 的 `${VLM_*}` 插值取 shell 环境）。

## 九、验证速查（确认每个能力真的好了）

```bash
rbnx caps -v                       # 看哪些 provider ACTIVE、各自 capability
# ASR/语音:rbnx chat → Ctrl+V 说话 → 看 transcript 是否正确(不是"嗯")
# speak(USB 播报):MCP 调 speak(target="audio_driver", text="测试") → 听 USB 出声
#   端点:atlas.log 里 grep "speech/speak via Mcp -> http://..."
# realsense rgb MCP:MCP 调 snapshot → 应返回 JPEG(encoding=jpeg)
# mid360 点云:unset CYCLONEDDS_URI; ros2 topic hz /livox/lidar  → 应稳定出帧
# mapping pose:ros2 topic echo <mapping pose topic>(或 rviz2,先 unset CYCLONEDDS_URI)
# scene 语义图:浏览器开 http://100.87.172.93:50107
```

## 十、demo 当天降级方案

- **雷达/mapping 没调通** → 退而求其次：只演**语音交互 + USB 播报 + scene 感知**（这条今天已通）,pose/导航部分用仿真演。
- **VLM(ofox)抽风/慢** → 备 deepseek 等中转；或先用文字交互（不依赖 ASR）。
- **USB 喇叭卡死** → 重启栈 + `pkill -9 aplay arecord`；或播报临时切回 mac(`speak(target="audio_macos_bridge")`)。

## 卡住找谁
- robonix-api / 迁移 / 语音 / speech MCP / VLM:wheatfox
- 雷达硬件 / USB / CAN：硬件同学
