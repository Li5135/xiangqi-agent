# 架构设计

## 坐标系统（全项目统一）

### 棋盘逻辑坐标（Xiangqi FEN 标准）

- 9 列（file）：`a`–`i`，**从左到右是红方视角**（红方坐在下方时，a 在最左）
- 10 行（rank）：`0`–`9`（或 FEN 的 `1`–`10`），**0/1 是红方底线**
- 棋子：红方大写 `R H E A C P K`（车马象仕炮兵帅），黑方小写 `r h e a c p k`（车马象士炮卒将）
- 走法格式（UCCI）：`h2e2` = 源 `(file=h, rank=2)` → 目标 `(file=e, rank=2)`

### 屏幕像素坐标

- 像素 `(x, y)`，左上角原点
- 九宫格校准数据存 4 个角点 `board.tl/tr/bl/br`（top-left/top-right/bottom-left/bottom-right）
- 换算：逻辑 `(file, rank)` → 像素，先线性插值行/列网格，再取格中心

```
file a(左) ──────── i(右)      rank 0(红底线,下方)
  │  (col=file, row=rank)        │
  │   像素 = 双线性插值           │ rank 9(黑底线,上方)
```

> 注意：JJ象棋 棋盘中「红方在下、黑方在上」时，rank 0 在屏幕**下方**。
> 校准阶段用屏幕坐标标 4 角，引擎内部统一转逻辑坐标，谁红谁黑由 `side` 决定。

## 数据流

```
主循环（main.py）
  1. screen.take_screenshot()                  # Termux:API / adb
  2. vision.recognize(img) → {fen, board_box}  # GLM-4.6V
  3. 与上次 fen 对比 → 对手已走棋？             # 变化则继续
  4. brain.choose_move(fen, side, history)     # DeepSeek → "h2e2"
  5. engine.validate(fen, move)                # 合法性校验，非法重试
  6. engine.move_to_pixels(board, move)        # 源/目标格像素
  7. input_backend.tap(src) → 延时 → tap(dst)  # ClickServer / adb
  8. 等待 poll_interval 秒，回 1
```

## 模块职责

| 模块 | 职责 | 可插拔点 |
|---|---|---|
| `screen.py` | 截图，返回 PIL Image | `termux`（手机）/ `adb`（电脑调试） |
| `input_backend.py` | `tap(x,y)` `swipe(...)` | `clickserver`（HTTP→无障碍）/ `adb` |
| `vision.py` | 截图 → FEN + 棋盘边框 | 模型换 GLM-4.6V ↔ 其它 OpenAI 兼容视觉模型 |
| `brain.py` | FEN+side+history → UCCI 走法 | 换 Pikafish 引擎即可变强引擎 |
| `engine.py` | 走法解析/校验/像素换算 | 纯函数，无 IO |
| `calibrate.py` | 4 角标定 → config.board | 一次性的 CLI 流程 |

## 无障碍 APK（clickserver）

- 一个 AccessibilityService，开启后注册 `dispatchGesture` 能力
- 内嵌 HTTP 服务监听 `127.0.0.1:8123`
  - `POST /tap` `{"x":..,"y":..}` → 单击
  - `POST /swipe` `{"from":[x,y],"to":[x,y],"duration":ms}` → 滑动
  - `GET /health` → 200（Termux 侧用它探测服务是否就绪）
- 为什么用 HTTP：Termux 的 Python 进程无法直接调 Android 无障碍 API，
  这是无 root 前提下最薄的一层桥。

## 视觉识别提示词要点（vision.py）

- 输入：整屏截图（JJ象棋）
- 输出：严格 JSON：`{"fen": "...", "box": {"left":..,"top":..,"right":..,"bottom":..}}`
- 规则：红方大写、黑方小写；列 a–i 以红方视角从左到右；空位 `1`~`9` 数字合并
- 程序侧再校验：将/帅各恰 1、棋子总数合法；不合法则带错误信息重试一次
