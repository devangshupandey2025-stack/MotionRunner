import unittest

from controller.action import Ability, Lane, PlayerState, Posture
from controller.action_executor import ActionExecutor
from controller.keyboard_events import KeyEventType
from utils.config import KeyMap, PlayerCommand


def state(lane=Lane.CENTER, posture=Posture.RUNNING, abilities=None):
    return PlayerState(
        lane=lane,
        posture=posture,
        abilities=set(abilities or []),
    )


class ActionExecutorTests(unittest.TestCase):
    def setUp(self):
        self.executor = ActionExecutor(KeyMap())

    def test_lane_transition_taps_once(self):
        self.executor.execute(state())
        events = self.executor.execute(state(lane=Lane.LEFT))
        repeated = self.executor.execute(state(lane=Lane.LEFT))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].command, PlayerCommand.LEFT)
        self.assertEqual(events[0].type, KeyEventType.TAP)
        self.assertEqual(repeated, [])

    def test_direct_lane_switch_taps_new_lane(self):
        self.executor.execute(state(lane=Lane.LEFT))
        events = self.executor.execute(state(lane=Lane.RIGHT))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].command, PlayerCommand.RIGHT)

    def test_return_to_center_emits_no_lane_event(self):
        self.executor.execute(state(lane=Lane.LEFT))
        events = self.executor.execute(state())

        self.assertEqual(events, [])

    def test_slide_hold_and_release(self):
        self.executor.execute(state())
        enter = self.executor.execute(state(posture=Posture.SLIDE))
        repeated = self.executor.execute(state(posture=Posture.SLIDE))
        exit_slide = self.executor.execute(state())

        self.assertEqual(enter[0].command, PlayerCommand.SLIDE)
        self.assertEqual(enter[0].type, KeyEventType.HOLD)
        self.assertEqual(repeated, [])
        self.assertEqual(exit_slide[0].command, PlayerCommand.SLIDE)
        self.assertEqual(exit_slide[0].type, KeyEventType.RELEASE)

    def test_slide_to_jump_releases_then_taps(self):
        self.executor.execute(state(posture=Posture.SLIDE))
        events = self.executor.execute(state(posture=Posture.JUMP))

        self.assertEqual([event.command for event in events], [PlayerCommand.SLIDE, PlayerCommand.JUMP])
        self.assertEqual([event.type for event in events], [KeyEventType.RELEASE, KeyEventType.TAP])

    def test_hoverboard_entry_taps_once(self):
        self.executor.execute(state())
        events = self.executor.execute(state(abilities={Ability.HOVERBOARD}))
        repeated = self.executor.execute(state(abilities={Ability.HOVERBOARD}))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].command, PlayerCommand.HOVERBOARD)
        self.assertEqual(events[0].type, KeyEventType.TAP)
        self.assertEqual(repeated, [])

    def test_simultaneous_transitions_are_ordered(self):
        self.executor.execute(state())
        events = self.executor.execute(state(
            lane=Lane.LEFT,
            posture=Posture.SLIDE,
            abilities={Ability.HOVERBOARD},
        ))

        self.assertEqual(
            [event.command for event in events],
            [PlayerCommand.LEFT, PlayerCommand.SLIDE, PlayerCommand.HOVERBOARD],
        )


if __name__ == "__main__":
    unittest.main()
