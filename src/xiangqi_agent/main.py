"""主循环：截图 → GLM 识别 → DeepSeek 走法 → 无障碍点击。

用法：
    python -m xiangqi_agent.main [--once] [--debug]
"""
from __future__ import annotations

import argparse
import sys
import time

from .brain import choose_move
from .config import load_config
from .engine import Board, GridMapper, apply_move
from .input_backend import make_input_backend, wait_until_ready
from .screen import Screen
from .vision import recognize

import os


class Agent:
    def __init__(self, cfg, debug: bool = False):
        self.cfg = cfg
        self.debug = debug
        self.my_side = cfg.side
        self.screen = Screen(cfg.screen_backend, cfg.adb.get("serial", ""))
        self.input = make_input_backend(
            cfg.input_backend,
            serial=cfg.adb.get("serial", ""),
            host=cfg.clickserver.get("host", "127.0.0.1"),
            port=cfg.clickserver.get("port", 8123),
        )
        if not cfg.board:
            raise SystemExit(
                "[main] config.json 缺少 board 校准数据，先运行: python -m xiangqi_agent.calibrate"
            )
        self.mapper = GridMapper(cfg.board)
        self.history: list[str] = []          # 我方走的着法
        self.last_fen: str | None = None
        self.my_turn = self.my_side == "red"  # 红先
        self._consecutive_errors = 0

    # ---------- 截图 + 识别 ----------

    def _snapshot(self) -> tuple[str, object]:
        """截图并识别，返回 (fen, img)。识别失败时抛 LLMError。"""
        img = self.screen.take()
        if self.debug:
            os.makedirs(self.cfg.debug_dir, exist_ok=True)
            img.save(os.path.join(self.cfg.debug_dir, "last_shot.png"))
        fen = recognize(img, self.cfg, save_debug=(
            os.path.join(self.cfg.debug_dir, "last_vision.txt") if self.debug else None
        ))["fen"]
        return fen, img

    def get_stable_fen(self, tries: int = 4) -> str:
        """连续两次识别相同才返回（抗 GLM 抖动/动画残影）。"""
        prev = None
        for i in range(tries):
            try:
                fen, _ = self._snapshot()
            except Exception as e:
                print(f"[main] 识别异常: {e}，{self.cfg.poll_interval}s 后重试")
                time.sleep(self.cfg.poll_interval)
                continue
            if prev is not None and fen == prev:
                return fen
            prev = fen
            time.sleep(self.cfg.poll_interval)
        return prev

    # ---------- 我方走棋 ----------

    def try_move(self) -> bool:
        fen = self.get_stable_fen()
        board = Board.from_fen(fen, side=self.my_side)
        if self.last_fen and fen == self.last_fen:
            return False  # 局面没变（可能对手还没走）
        if board.side != self.my_side:
            print(f"[main] 局面显示轮到 {'红' if board.side=='red' else '黑'}，不是我方，等待")
            self.last_fen = fen
            return False

        res = choose_move(board, self.history, self.my_side, self.cfg,
                          max_retries=self.cfg.max_retries, verbose=self.cfg.verbose)
        move = res["move"]
        from .engine import parse_move
        f0, r0, f1, r1 = parse_move(move)
        print(f"[main] 我方({self.my_side})走 {move} —— {res['reason']}")

        # 点击：先点源格，再点目标格
        src, dst = self.mapper.cell_center(f0, r0), self.mapper.cell_center(f1, r1)
        self.input.tap(*src)
        time.sleep(0.35)
        self.input.tap(*dst)
        time.sleep(1.2)  # 等落子动画

        # 确认：走完后的局面（用 apply 预测 + 截图核对一次）
        b2 = apply_move(Board.from_fen(fen, side=self.my_side), f0, r0, f1, r1)
        expected = b2.fen()
        try:
            got, _ = self._snapshot()
        except Exception:
            got = ""
        if got and got != expected.split()[0]:
            print(f"[main] 点击后局面与预期不符（识别={got.split()[0][:30]}…），下回合再核对")
        self.last_fen = expected
        self.history.append(move)
        self.my_turn = False
        self._consecutive_errors = 0
        return True

    # ---------- 主循环 ----------

    def run(self, once: bool = False):
        print(f"[main] 我执{'红' if self.my_side=='red' else '黑'}，"
              f"截图后端={self.cfg.screen_backend}，点击后端={self.cfg.input_backend}")
        if not wait_until_ready(self.input):
            raise SystemExit("[main] 点击后端未就绪：请开启无障碍服务（ClickServer）或连接 adb")

        try:
            while True:
                fen = self.get_stable_fen()
                if not fen:
                    self._consecutive_errors += 1
                    if self._consecutive_errors >= 5:
                        print("[main] 连续识别失败过多，退出")
                        break
                    time.sleep(self.cfg.poll_interval)
                    continue
                self._consecutive_errors = 0

                if fen == self.last_fen:
                    # 局面没变：等待对手/等待动画
                    time.sleep(self.cfg.poll_interval)
                    continue

                if self.my_turn:
                    ok = self.try_move()
                    if once:
                        break
                    if not ok:
                        time.sleep(self.cfg.poll_interval)
                else:
                    # 局面变了且不是我方行动：对手走完了
                    print(f"[main] 检测到对手走棋（{fen.split()[0][:30]}…），轮到我")
                    self.last_fen = fen
                    self.my_turn = True
                    time.sleep(self.cfg.poll_interval)
        except KeyboardInterrupt:
            print("\n[main] 已停止")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description="象棋 Agent 主循环")
    ap.add_argument("--once", action="store_true", help="只执行一次走棋后退出")
    ap.add_argument("--debug", action="store_true", help="保存截图/识别文本到 debug/")
    args = ap.parse_args(argv)
    cfg = load_config()
    agent = Agent(cfg, debug=args.debug)
    agent.run(once=args.once)


if __name__ == "__main__":
    main()
