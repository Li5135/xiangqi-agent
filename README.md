# 象棋 Agent（JJ象棋 · GLM 视觉 + DeepSeek 决策 + 无障碍点击）

一个跑在 **Termux（Android 手机）** 上的中国象棋自动下棋 agent：

1. **GLM-4.6V（智谱）** 看截图，把 JJ象棋 棋盘识别成 FEN + 屏幕坐标
2. **DeepSeek** 根据局面思考并给出走法（UCCI 坐标，如 `h2e2`）
3. 程序把走法换算成屏幕像素，通过 **无障碍服务 APK（ClickServer）** 点选落子
4. 循环等待对手走棋，继续下一回合

手机无需 root：截图走 Termux:API（`termux-screenshot`），点击走无障碍服务。

> 纯 LLM 决策棋力有限（可正常对弈，但下不过强引擎）。如果你以后想下得更强，
> 把 `src/xiangqi_agent/brain.py` 换成 Pikafish 引擎调用即可，其余模块不用动。

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│  Android 手机（Termux）                                      │
│                                                             │
│  ┌─────────┐ 截图  ┌────────────┐  JSON  ┌────────────────┐ │
│  │ JJ象棋   │──────►│ GLM-4.6V    │────────►│ DeepSeek       │ │
│  │ 屏幕     │◄──────│ 视觉识别FEN  │        │ 决策走法        │ │
│  └─────────┘ 点击   └────────────┘        └───────┬────────┘ │
│       ▲                                           │ UCCI     │
│       │ dispatchGesture        ┌──────────────────▼────────┐ │
│  ┌────┴──────────┐   HTTP POST │  engine.py                │ │
│  │ ClickServer    │◄────────────│  走法校验 + 坐标换算       │ │
│  │ 无障碍服务 APK │  /tap /swipe│                          │ │
│  └───────────────┘             └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 目录结构

```
xiangqi-agent/
├── src/xiangqi_agent/
│   ├── config.py          # 配置加载（config.json）
│   ├── screen.py          # 截图后端：termux / adb（可插拔）
│   ├── input_backend.py   # 点击后端：clickserver / adb（可插拔）
│   ├── vision.py          # GLM 视觉：截图 → FEN + 棋盘九宫格
│   ├── brain.py           # DeepSeek：FEN → 走法
│   ├── engine.py          # 走法解析、合法性校验、像素换算
│   ├── calibrate.py       # 棋盘校准（一次性，存 config）
│   └── main.py            # 主循环 CLI
├── clickserver/           # 无障碍服务 APK（Gradle 工程，云端构建）
├── .github/workflows/build-apk.yml
├── config.example.json
└── requirements.txt
```

## 电脑端调试（可选，推荐先跑通再上手机）

不需要手机也能验证视觉/决策两个核心模块：

```bash
pip install -r requirements.txt
cd xiangqi-agent
export PYTHONPATH=src        # Windows: set PYTHONPATH=src

# 1) 校准：用一张 JJ象棋 棋盘截图生成九宫格
python -m xiangqi_agent.calibrate assets/screenshot.png
# 2) 单步：识别局面 + 生成走法
python -m xiangqi_agent.vision assets/screenshot.png
python -m xiangqi_agent.brain assets/screenshot.png
```

有手机连 USB 时，`screen_backend=adb`、`input_backend=adb` 即可在电脑上整机跑通。

## 手机端部署（Termux）

```bash
# 1. 安装 Termux + Termux:API（F-Droid），然后：
pkg install python termux-api -y
pip install requests pillow

# 2. 把项目拷到手机（git clone 或 termux-setup-storage 后复制）
cd xiangqi-agent
export PYTHONPATH=src

# 3. 安装 ClickServer.apk（GitHub Actions 构建产物，见下）
#    设置 → 无障碍 → 开启 ClickServer

# 4. 填 key 与配置
cp config.example.json config.json
nano config.json          # 填 GLM/DeepSeek key、side=红/黑

# 5. 校准（屏幕上先摆好 JJ象棋 开局，运行后按提示点 4 个角）
python -m xiangqi_agent.calibrate

# 6. 开一局 JJ象棋，运行 agent
python -m xiangqi_agent.main
```

## 视觉模型选型（重要）

实测（合成棋盘图）：`glm-4.6v-flash`（免费）识别快但**漏认棋子**；
`glm-4.6v-flashx` 更准但慢（单次 1-2 分钟）。真实 JJ象棋 截图棋子大而清晰，
识别率会显著更高，但**务必先用真机截图实测**再选模型：

- 先用 `python -m xiangqi_agent.calibrate shot.png` 对一张真实截图跑通
- 准确率不够时，`config.json` 里换更强视觉模型，例如：
  - `glm-4v-plus`（智谱付费档，视觉更强）
  - `qwen-vl-max`（阿里通义，需相应 key）
- 免费 flash 版适合试跑，正式对局建议 flashx 或付费模型

## 构建 ClickServer APK

本地无需 Android SDK，推 GitHub 云端构建（已带 workflow，复用 mobile-app 经验）：

```bash
git init && git add -A && git commit -m "xiangqi agent"
git remote add origin git@github.com:<你>/xiangqi-agent.git
git push -u origin main
# Actions → build-apk → 下载 artifacts/clickserver.apk
```

APK 安装后：
1. 设置 → 无障碍 → ClickServer → 开启（授予"执行手势"能力）
2. Agent 通过 `http://127.0.0.1:8123/tap` 调用它点击屏幕

## 常见问题

- **截图黑屏**：确认已装 Termux:API 且执行过 `termux-setup-storage`；个别 ROM 需在通知栏允许"屏幕截图"权限
- **点击无效**：无障碍里 ClickServer 开关是否打开；JJ象棋 是否需要先点棋盘进入对局
- **GLM 识别不准**：`vision.py` 里 `--debug` 保存识别图，调整提示词；或用 `calibrate.py` 校准过棋盘后识别更稳
- **DeepSeek 走法非法**：engine.py 会自动校验并让 DeepSeek 重试（最多 3 次），仍失败则跳过本回合等下一次
