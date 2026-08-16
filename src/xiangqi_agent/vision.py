"""GLM 视觉识别：整屏截图 → 棋盘矩阵 + 棋盘位置框（程序转 FEN）。

模型输出（JSON）：
    {"grid": ["r n b a k a b n r", ..., "R N B A K A B N R"],
     "box":  {"left":0,"top":0,"right":0,"bottom":0}}
grid 共 10 行，每行 9 个棋子符号（空格分隔），第 1 行=黑方底线(屏幕最上方)。
程序把矩阵转成标准 Xiangqi FEN。
"""
from __future__ import annotations

import json
import re

from PIL import Image

from .engine import Board
from .llm import LLMError, chat_vision

PROMPT = """你是中国象棋棋盘识别器。请看这张 JJ象棋 游戏截图，完成两件事：

1. 逐格识别棋盘上所有棋子，输出 10 行 × 9 列的矩阵。
   棋子符号（不要用汉字，只用字母）：
     红方：车=R 马=N 相=B 仕=A 帅=K 炮=C 兵=P
     黑方：车=r 马=n 象=b 士=a 将=k 炮=c 卒=p
     空格：.
   第 1 行是【黑方底线】（屏幕最上面一行），第 10 行是【红方底线】（屏幕最下面一行）。
   每一行恰好 9 个符号，从左到右，符号之间用一个空格分隔。
   例如开局黑方底线那行是：r n b a k a b n r

2. 识别棋盘 9×10 网格最外边框在截图中的像素位置。
   输出 box: {"left": x, "top": y, "right": x, "bottom": y}，
   left 是棋盘最左，top 是最上（黑方一侧），bottom 是最下（红方一侧）。

只输出一个 JSON 对象，不要输出任何其它文字，形如：
{"grid": ["r n b a k a b n r", "9 个符号的 10 行"], "box": {"left":0,"top":0,"right":0,"bottom":0}}
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if m:
        text = m.group(1)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"响应中没有 JSON: {text[:200]}")
    return json.loads(m.group(0))


def _grid_to_fen(grid: list[str]) -> str:
    if len(grid) != 10:
        raise ValueError(f"grid 应有 10 行，实际 {len(grid)}")
    ranks = []
    for row in grid:
        cells = re.sub(r"\s+", "", str(row))
        if len(cells) != 9:
            raise ValueError(f"行宽错误（应为 9）：{cells!r}")
        seg = ""
        n = 0
        for ch in cells:
            if ch == ".":
                n += 1
            else:
                if n:
                    seg += str(n)
                    n = 0
                seg += ch
        if n:
            seg += str(n)
        ranks.append(seg)
    # grid 第 0 行是黑方底线(rank9)…第 9 行是红方底线(rank0)，FEN 段落顺序正好一致
    return "/".join(ranks)


def _validate_fen(fen: str) -> str | None:
    """FEN 合理性校验。返回错误信息或 None。"""
    try:
        b = Board.from_fen(fen)
    except Exception as e:
        return f"FEN 无法解析: {e}"
    kings = sum(row.count("K") for row in b.grid)
    gen = sum(row.count("k") for row in b.grid)
    if kings != 1 or gen != 1:
        return f"将/帅数量不对（红{kings} 黑{gen}），应各 1 个"
    red_n = sum(1 for row in b.grid for c in row if c in "RNBAKCP")
    black_n = sum(1 for row in b.grid for c in row if c in "rnbakcp")
    if red_n > 16 or black_n > 16:
        return f"棋子数异常（红{red_n} 黑{black_n}）"
    return None


def _maybe_upscale(img: Image.Image, min_side: int = 1080) -> Image.Image:
    """短边小于阈值时放大（视觉模型对小文字识别差）。"""
    w, h = img.size
    if min(w, h) >= min_side:
        return img
    scale = min_side / min(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def recognize(img, cfg, retries: int = 2, save_debug: str | None = None) -> dict:
    """识别局面。返回 {"fen": str, "box": {...}, "raw": str}。"""
    if isinstance(img, (str, bytes)):
        img = Image.open(img).convert("RGB")
    img = _maybe_upscale(img)
    last_err = ""
    for attempt in range(retries):
        text = chat_vision(
            cfg.glm["base_url"], cfg.glm["api_key"], cfg.glm["model"],
            img, PROMPT, timeout=cfg.glm.get("timeout", 90),
        )
        if save_debug:
            with open(save_debug, "w", encoding="utf-8") as f:
                f.write(text)
        try:
            d = _extract_json(text)
            fen = _grid_to_fen(d["grid"])
            box = d["box"]
        except Exception as e:
            last_err = f"解析失败: {e}"
            continue
        err = _validate_fen(fen)
        if err:
            last_err = err
            continue
        return {"fen": fen, "box": box, "raw": text}
    raise LLMError(f"GLM 识别失败（{retries} 次尝试后）：{last_err}")
