import unittest

import numpy as np

from controller.calibration import CalibrationData
from utils.config import AppConfig, ProcessingMode
from utils.performance import InferenceScheduler
from vision.pose_tracker import PoseTracker


class InferenceSchedulerTests(unittest.TestCase):
    def test_every_frame_processes_each_frame(self):
        scheduler = InferenceScheduler(ProcessingMode.EVERY_FRAME)
        self.assertEqual([scheduler.should_process() for _ in range(4)], [True, True, True, True])

    def test_every_two_frames_skips_alternating_frames(self):
        scheduler = InferenceScheduler(ProcessingMode.EVERY_2_FRAMES)
        self.assertEqual([scheduler.should_process() for _ in range(6)], [True, False, True, False, True, False])

    def test_every_three_frames_skips_two_between_inference(self):
        scheduler = InferenceScheduler(ProcessingMode.EVERY_3_FRAMES)
        self.assertEqual([scheduler.should_process() for _ in range(7)], [True, False, False, True, False, False, True])

    def test_auto_mode_uses_hysteresis(self):
        scheduler = InferenceScheduler(ProcessingMode.AUTO)
        for _ in range(3):
            scheduler.record_inference(19.0)
        self.assertEqual(scheduler.active_mode_name, "AUTO(2)")

        for _ in range(12):
            scheduler.record_inference(30.0)
        self.assertEqual(scheduler.active_mode_name, "AUTO(3)")

        for _ in range(8):
            scheduler.record_inference(9.0)
        self.assertEqual(scheduler.active_mode_name, "AUTO(2)")


class PoseTrackerPreparationTests(unittest.TestCase):
    def test_prepare_input_resizes_when_processing_dimensions_are_set(self):
        tracker = PoseTracker(AppConfig(processing_width=160, processing_height=120))
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        rgb = tracker.prepare_input(frame)

        self.assertEqual(rgb.shape, (120, 160, 3))

    def test_prepare_input_preserves_frame_size_by_default(self):
        tracker = PoseTracker(AppConfig())
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        rgb = tracker.prepare_input(frame)

        self.assertEqual(rgb.shape, (480, 640, 3))


class CalibrationDataTests(unittest.TestCase):
    def test_cached_calibration_values_are_populated(self):
        config = AppConfig()
        data = CalibrationData()
        data.shoulder_width = 0.2
        data.body_height = 0.5
        data.rest_hip_y = 0.6
        data.inverse_shoulder_width = 1.0 / data.shoulder_width
        data.jump_line_y = data.rest_hip_y - config.jump_line_offset * data.body_height
        data.effective_jump_line_y = data.jump_line_y - config.jump_dead_zone * data.body_height
        data.duck_line_y = data.rest_hip_y + config.duck_line_offset * data.body_height

        self.assertGreater(data.inverse_shoulder_width, 0.0)
        self.assertLess(data.jump_line_y, data.rest_hip_y)
        self.assertGreater(data.duck_line_y, data.rest_hip_y)


class ConfigDefaultTests(unittest.TestCase):
    def test_performance_defaults_preserve_current_behavior(self):
        config = AppConfig()

        self.assertEqual(config.processing_mode, ProcessingMode.AUTO)
        self.assertEqual(config.pose_model_complexity, 0)
        self.assertEqual(config.processing_width, 0)
        self.assertEqual(config.processing_height, 0)
        self.assertTrue(config.show_pose_overlay)
        self.assertTrue(config.show_sidebar)
        self.assertTrue(config.show_guides)
        self.assertTrue(config.show_hand_landmarks)


if __name__ == "__main__":
    unittest.main()
