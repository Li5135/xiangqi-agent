"""走法解析、合法性校验、像素换算（纯函数，无 IO）。

坐标约定
--------
- 逻辑坐标: (file, rank)，file 0-8（a-i，红方视角从左到右），rank 0-9（0=红方底线）
- 走法格式 (UCCI): "h2e2" = 源 file行 → 目标 file行
- FEN: 标准 Xiangqi FEN（黑方视角列顺序固定，段落从上到下=rank 9..0）
"""
from __future__ import annotations

import re
from dataclasses import dataclass

FILES = "abcdefghi"          # file 索引 → 字母
FILES_INDEX = {c: i for i, c in enumerate(FILES)}

# 标准 Xiangqi FEN 符号：红 N马 B象（国际象棋习惯，但为中国象棋规则）
RED = "RNBAKCP"              # 车马象仕帅炮兵
BLACK = "rnbakcp"            # 车马象士将炮卒
EMPTY = "."


class MoveError(ValueError):
    """走法非法（含解析失败）。message 给 DeepSeek 重试时看。"""


@dataclass
class Board:
    grid: list[list[str]]    # grid[rank][file]
    side: str                # 'red' | 'black'，当前轮到谁走

    @classmethod
    def from_fen(cls, fen: str, side: str = "red") -> "Board":
        parts = fen.strip().split()
        ranks = parts[0].split("/")
        if len(ranks) != 10:
            raise ValueError(f"FEN 段数错误: {len(ranks)}")
        grid = []
        for seg in ranks:
            row = []
            for ch in seg:
                if ch.isdigit():
                    row += [EMPTY] * int(ch)
                else:
                    row.append(ch)
            if len(row) != 9:
                raise ValueError(f"FEN 行宽错误: {len(row)}")
            grid.append(row)
        # FEN 第 0 段是黑方底线(rank9)…第 9 段是红方底线(rank0)
        grid.reverse()       # 现在 grid[rank]，rank0=红方底线
        if len(parts) > 1 and parts[1] in ("w", "b"):
            side = "red" if parts[1] == "w" else "black"
        return cls(grid=grid, side=side)

    def fen(self) -> str:
        rows = []
        for r in range(9, -1, -1):
            seg = ""
            n = 0
            for f in range(9):
                ch = self.grid[r][f]
                if ch == EMPTY:
                    n += 1
                else:
                    if n:
                        seg += str(n)
                        n = 0
                    seg += ch
            if n:
                seg += str(n)
            rows.append(seg)
        return "/".join(rows) + f" {'w' if self.side == 'red' else 'b'} - - 0 1"

    def piece(self, f: int, r: int) -> str:
        return self.grid[r][f]

    def in_board(self, f: int, r: int) -> bool:
        return 0 <= f < 9 and 0 <= r < 10

    def copy(self) -> "Board":
        return Board([row[:] for row in self.grid], self.side)


# ---------- 基本走法规则 ----------

def _line_clear(board: Board, f0, r0, f1, r1) -> bool:
    """两点间路径是否无子（不含端点）。仅限同行/同列。"""
    if f0 == f1:
        lo, hi = sorted((r0, r1))
        for r in range(lo + 1, hi):
            if board.piece(f0, r) != EMPTY:
                return False
    elif r0 == r1:
        lo, hi = sorted((f0, f1))
        for f in range(lo + 1, hi):
            if board.piece(f, r0) != EMPTY:
                return False
    else:
        return False
    return True


def _pseudo_legal(board: Board, f0, r0, f1, r1) -> str | None:
    """返回 None=合法，否则返回非法原因。只判断单子走法，不含送将。"""
    p = board.piece(f0, r0)
    if p == EMPTY:
        return "源格无棋子"
    mine = RED if p in RED else BLACK
    tgt = board.piece(f1, r1)
    if tgt != EMPTY and (tgt in RED) == (p in RED):
        return "目标格是己方棋子"
    dx, dy = f1 - f0, r1 - r0
    adx, ady = abs(dx), abs(dy)
    up = p in RED          # 红方棋子向上（rank 减小）
    low = p.lower()

    if low == "r":         # 车
        if not (adx == 0 or ady == 0) or not _line_clear(board, f0, r0, f1, r1):
            return "车只能走直线且路径不能有子"
    elif low == "n":       # 马
        if not ((adx, ady) in ((1, 2), (2, 1))):
            return "马必须走日字"
        leg = (f0 + (1 if dx > 0 else -1), r0) if adx == 2 else (f0, r0 + (1 if dy > 0 else -1))
        if board.piece(*leg) != EMPTY:
            return "马被蹩马腿"
    elif low == "b":       # 象/相
        if not (adx == 2 and ady == 2):
            return "象必须走田字"
        mid = (f0 + dx // 2, r0 + dy // 2)
        if board.piece(*mid) != EMPTY:
            return "象眼被塞"
        if up and r1 > 4 or (not up) and r1 < 5:
            return "象不能过河"
    elif low == "a":       # 士/仕
        if not (adx == 1 and ady == 1):
            return "士只能斜走一步"
        if not _in_palace(f1, r1, up):
            return "士不能出九宫"
    elif low == "k":       # 将/帅
        if not (adx + ady == 1):
            return "将只能直走一步"
        if not _in_palace(f1, r1, up):
            return "将不能出九宫"
    elif low == "c":       # 炮
        if adx == 0 or ady == 0:
            blockers = sum(
                1
                for r in range(min(r0, r1) + 1, max(r0, r1)) if board.piece(f0, r) != EMPTY
            ) if adx == 0 else sum(
                1
                for f in range(min(f0, f1) + 1, max(f0, f1)) if board.piece(f, r0) != EMPTY
            )
            if tgt == EMPTY and blockers != 0:
                return "炮移动时路径不能有子"
            if tgt != EMPTY and blockers != 1:
                return "炮吃子必须隔一子"
        else:
            return "炮只能走直线"
    elif low == "p":       # 兵/卒
        fwd = -1 if up else 1
        crossed = (r0 >= 5) if up else (r0 <= 4)
        if dy == fwd and dx == 0:
            pass
        elif dy == 0 and adx == 1 and crossed:
            pass
        else:
            return "兵只能向前，过河后才能横走"
    else:
        return f"未知棋子 {p}"
    return None


def _in_palace(f: int, r: int, red: bool) -> bool:
    if red:
        return 3 <= f <= 5 and 0 <= r <= 2
    return 3 <= f <= 5 and 7 <= r <= 9


def _find_king(board: Board, red: bool) -> tuple[int, int] | None:
    k = "K" if red else "k"
    for r in range(10):
        for f in range(9):
            if board.piece(f, r) == k:
                return f, r
    return None


def _attacked(board: Board, f, r, by_red: bool) -> bool:
    """位置 (f,r) 是否被 by_red 一方攻击（一步能吃）。不检查送将，避免递归。"""
    for r0 in range(10):
        for f0 in range(9):
            p = board.piece(f0, r0)
            if p == EMPTY or (p in RED) != by_red:
                continue
            if _pseudo_legal(board, f0, r0, f, r) is None:
                return True
    return False


def _face_to_face(board: Board) -> bool:
    """将帅是否同列且中间无子（非法局面）。"""
    rk = _find_king(board, True)
    bk = _find_king(board, False)
    if not rk or not bk:
        return False
    if rk[0] != bk[0]:
        return False
    return all(board.piece(rk[0], r) == EMPTY for r in range(min(rk[1], bk[1]) + 1, max(rk[1], bk[1])))


# ---------- 对外 API ----------

def parse_move(move: str) -> tuple[int, int, int, int]:
    """'h2e2' → (f0, r0, f1, r1)。支持 'h2-e2'、'H2E2'、'h2e2'。"""
    m = re.fullmatch(r"([a-iA-I])([0-9])\s*[-–]?\s*([a-iA-I])([0-9])", move.strip())
    if not m:
        raise MoveError(f"走法格式不对（应为 h2e2 形式）: {move!r}")
    f0, r0, f1, r1 = m.groups()
    return FILES_INDEX[f0.lower()], int(r0), FILES_INDEX[f1.lower()], int(r1)


def format_move(f0, r0, f1, r1) -> str:
    return f"{FILES[f0]}{r0}{FILES[f1]}{r1}"


def legal_moves(board: Board, f0, r0) -> list[tuple[int, int, int, int]]:
    """返回 (f0,r0) 上棋子的所有合法走法（含送将检查）。"""
    if not board.in_board(f0, r0) or board.piece(f0, r0) == EMPTY:
        return []
    out = []
    for f1 in range(9):
        for r1 in range(10):
            if f1 == f0 and r1 == r0:
                continue
            if validate_move(board, f0, r0, f1, r1) is None:
                out.append((f0, r0, f1, r1))
    return out


def validate_move(board: Board, f0, r0, f1, r1) -> str | None:
    """完整校验：单子规则 + 送将 + 将帅对脸。合法返回 None，否则返回原因。"""
    if not board.in_board(f0, r0) or not board.in_board(f1, r1):
        return "越界"
    p = board.piece(f0, r0)
    if p == EMPTY:
        return "源格无棋子"
    if (p in RED) != (board.side == "red"):
        return "不是当前行动方的棋子"
    err = _pseudo_legal(board, f0, r0, f1, r1)
    if err:
        return err
    # 模拟走子，检查送将
    b2 = board.copy()
    b2.grid[r1][f1] = p
    b2.grid[r0][f0] = EMPTY
    king = _find_king(b2, board.side == "red")
    if king and _attacked(b2, *king, by_red=board.side != "red"):
        return "走完后己方将帅会被将军"
    if _face_to_face(b2):
        return "将帅不能直接照面"
    return None


def apply_move(board: Board, f0, r0, f1, r1) -> Board:
    """执行走法，返回新局面（调用前应先 validate_move）。"""
    b2 = board.copy()
    b2.grid[r1][f1] = b2.grid[r0][f0]
    b2.grid[r0][f0] = EMPTY
    b2.side = "black" if b2.side == "red" else "red"
    return b2


# ---------- 像素换算 ----------

def board_from_config(board_cfg: dict) -> "GridMapper":
    return GridMapper(board_cfg)


class GridMapper:
    """4 角校准数据 → 逻辑坐标 ↔ 屏幕像素。"""

    def __init__(self, cfg: dict):
        # cfg: {"tl":[x,y],"tr":[...],"bl":[...],"br":[...],"side":"red"}
        self.tl = tuple(cfg["tl"])
        self.tr = tuple(cfg["tr"])
        self.bl = tuple(cfg["bl"])
        self.br = tuple(cfg["br"])
        self.side = cfg.get("side", "red")

    def _point(self, u: float, v: float) -> tuple[float, float]:
        """u:0左→1右, v:0上→1下，双线性插值。"""
        def lerp(a, b, t):
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        top = lerp(self.tl, self.tr, u)
        bot = lerp(self.bl, self.br, u)
        return lerp(top, bot, v)

    def cell_center(self, f: int, r: int) -> tuple[int, int]:
        """逻辑 (file,rank) → 格心像素。rank0 是红方底线。"""
        if self.side == "red":
            u = (f + 0.5) / 9
            v = (9 - r - 0.5) / 9      # rank0(红底) 在屏幕下方
        else:                          # 黑方在下，红方在上：屏幕左右/上下都翻转
            u = (8 - f + 0.5) / 9
            v = (r + 0.5) / 9
        x, y = self._point(u, v)
        return int(round(x)), int(round(y))

    def tap_source_target(self, f0, r0, f1, r1, delay_ms: int = 350):
        return self.cell_center(f0, r0), self.cell_center(f1, r1)
