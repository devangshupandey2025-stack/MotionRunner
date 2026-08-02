import ctypes
import time
from ctypes import wintypes

from utils.config import AppConfig

try:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = wintypes.HWND
    user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.GetClientRect.restype = wintypes.BOOL
    user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.restype = wintypes.BOOL
    user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
except (OSError, AttributeError):
    user32 = None


class ScrcpyWindow:
    def __init__(self, config: AppConfig):
        self._title: str = config.mouse_window_title
        self._refresh_interval_ms: int = config.mouse_bounds_refresh_ms
        self._cached_bounds: tuple[int, int, int, int] | None = None
        self._last_refresh_ms: float = 0.0

    @property
    def is_available(self) -> bool:
        return self._cached_bounds is not None

    def find(self) -> tuple[int, int, int, int] | None:
        now_ms = time.time() * 1000
        self.refresh_if_stale(now_ms)
        return self._cached_bounds

    def refresh_if_stale(self, now_ms: float) -> None:
        if now_ms - self._last_refresh_ms > self._refresh_interval_ms:
            self._refresh()
            self._last_refresh_ms = now_ms

    def _refresh(self) -> bool:
        if user32 is None:
            return False
        hwnd = user32.FindWindowW(None, self._title)
        if not hwnd:
            self._cached_bounds = None
            return False
        rect = wintypes.RECT()
        if not user32.GetClientRect(hwnd, ctypes.pointer(rect)):
            self._cached_bounds = None
            return False
        pt = wintypes.POINT()
        if not user32.ClientToScreen(hwnd, ctypes.pointer(pt)):
            self._cached_bounds = None
            return False
        left = pt.x
        top = pt.y
        right = left + rect.right
        bottom = top + rect.bottom
        self._cached_bounds = (left, top, right, bottom)
        return True

    def center(self) -> tuple[int, int] | None:
        if self._cached_bounds is None:
            return None
        left, top, right, bottom = self._cached_bounds
        return ((left + right) // 2, (top + bottom) // 2)
