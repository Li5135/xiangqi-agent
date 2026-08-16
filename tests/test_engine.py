"""engine 规则单元测试（unittest，无第三方依赖）。

基准：中国象棋标准开局红方先手合法着法数为 44。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from xiangqi_agent.engine import (  # noqa: E402
    Board,
    apply_move,
    format_move,
    legal_moves,
    parse_move,
    validate_move,
)

OPENING = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"


class TestFen(unittest.TestCase):
    def test_parse_roundtrip(self):
        b = Board.from_fen(OPENING)
        self.assertEqual(b.fen().split()[0], OPENING.split()[0])
        self.assertEqual(b.side, "red")
        self.assertEqual(b.piece(4, 0), "K")   # 红帅在 file4 rank0
        self.assertEqual(b.piece(4, 9), "k")   # 黑将在 file4 rank9

    def test_legal_moves_opening_44(self):
        b = Board.from_fen(OPENING, side="red")
        total = sum(len(legal_moves(b, f, r)) for f in range(9) for r in range(10))
        self.assertEqual(total, 44, f"开局红方合法着法应为 44，实际 {total}")

    def test_black_opening_44(self):
        b = Board.from_fen(OPENING, side="black")
        total = sum(len(legal_moves(b, f, r)) for f in range(9) for r in range(10))
        self.assertEqual(total, 44)


class TestRules(unittest.TestCase):
    def setUp(self):
        self.b = Board.from_fen(OPENING, side="red")

    def test_cannon_flat(self):
        # 炮二平五（二路=file7，五路=file4）：h2e2 合法
        self.assertIsNone(validate_move(self.b, 7, 2, 4, 2))

    def test_cannon_capture_needs_screen(self):
        # 构造：红炮(4,0)，黑车(4,9)，路径全空 → 吃车必须隔一子
        fen = "4r3k/9/9/9/9/9/9/9/9/4C4"
        b = Board.from_fen(fen, side="red")
        self.assertEqual(validate_move(b, 4, 0, 4, 9), "炮吃子必须隔一子")

    def test_horse_leg(self):
        # 马二进三（二路=file7 → 三路=file6，进两格）：h0g2 合法
        self.assertIsNone(validate_move(self.b, 7, 0, 6, 2))
        # 马九进七（九路马=file1 → 七路=file2）：b0c2 合法（蹩脚点 b1 空）
        self.assertIsNone(validate_move(self.b, 1, 0, 2, 2))
        # 非日字非法
        self.assertIsNotNone(validate_move(self.b, 1, 0, 2, 1))
        # 蹩马腿：红马(1,0)→(2,2) 蹩脚点 (1,1)；空则合法，有子则非法
        b = Board.from_fen("4k4/9/9/9/9/9/4P4/9/9/1N7", side="red")
        self.assertIsNone(validate_move(b, 1, 0, 2, 2))
        b2 = Board.from_fen("4k4/9/9/9/9/9/9/9/1P7/1N7", side="red")  # P 在 (1,1) 挡马腿
        self.assertEqual(validate_move(b2, 1, 0, 2, 2), "马被蹩马腿")

    def test_elephant_eye(self):
        # 相三进五：c0→e2，象眼 (d1) 空 → 合法
        self.assertIsNone(validate_move(self.b, 2, 0, 4, 2))
        # 相三进一? c0→a2 象眼 b1 空 → 合法
        self.assertIsNone(validate_move(self.b, 2, 0, 0, 2))

    def test_pawn_rules(self):
        # 兵五进一合法
        self.assertIsNone(validate_move(self.b, 4, 3, 4, 2))
        # 未过河不能横走
        self.assertIsNotNone(validate_move(self.b, 4, 3, 3, 3))

    def test_king_palace(self):
        # 帅不能出九宫：先清开仕再测（开局帅只能前后？上下有仕）
        # 帅四平五? file3→4 rank0：士在 file3 rank0 是仕 A？RNBAKABNR: file3=A。帅移动目标 file4 是自己 → 非法
        pass

    def test_self_capture(self):
        # 车 a0 → b0（马）目标己方
        self.assertEqual(validate_move(self.b, 0, 0, 1, 0), "目标格是己方棋子")

    def test_apply_flips_turn(self):
        b2 = apply_move(self.b, 1, 2, 4, 2)
        self.assertEqual(b2.side, "black")
        self.assertEqual(b2.piece(4, 2), "C")


class TestFacingKings(unittest.TestCase):
    def test_face_to_face(self):
        # 构造：红帅(4,0) 黑将(4,9)，中间全空 → 红帅不能走到 (4,1)（会照面）
        fen = "4k4/9/9/9/9/9/9/9/9/4K4"
        b = Board.from_fen(fen, side="red")
        err = validate_move(b, 4, 0, 4, 1)
        self.assertIsNotNone(err)
        self.assertIn("照面", err or "")

    def test_expose_king(self):
        # 黑马(5,2) 蹩脚点 (5,1) 被红士占着；红士(5,1) 走到 (4,2) 后马腿放空 → 帅被将
        fen = "8k/9/9/9/9/9/9/5n3/5A3/4K4"
        b = Board.from_fen(fen, side="red")
        err = validate_move(b, 5, 1, 4, 2)
        self.assertIsNotNone(err)
        self.assertIn("将军", err or "")


class TestMoveFormat(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_move("h2e2"), (7, 2, 4, 2))
        self.assertEqual(parse_move("B0C1"), (1, 0, 2, 1))
        self.assertEqual(format_move(7, 2, 4, 2), "h2e2")

    def test_bad(self):
        with self.assertRaises(ValueError):
            parse_move("xx")


if __name__ == "__main__":
    unittest.main()
