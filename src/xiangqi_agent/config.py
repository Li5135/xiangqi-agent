"""配置加载：config.json（或 config.example.json 兜底）。"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = PROJECT_ROOT / "config.json"
EXAMPLE_PATH = PROJECT_ROOT / "config.example.json"

REQUIRED_KEYS = ("glm", "deepseek")


class Config:
    def __init__(self, data: dict):
        self.data = data
        self.glm = data.get("glm", {})
        self.deepseek = data.get("deepseek", {})
        self.side = data.get("side", "red").lower()
        self.screen_backend = data.get("screen_backend", "termux")
        self.input_backend = data.get("input_backend", "clickserver")
        self.clickserver = data.get("clickserver", {"host": "127.0.0.1", "port": 8123})
        self.adb = data.get("adb", {"serial": ""})
        self.board = data.get("board")
        self.poll_interval = float(data.get("poll_interval", 2.0))
        self.max_retries = int(data.get("max_retries", 3))
        self.debug_dir = data.get("debug_dir", "debug")
        self.verbose = bool(data.get("verbose", True))

    def save(self, path: str | os.PathLike | None = None):
        (PROJECT_ROOT if path is None else Path(path)).write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def load_config(path: str | os.PathLike | None = None) -> Config:
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        if EXAMPLE_PATH.exists():
            print(f"[config] 未找到 {p.name}，使用 config.example.json（记得填 API key）")
            p = EXAMPLE_PATH
        else:
            raise FileNotFoundError(f"找不到配置文件: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if not data.get(k, {}).get("api_key")
               or "在这里填" in str(data.get(k, {}).get("api_key", ""))]
    if missing:
        raise SystemExit(f"[config] 缺少 API key: {', '.join(missing)}，请编辑 {p}")
    return Config(data)
