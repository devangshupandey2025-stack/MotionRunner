import unittest
from types import SimpleNamespace
from unittest.mock import patch

from controller.action import Ability, Lane, PlayerState, Posture
from controller.mouse_controller import MouseController


def _make_config(cursor_speed=400.0):
    return SimpleNamespace(cursor_speed=cursor_speed)


class FakeMouse:
    """Fake pynput.mouse.Controller that records position setter calls."""

    def __init__(self, position=(0, 0)):
        self._position = position
        self.set_calls: list = []

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, value):
        self.set_calls.append(value)
        self._position = value


class StubWindow:
    """Stub ScrcpyWindow with mutable bounds and availability."""

    def __init__(self, bounds=(0, 0, 1000, 1000), available=True):
        self.bounds = bounds
        self.available = available

    @property
    def is_available(self):
        return self.available

    def find(self):
        return self.bounds

    def center(self):
        if self.bounds is None:
            return None
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)


class MouseControllerTests(unittest.TestCase):
    @patch("controller.mouse_controller.Controller")
    def test_left_lane_decreases_cursor_x(self, mock_controller_class):
        # (a) LEFT for 1.0s at speed=400 -> cursor_x decreased by ~400
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 1.0)

        self.assertEqual(fake_mouse.set_calls[-1], (100, 500))

    @patch("controller.mouse_controller.Controller")
    def test_right_lane_increases_cursor_x(self, mock_controller_class):
        # (b) RIGHT for 1.0s -> cursor_x increased by ~400
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.RIGHT, posture=Posture.RUNNING), 1.0)

        self.assertEqual(fake_mouse.set_calls[-1], (900, 500))

    @patch("controller.mouse_controller.Controller")
    def test_center_lane_no_x_movement(self, mock_controller_class):
        # (c) CENTER -> no movement (delta_x = 0), but setter IS called (write every frame)
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.CENTER, posture=Posture.RUNNING), 1.0)

        self.assertEqual(fake_mouse.set_calls[-1], (500, 500))

    @patch("controller.mouse_controller.Controller")
    def test_jump_posture_decreases_cursor_y(self, mock_controller_class):
        # (d) JUMP for 0.5s at speed=400 -> cursor_y decreased by ~200
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.CENTER, posture=Posture.JUMP), 0.5)

        self.assertEqual(fake_mouse.set_calls[-1], (500, 300))

    @patch("controller.mouse_controller.Controller")
    def test_slide_posture_increases_cursor_y(self, mock_controller_class):
        # (e) SLIDE for 0.5s -> cursor_y increased by ~200
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.CENTER, posture=Posture.SLIDE), 0.5)

        self.assertEqual(fake_mouse.set_calls[-1], (500, 700))

    @patch("controller.mouse_controller.Controller")
    def test_jump_and_left_diagonal_movement(self, mock_controller_class):
        # (f) JUMP + LEFT simultaneously -> diagonal movement (both x and y change)
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.JUMP), 1.0)

        self.assertEqual(fake_mouse.set_calls[-1], (100, 100))

    @patch("controller.mouse_controller.Controller")
    def test_clamp_to_bounds_on_large_delta(self, mock_controller_class):
        # (g) clamp: cursor cannot escape (0,0,1000,1000) even with large delta
        fake_mouse = FakeMouse(position=(950, 950))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.RIGHT, posture=Posture.SLIDE), 10.0)

        self.assertEqual(fake_mouse.set_calls[-1], (1000, 1000))

    @patch("controller.mouse_controller.Controller")
    def test_pause_blocks_position_writes(self, mock_controller_class):
        # (h) pause() then update() -> no position change AND no setter call
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.pause()
        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 1.0)

        self.assertEqual(len(fake_mouse.set_calls), 0)
        self.assertEqual(mc.state, "PAUSED")

    @patch("controller.mouse_controller.Controller")
    def test_reset_to_center_works_while_paused(self, mock_controller_class):
        # (i) reset_to_center() snaps to (500, 500) AND works while paused (does NOT unpause)
        fake_mouse = FakeMouse(position=(100, 100))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.pause()
        mc.reset_to_center()

        self.assertEqual(fake_mouse.set_calls[-1], (500, 500))
        self.assertEqual(mc.state, "PAUSED")

    @patch("controller.mouse_controller.Controller")
    def test_inactive_when_window_unavailable(self, mock_controller_class):
        # (j) is_active False when window.is_available is False -> no position writes
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000), available=False)
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 1.0)

        self.assertEqual(len(fake_mouse.set_calls), 0)
        self.assertFalse(mc.is_active)
        self.assertEqual(mc.state, "PAUSED")

    @patch("controller.mouse_controller.Controller")
    def test_auto_resume_when_window_becomes_available(self, mock_controller_class):
        # (k) is_active True again when window.is_available becomes True (auto-resume)
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000), available=False)
        mc = MouseController(_make_config(), window)

        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 1.0)
        self.assertEqual(len(fake_mouse.set_calls), 0)

        window.available = True
        mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 1.0)

        self.assertEqual(len(fake_mouse.set_calls), 1)
        self.assertTrue(mc.is_active)
        self.assertEqual(mc.state, "ACTIVE")

    @patch("controller.mouse_controller.Controller")
    def test_hoverboard_alone_no_movement(self, mock_controller_class):
        # (l) HOVERBOARD active alone -> no cursor movement (delta_x=0, delta_y=0)
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(
            PlayerState(
                lane=Lane.CENTER,
                posture=Posture.RUNNING,
                abilities={Ability.HOVERBOARD},
            ),
            1.0,
        )

        self.assertEqual(fake_mouse.set_calls[-1], (500, 500))

    @patch("controller.mouse_controller.Controller")
    def test_hoverboard_with_left_still_moves(self, mock_controller_class):
        # (m) HOVERBOARD + LEFT -> cursor moves left (HOVERBOARD ignored, lane drives x)
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        mc.update(
            PlayerState(
                lane=Lane.LEFT,
                posture=Posture.RUNNING,
                abilities={Ability.HOVERBOARD},
            ),
            1.0,
        )

        self.assertEqual(fake_mouse.set_calls[-1], (100, 500))

    @patch("controller.mouse_controller.Controller")
    def test_bounds_shrink_clamps_cursor(self, mock_controller_class):
        # (n) bounds shrink: cursor at (900,500) when bounds change to (0,0,800,800)
        #     -> next update clamps to (800, 500)
        fake_mouse = FakeMouse(position=(900, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        window.bounds = (0, 0, 800, 800)
        mc.update(PlayerState(lane=Lane.CENTER, posture=Posture.RUNNING), 0.016)

        self.assertEqual(fake_mouse.set_calls[-1], (800, 500))

    @patch("controller.mouse_controller.Controller")
    def test_three_frames_three_writes_decreasing_x(self, mock_controller_class):
        # (o) integration guard: 3 frames with LEFT -> setter called exactly 3 times
        #     with decreasing x values
        fake_mouse = FakeMouse(position=(500, 500))
        mock_controller_class.return_value = fake_mouse
        window = StubWindow(bounds=(0, 0, 1000, 1000))
        mc = MouseController(_make_config(), window)

        for _ in range(3):
            mc.update(PlayerState(lane=Lane.LEFT, posture=Posture.RUNNING), 0.016)

        self.assertEqual(len(fake_mouse.set_calls), 3)
        xs = [pos[0] for pos in fake_mouse.set_calls]
        self.assertTrue(xs[0] > xs[1] > xs[2])


if __name__ == "__main__":
    unittest.main()
