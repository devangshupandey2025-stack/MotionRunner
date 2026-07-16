import unittest

from controller.action import Ability, Lane, PlayerState, Posture
from input.adapters import player_state_to_input_state


class InputAdapterTests(unittest.TestCase):
    def test_player_state_round_trip_preserves_keyboard_semantics(self):
        player_state = PlayerState(
            lane=Lane.LEFT,
            posture=Posture.SLIDE,
            abilities={Ability.HOVERBOARD},
            lane_confidence=0.9,
            posture_confidence=0.8,
            ability_confidence=1.0,
            timestamp=12.0,
            frame_index=34,
            debug="debug",
        )

        input_state = player_state_to_input_state(
            player_state,
            provider_name="pose",
            tracking=True,
            calibrated=True,
            gesture_label="SLIDE",
        )

        self.assertEqual(input_state.to_player_state(), player_state)
        self.assertEqual(input_state.provider_name, "pose")
        self.assertEqual(input_state.gesture_label, "SLIDE")


if __name__ == "__main__":
    unittest.main()
