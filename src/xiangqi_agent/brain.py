"""DeepSeek 决策：FEN 局面 → UCCI 走法。带 engine 校验 + 重试。"""
from __future__ import annotations

import json
import re

from .engine import Board, MoveError, apply_move, format_move, parse_move, validate_move
from .llm import LLMError, chat

PIECE_TABLE = """棋子对照：R车 N马 B相 A仕 K帅 C炮 P兵（红方，大写）
               r车 n马 b象 a士 k将 c炮 p卒（黑方，小写）"""


def build_prompt(board: Board, history: list[str], my_side: str) -> str:
    fen = board.fen()
    hist = "、".join(history) if history else "（无）"
    return f"""你是中国象棋高手。请根据当前局面选择一步最佳走法。

局面（Xiangqi FEN）：
{fen}

{PIECE_TABLE}

规则：
- FEN 中 'w' 表示红方走，'b' 表示黑方走。
- 你执【{"红方" if my_side == "red" else "黑方"}】，轮到你走。
- 我方已走的着法历史（UCCI 格式）：{hist}
- 请认真计算：考虑子力价值（车9 马4 炮4.5 象2 士2 兵1）、攻防、牵制、先手。

输出格式（只输出 JSON，不要解释）：
{{"move": "h2e2", "reason": "一句话说明为什么"}}
move 必须用 UCCI 格式：源列行+目标列行，列 a-i（红方视角左到右），行 0-9（0 是红方底线）。
例如 红炮从(列h,行2)平到(列e,行2) → "h2e2"。"""


def _extract_move(text: str) -> str:
    m = re.search(r"\"?move\"?\s*[:：]\s*\"([a-iA-I][0-9][a-iA-I][0-9])\"", text)
    if m:
        return m.group(1).lower()
    m = re.search(r"\b([a-iA-I][0-9]\s*[-–]?\s*[a-iA-I][0-9])\b", text)
    if m:
        return m.group(1).replace(" ", "").replace("-", "").lower()
    raise MoveError(f"DeepSeek 输出中没有合法走法: {text[:200]}")


def choose_move(board: Board, history: list[str], my_side: str, cfg,
               max_retries: int = 3, verbose: bool = True) -> dict:
    """返回 {"move": "h2e2", "reason": str, "attempts": int}。"""
    last_err = ""
    for attempt in range(max_retries):
        prompt = build_prompt(board, history, my_side)
        text = chat(
            cfg.deepseek["base_url"], cfg.deepseek["api_key"],
            cfg.deepseek["model"], [{"role": "user", "content": prompt}],
            timeout=cfg.deepseek.get("timeout", 60),
        )
        try:
            move_str = _extract_move(text)
            f0, r0, f1, r1 = parse_move(move_str)
            err = validate_move(board, f0, r0, f1, r1)
            if err:
                last_err = err
                if verbose:
                    print(f"[brain] 走法 {format_move(f0, r0, f1, r1)} 非法: {err}，重试")
                continue
            reason_m = re.search(r"\"?reason\"?\s*[:：]\s*\"([^\"]*)\"", text)
            return {
                "move": format_move(f0, r0, f1, r1),
                "reason": reason_m.group(1) if reason_m else "",
                "attempts": attempt + 1,
            }
        except (MoveError, ValueError) as e:
            last_err = str(e)
            if verbose:
                print(f"[brain] {last_err}，重试")
            continue
    raise LLMError(f"DeepSeek 连续 {max_retries} 次未给出合法走法：{last_err}")
