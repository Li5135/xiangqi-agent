"""点击后端：clickserver（手机，HTTP→无障碍服务）/ adb（电脑调试）。"""
import subprocess
import time

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class InputError(RuntimeError):
    pass


class ClickServerBackend:
    """POST http://127.0.0.1:8123 → 无障碍服务 dispatchGesture。"""

    def __init__(self, host: str = "127.0.0.1", port: int = 8123, timeout: float = 5.0):
        if requests is None:
            raise InputError("缺少 requests，pip install requests")
        self.base = f"http://{host}:{port}"
        self.timeout = timeout

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.base}/health", timeout=self.timeout)
            return r.status_code == 200
        except Exception:
            return False

    def tap(self, x: float, y: float):
        r = requests.post(
            f"{self.base}/tap", json={"x": float(x), "y": float(y)}, timeout=self.timeout
        )
        if r.status_code != 200:
            raise InputError(f"/tap 失败: {r.status_code} {r.text[:200]}")

    def swipe(self, x1, y1, x2, y2, duration_ms: int = 300):
        r = requests.post(
            f"{self.base}/swipe",
            json={"from": [float(x1), float(y1)], "to": [float(x2), float(y2)],
                  "duration": int(duration_ms)},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise InputError(f"/swipe 失败: {r.status_code} {r.text[:200]}")


class AdbBackend:
    def __init__(self, serial: str = ""):
        self.serial = serial

    def _cmd(self, *args: str) -> list[str]:
        return ["adb", *(["-s", self.serial] if self.serial else []), *args]

    def _run(self, *args: str):
        r = subprocess.run(self._cmd(*args), capture_output=True, timeout=15)
        if r.returncode != 0:
            raise InputError(
                f"adb {' '.join(args)} 失败: {r.stderr.decode('utf-8','replace')[:300]}"
            )

    def health(self) -> bool:
        try:
            self._run("shell", "echo", "ok")
            return True
        except Exception:
            return False

    def tap(self, x: float, y: float):
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1, y1, x2, y2, duration_ms: int = 300):
        self._run(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms)),
        )


def make_input_backend(kind: str, serial: str = "", host: str = "127.0.0.1", port: int = 8123):
    if kind == "clickserver":
        return ClickServerBackend(host=host, port=port)
    if kind == "adb":
        return AdbBackend(serial=serial)
    raise ValueError(f"未知点击后端: {kind}")


def wait_until_ready(backend, tries: int = 10, interval: float = 1.0) -> bool:
    """等待点击后端就绪（ClickServer 无障碍服务开启 / adb 连上）。"""
    for i in range(tries):
        if backend.health():
            return True
        time.sleep(interval)
    return False
