from typing import assert_never

from pynput.mouse import Controller

from controller.action import Lane, PlayerState, Posture
from controller.scrcpy_window import ScrcpyWindow
from utils.config import AppConfig


class MouseController:
    """Consumes PlayerState directly and moves the Windows cursor via pynput."""

    def __init__(self, config: AppConfig, window: ScrcpyWindow):
        self.config = config
        self._window = window
        self._mouse = Controller()
        self._user_paused = False
        self._last_intent: PlayerState | None = None

    @property
    def is_active(self) -> bool:
        return not self._user_paused and self._window.is_available

    @property
    def state(self) -> str:
        return "ACTIVE" if self.is_active else "PAUSED"

    @property
    def current_position(self) -> tuple[int, int] | None:
        return self._mouse.position

    @property
    def last_intent(self) -> PlayerState | None:
        return self._last_intent

    def update(self, player_state: PlayerState, dt: float) -> None:
        if not self.is_active:
            self._last_intent = player_state
            return

        speed = self.config.cursor_speed

        match player_state.lane:
            case Lane.LEFT:
                delta_x = -speed * dt
            case Lane.RIGHT:
                delta_x = speed * dt
            case Lane.CENTER:
                delta_x = 0.0
            case never:
                assert_never(never)

        match player_state.posture:
            case Posture.JUMP:
                delta_y = -speed * dt
            case Posture.SLIDE:
                delta_y = speed * dt
            case Posture.RUNNING:
                delta_y = 0.0
            case never:
                assert_never(never)

        current_x, current_y = self._mouse.position
        new_x = current_x + delta_x
        new_y = current_y + delta_y

        bounds = self._window.find()
        if bounds is not None:
            left, top, right, bottom = bounds
            new_x = max(left, min(new_x, right))
            new_y = max(top, min(new_y, bottom))

        self._mouse.position = (new_x, new_y)
        self._last_intent = player_state

    def pause(self) -> None:
        self._user_paused = True

    def resume(self) -> None:
        self._user_paused = False

    def reset_to_center(self) -> None:
        center = self._window.center()
        if center is not None:
            self._mouse.position = center

    def shutdown(self) -> None:
        self._user_paused = True
