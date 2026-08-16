"""截图后端：termux（手机）/ adb（电脑调试）。统一返回 PIL Image。"""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class ScreenError(RuntimeError):
    pass


def _run(cmd: list[str], timeout: int = 30) -> bytes:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except FileNotFoundError as e:
        raise ScreenError(f"命令不存在: {cmd[0]}（{e}）") from e
    except subprocess.TimeoutExpired as e:
        raise ScreenError(f"命令超时: {cmd}") from e
    if r.returncode != 0:
        raise ScreenError(
            f"命令失败: {' '.join(cmd)}\nstderr: {r.stderr.decode('utf-8', 'replace')[:500]}"
        )
    return r.stdout


def adb_devices() -> list[str]:
    """返回已连接的 adb 设备序列号（电脑调试用）。"""
    out = _run(["adb", "devices"]).decode("utf-8", "replace")
    devs = []
    for line in out.splitlines()[1:]:
        if line.strip() and "offline" not in line:
            devs.append(line.split()[0])
    return devs


def take_screenshot_termux(path: str | None = None) -> Image.Image:
    """Termux 截图：termux-screenshot（Termux:API）。"""
    if requests is None:
        raise ScreenError("缺少 requests，pip install requests")
    # termux-screenshot 默认保存到当前目录 screenshots/；用 --dir 指定临时目录
    tmp = Path(tempfile.mkdtemp(prefix="xq_shot_"))
    r = subprocess.run(
        ["termux-screenshot", "-d", str(tmp)], capture_output=True, timeout=30
    )
    if r.returncode != 0:
        raise ScreenError(
            "termux-screenshot 失败，请确认已安装 Termux:API 并授予截图权限\n"
            + r.stderr.decode("utf-8", "replace")[:300]
        )
    files = sorted(tmp.glob("*.png")) + sorted(tmp.glob("*.jpg"))
    if not files:
        raise ScreenError("termux-screenshot 未产出图片")
    img = Image.open(files[-1]).convert("RGB")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    return img


def take_screenshot_adb(path: str | None = None, serial: str = "") -> Image.Image:
    """adb 截图：adb exec-out screencap -p。"""
    cmd = ["adb"]
    if serial:
        cmd += ["-s", serial]
    cmd += ["exec-out", "screencap", "-p"]
    data = _run(cmd)
    img = Image.open(__import__("io").BytesIO(data)).convert("RGB")
    if path:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
    return img


class Screen:
    """按 config.screen_backend 选择实现。"""

    def __init__(self, backend: str, serial: str = ""):
        self.backend = backend
        self.serial = serial
        if backend == "termux":
            self._shot = take_screenshot_termux
        elif backend == "adb":
            self._shot = lambda p=None: take_screenshot_adb(p, self.serial)
        else:
            raise ValueError(f"未知截图后端: {backend}")

    def take(self, path: str | None = None) -> Image.Image:
        return self._shot(path)

    def __repr__(self):  # pragma: no cover
        return f"Screen(backend={self.backend})"
