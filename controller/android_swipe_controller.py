from __future__ import annotations

from dataclasses import dataclass
import queue
import re
import subprocess
import threading
import time

from controller.action import Lane, PlayerState, Posture


@dataclass(frozen=True)
class _Swipe:
    direction: str
    generation: int


class AndroidSwipeController:
    """Sends ordered, native Android swipe gestures through ADB."""

    _SWIPE_DURATION_MS = 120
    _DUPLICATE_COOLDOWN_S = 0.1
    _QUEUE_SIZE = 16

    def __init__(self, adb_path: str = "adb"):
        import shutil
        import os
        
        # If the user didn't specify a custom path, and it's not in PATH, try common locations
        if adb_path == "adb" and not shutil.which("adb"):
            local_appdata = os.environ.get("LOCALAPPDATA")
            if local_appdata:
                fallback = os.path.join(local_appdata, "Android", "Sdk", "platform-tools", "adb.exe")
                if os.path.exists(fallback):
                    adb_path = fallback
                    
        self._adb_path = adb_path
        self._queue: queue.Queue[_Swipe | None] = queue.Queue(maxsize=self._QUEUE_SIZE)
        self._worker: threading.Thread | None = None
        self._worker_lock = threading.Lock()
        self._user_paused = True
        self._shutdown = False
        self._generation = 0
        self._device_serial: str | None = None
        self._screen_size: tuple[int, int] | None = None
        self._last_error = "Output disabled"
        self._last_intent: PlayerState | None = None
        self._previous_posture: Posture | None = None
        self._last_submission: dict[str, float] = {}

    @property
    def is_active(self) -> bool:
        return (
            not self._user_paused
            and self._device_serial is not None
            and self._screen_size is not None
            and not self._shutdown
        )

    @property
    def state(self) -> str:
        return "ACTIVE" if self.is_active else "PAUSED"

    @property
    def last_intent(self) -> PlayerState | None:
        return self._last_intent

    @property
    def device_label(self) -> str:
        if self._device_serial and self._screen_size:
            width, height = self._screen_size
            return f"{self._device_serial} ({width}x{height})"
        return self._last_error

    def resume(self) -> bool:
        """Connect to exactly one authorized device and start the worker."""
        if self._shutdown:
            return False
        self._user_paused = False
        if not self._discover_device():
            self._user_paused = True
            return False
        self._ensure_worker()
        return True

    def pause(self) -> None:
        self._user_paused = True
        self.clear_pending()

    def clear_pending(self) -> None:
        self._generation += 1
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
            else:
                self._queue.task_done()

    def update(self, player_state: PlayerState) -> None:
        """Submit a one-shot vertical swipe when posture enters jump or slide."""
        previous = self._previous_posture
        self._previous_posture = player_state.posture
        self._last_intent = player_state

        if not self.is_active or previous == player_state.posture:
            return
        if player_state.posture == Posture.JUMP:
            self._submit("up")
        elif player_state.posture == Posture.SLIDE:
            self._submit("down")

    def dispatch_lane_change(self, previous_game_lane: int, desired_game_lane: int) -> None:
        """Submit one horizontal swipe for each lane step, in order."""
        if not self.is_active or previous_game_lane == desired_game_lane:
            return
        direction = "left" if desired_game_lane < previous_game_lane else "right"
        for _ in range(abs(desired_game_lane - previous_game_lane)):
            self._submit(direction, bypass_cooldown=True)

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self.pause()
        self._shutdown = True
        self._queue.put(None)
        if self._worker is not None:
            self._worker.join(timeout=1.0)

    def _ensure_worker(self) -> None:
        with self._worker_lock:
            if self._worker is None:
                self._worker = threading.Thread(
                    target=self._run_worker,
                    name="android-swipe-worker",
                    daemon=True,
                )
                self._worker.start()

    def _discover_device(self) -> bool:
        try:
            result = subprocess.run(
                [self._adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._set_unavailable(f"ADB unavailable: {exc}")
            return False

        if result.returncode != 0:
            self._set_unavailable("ADB device discovery failed")
            return False

        devices = []
        for line in result.stdout.splitlines()[1:]:
            fields = line.split()
            if len(fields) >= 2:
                devices.append((fields[0], fields[1]))
        if len(devices) != 1 or devices[0][1] != "device":
            self._set_unavailable("Connect exactly one authorized ADB device")
            return False

        serial = devices[0][0]
        try:
            size_result = subprocess.run(
                [self._adb_path, "-s", serial, "shell", "wm", "size"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._set_unavailable(f"Could not read Android display size: {exc}")
            return False

        sizes = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", size_result.stdout)
        if size_result.returncode != 0 or not sizes:
            self._set_unavailable("Could not read Android display size")
            return False

        width, height = (int(value) for value in sizes[-1])
        self._device_serial = serial
        self._screen_size = (width, height)
        self._last_error = ""
        return True

    def _set_unavailable(self, message: str) -> None:
        self._device_serial = None
        self._screen_size = None
        self._last_error = message
        self._user_paused = True
        self.clear_pending()

    def _submit(self, direction: str, bypass_cooldown: bool = False) -> None:
        now = time.monotonic()
        if not bypass_cooldown and now - self._last_submission.get(direction, -float("inf")) < self._DUPLICATE_COOLDOWN_S:
            return
        self._last_submission[direction] = now
        try:
            self._queue.put_nowait(_Swipe(direction, self._generation))
        except queue.Full:
            self._set_unavailable("ADB gesture queue is full")

    def _run_worker(self) -> None:
        while True:
            swipe = self._queue.get()
            try:
                if swipe is None:
                    return
                if self.is_active and swipe.generation == self._generation:
                    self._send_swipe(swipe.direction)
            finally:
                self._queue.task_done()

    def _send_swipe(self, direction: str) -> None:
        if self._device_serial is None or self._screen_size is None:
            return
        width, height = self._screen_size
        x, y = width // 2, height // 2
        targets = {
            "left": (round(width * 0.30), y),
            "right": (round(width * 0.70), y),
            "up": (x, round(height * 0.35)),
            "down": (x, round(height * 0.65)),
        }
        target_x, target_y = targets[direction]
        try:
            result = subprocess.run(
                [
                    self._adb_path,
                    "-s",
                    self._device_serial,
                    "shell",
                    "input",
                    "swipe",
                    str(x),
                    str(y),
                    str(target_x),
                    str(target_y),
                    str(self._SWIPE_DURATION_MS),
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            self._set_unavailable(f"ADB gesture failed: {exc}")
            return
        if result.returncode != 0:
            self._set_unavailable("ADB gesture failed; output paused")
