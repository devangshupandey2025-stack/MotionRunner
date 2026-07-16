import unittest

from controller.action import Ability, Lane
from utils.config import AppConfig
from vision.hand_provider import HandCalibrationData, HandGestureInterpreter, HandObservation


class HandProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = AppConfig(hand_dead_zone=0.15, hand_horizontal_range=0.2, hoverboard_hold_ms=500)
        self.interpreter = HandGestureInterpreter(self.config)
        self.calibration = HandCalibrationData(center_x=0.5)

    def test_open_palm_maps_to_left_lane(self):
        observation = HandObservation(
            palm_x=0.2,
            open_palm=True,
            pinch_active=False,
            confidence=1.0,
            landmarks=[],
            timestamp=1.0,
            frame_index=1,
        )

        state = self.interpreter.interpret(observation, self.calibration, calibrated=True)

        self.assertEqual(state.lane, Lane.LEFT)
        self.assertEqual(state.gesture_label, "OPEN_PALM")
        self.assertTrue(state.tracking)

    def test_pinch_hold_triggers_hoverboard(self):
        first = HandObservation(
            palm_x=0.5,
            open_palm=False,
            pinch_active=True,
            confidence=1.0,
            landmarks=[],
            timestamp=1.0,
            frame_index=1,
        )
        second = HandObservation(
            palm_x=0.5,
            open_palm=False,
            pinch_active=True,
            confidence=1.0,
            landmarks=[],
            timestamp=1.6,
            frame_index=2,
        )

        first_state = self.interpreter.interpret(first, self.calibration, calibrated=True)
        second_state = self.interpreter.interpret(second, self.calibration, calibrated=True)

        self.assertEqual(first_state.abilities, set())
        self.assertIn(Ability.HOVERBOARD, second_state.abilities)
        self.assertEqual(second_state.gesture_label, "PINCH")


if __name__ == "__main__":
    unittest.main()
