import unittest
from types import SimpleNamespace
from unittest.mock import patch

from controller.scrcpy_window import ScrcpyWindow


def _make_config(title="MotionRunner-Expo", refresh_ms=200):
    return SimpleNamespace(
        mouse_window_title=title,
        mouse_bounds_refresh_ms=refresh_ms,
    )


def _fake_get_client_rect(hwnd, rect_ptr):
    rect_ptr.contents.right = 800
    rect_ptr.contents.bottom = 600
    return True


def _fake_client_to_screen(hwnd, pt_ptr):
    pt_ptr.contents.x = 100
    pt_ptr.contents.y = 50
    return True


class ScrcpyWindowTests(unittest.TestCase):
    @patch("controller.scrcpy_window.user32")
    def test_find_returns_inner_client_rect_on_success(self, mock_user32):
        mock_user32.FindWindowW.return_value = 12345
        mock_user32.GetClientRect.side_effect = _fake_get_client_rect
        mock_user32.ClientToScreen.side_effect = _fake_client_to_screen

        window = ScrcpyWindow(_make_config())
        bounds = window.find()

        self.assertEqual(bounds, (100, 50, 900, 650))
        self.assertTrue(window.is_available)

    @patch("controller.scrcpy_window.user32")
    def test_find_returns_none_when_window_not_found(self, mock_user32):
        mock_user32.FindWindowW.return_value = 0

        window = ScrcpyWindow(_make_config())
        bounds = window.find()

        self.assertIsNone(bounds)
        self.assertFalse(window.is_available)

    @patch("controller.scrcpy_window.user32")
    def test_find_throttles_refresh_within_interval(self, mock_user32):
        mock_user32.FindWindowW.return_value = 12345
        mock_user32.GetClientRect.side_effect = _fake_get_client_rect
        mock_user32.ClientToScreen.side_effect = _fake_client_to_screen

        window = ScrcpyWindow(_make_config(refresh_ms=200))
        window.find()
        window.find()

        self.assertEqual(mock_user32.FindWindowW.call_count, 1)

    @patch("controller.scrcpy_window.user32")
    def test_center_returns_center_of_cached_bounds(self, mock_user32):
        mock_user32.FindWindowW.return_value = 12345
        mock_user32.GetClientRect.side_effect = _fake_get_client_rect
        mock_user32.ClientToScreen.side_effect = _fake_client_to_screen

        window = ScrcpyWindow(_make_config())
        window.find()

        self.assertEqual(window.center(), (500, 350))


if __name__ == "__main__":
    unittest.main()
