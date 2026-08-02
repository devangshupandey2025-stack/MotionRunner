import subprocess
import unittest
from unittest.mock import patch

from controller.action import Lane, PlayerState, Posture
from controller.android_swipe_controller import AndroidSwipeController


def _result(stdout="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr="")


def _connected_device_results():
    return [
        _result("List of devices attached\nphone-1\tdevice\n"),
        _result("Physical size: 720x1600\n"),
    ]


class AndroidSwipeControllerTests(unittest.TestCase):
    def _controller(self, mock_run):
        mock_run.side_effect = _connected_device_results()
        controller = AndroidSwipeController("adb")
        self.assertTrue(controller.resume())
        self.addCleanup(controller.shutdown)
        return controller

    @patch("controller.android_swipe_controller.subprocess.run")
    def test_discovers_one_authorized_device_and_display_size(self, mock_run):
        controller = self._controller(mock_run)

        self.assertTrue(controller.is_active)
        self.assertEqual(controller.device_label, "phone-1 (720x1600)")
        self.assertEqual(mock_run.call_count, 2)

    @patch("controller.android_swipe_controller.subprocess.run")
    def test_rejects_missing_or_ambiguous_devices(self, mock_run):
        mock_run.return_value = _result("List of devices attached\na\tdevice\nb\tdevice\n")
        controller = AndroidSwipeController("adb")
        self.addCleanup(controller.shutdown)

        self.assertFalse(controller.resume())
        self.assertFalse(controller.is_active)
        self.assertEqual(controller.state, "PAUSED")
        self.assertIn("exactly one", controller.device_label)

    @patch("controller.android_swipe_controller.subprocess.run")
    def test_lane_steps_and_posture_entries_send_ordered_swipes(self, mock_run):
        controller = self._controller(mock_run)
        mock_run.reset_mock()
        mock_run.side_effect = lambda *args, **kwargs: _result()

        controller.update(PlayerState(Lane.CENTER, Posture.RUNNING))
        controller.dispatch_lane_change(2, 0)
        controller.update(PlayerState(Lane.CENTER, Posture.JUMP))
        controller.update(PlayerState(Lane.CENTER, Posture.JUMP))
        controller.update(PlayerState(Lane.CENTER, Posture.SLIDE))
        controller._queue.join()

        swipe_calls = [call.args[0] for call in mock_run.call_args_list]
        self.assertEqual(
            swipe_calls,
            [
                ["adb", "-s", "phone-1", "shell", "input", "swipe", "360", "800", "216", "800", "120"],
                ["adb", "-s", "phone-1", "shell", "input", "swipe", "360", "800", "216", "800", "120"],
                ["adb", "-s", "phone-1", "shell", "input", "swipe", "360", "800", "360", "560", "120"],
                ["adb", "-s", "phone-1", "shell", "input", "swipe", "360", "800", "360", "1040", "120"],
            ],
        )

    @patch("controller.android_swipe_controller.subprocess.run")
    @patch("controller.android_swipe_controller.time.monotonic", side_effect=[1.0, 1.05, 1.2])
    def test_duplicate_gesture_cooldown_preserves_later_input(self, mock_clock, mock_run):
        controller = self._controller(mock_run)
        mock_run.reset_mock()
        mock_run.side_effect = lambda *args, **kwargs: _result()

        controller._submit("up")
        controller._submit("up")
        controller._submit("up")
        controller._queue.join()

        self.assertEqual(mock_run.call_count, 2)

    @patch("controller.android_swipe_controller.subprocess.run")
    def test_pause_prevents_future_gestures_and_reuses_one_worker(self, mock_run):
        controller = self._controller(mock_run)
        worker = controller._worker
        mock_run.reset_mock()
        mock_run.side_effect = lambda *args, **kwargs: _result()

        controller._ensure_worker()
        self.assertIs(controller._worker, worker)
        controller.pause()
        controller.dispatch_lane_change(1, 0)
        controller.update(PlayerState(Lane.CENTER, Posture.JUMP))
        controller._queue.join()

        self.assertEqual(mock_run.call_count, 0)


if __name__ == "__main__":
    unittest.main()
