"""棋盘校准：用 GLM 识别出的 box 生成 4 角校准数据，写入 config.json。

用法：
    python -m xiangqi_agent.calibrate [截图.png] [--side red|black] [--manual]
  - 不给截图：自动截图（termux/adb 按 config）
  - --side：红方在屏幕下方填 red（默认），在上方填 black
  - --manual：手动输入 4 角像素坐标（更精确）
"""
from __future__ import annotations

import argparse
import json
import sys

from PIL import Image

from .config import load_config
from .engine import GridMapper
from .screen import Screen
from .vision import recognize


def auto_calibrate(img, cfg, side: str) -> dict:
    res = recognize(img, cfg)
    b = res["box"]
    board = {
        "tl": [b["left"], b["top"]],
        "tr": [b["right"], b["top"]],
        "bl": [b["left"], b["bottom"]],
        "br": [b["right"], b["bottom"]],
        "side": side,
    }
    return board


def manual_calibrate(img, side: str) -> dict:
    print("请查看截图，依次输入棋盘 4 个角点（整数像素坐标）：")
    print("  左上 tl, 右上 tr, 左下 bl, 右下 br（红方在下时，红方底线是下方）")
    if hasattr(img, "save"):
        img.save("debug/calibrate_input.png")
        print("截图已保存到 debug/calibrate_input.png，可打开查看")
    pts = {}
    for name in ("tl", "tr", "bl", "br"):
        while True:
            raw = input(f"{name} (x y): ").strip()
            parts = raw.split()
            if len(parts) == 2:
                try:
                    pts[name] = [int(parts[0]), int(parts[1])]
                    break
                except ValueError:
                    pass
            print("格式不对，输入两个整数，如: 100 320")
    pts["side"] = side
    return pts


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="棋盘校准")
    ap.add_argument("screenshot", nargs="?", help="截图路径（缺省则实时截图）")
    ap.add_argument("--side", default="red", choices=["red", "black"],
                    help="红方在屏幕下方=red（默认）；红方在上方=black")
    ap.add_argument("--manual", action="store_true", help="手动输入 4 角坐标")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.screenshot:
        img = Image.open(args.screenshot).convert("RGB")
    else:
        screen = Screen(cfg.screen_backend, cfg.adb.get("serial", ""))
        img = screen.take("debug/last_shot.png")
        print(f"[calibrate] 已截图: debug/last_shot.png ({img.size[0]}x{img.size[1]})")

    board = manual_calibrate(img, args.side) if args.manual else auto_calibrate(img, cfg, args.side)
    cfg.data["board"] = board
    cfg.save()
    # 校验：打印格心坐标抽查
    m = GridMapper(board)
    print(f"[calibrate] 已写入 config.json:\n  {json.dumps(board, ensure_ascii=False)}")
    print("抽查格心像素：帅(4,0) ->", m.cell_center(4, 0),
          " | 将(4,9) ->", m.cell_center(4, 9),
          " | 车(0,0) ->", m.cell_center(0, 0),
          " | 车(8,9) ->", m.cell_center(8, 9))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
