import time

from controller.action import Ability, Lane, PlayerState, Posture
from controller.keyboard_events import KeyboardEvent, KeyEventType
from utils.config import KeyMap, PlayerCommand


class LaneExecutor:
    def __init__(self, keymap: KeyMap):
        self.keymap = keymap

    def execute(self, previous: PlayerState | None, current: PlayerState) -> list[KeyboardEvent]:
        if previous is None or previous.lane == current.lane or current.lane == Lane.CENTER:
            return []

        if current.lane == Lane.LEFT:
            return [self._tap(PlayerCommand.LEFT, "Lane LEFT")]
        if current.lane == Lane.RIGHT:
            return [self._tap(PlayerCommand.RIGHT, "Lane RIGHT")]
        return []

    def _tap(self, command: PlayerCommand, reason: str) -> KeyboardEvent:
        return KeyboardEvent(
            timestamp=time.perf_counter(),
            command=command,
            key=self.keymap.bindings[command],
            type=KeyEventType.TAP,
            reason=reason,
        )


class PostureExecutor:
    def __init__(self, keymap: KeyMap):
        self.keymap = keymap

    def execute(self, previous: PlayerState | None, current: PlayerState) -> list[KeyboardEvent]:
        if previous is None or previous.posture == current.posture:
            return []

        events: list[KeyboardEvent] = []
        if previous.posture == Posture.SLIDE and current.posture != Posture.SLIDE:
            events.append(self._event(PlayerCommand.SLIDE, KeyEventType.RELEASE, "Slide release"))

        if current.posture == Posture.JUMP:
            events.append(self._event(PlayerCommand.JUMP, KeyEventType.TAP, "Posture JUMP"))
        elif current.posture == Posture.SLIDE:
            events.append(self._event(PlayerCommand.SLIDE, KeyEventType.HOLD, "Posture SLIDE"))

        return events

    def _event(self, command: PlayerCommand, event_type: KeyEventType, reason: str) -> KeyboardEvent:
        return KeyboardEvent(
            timestamp=time.perf_counter(),
            command=command,
            key=self.keymap.bindings[command],
            type=event_type,
            reason=reason,
        )


class AbilityExecutor:
    def __init__(self, keymap: KeyMap):
        self.keymap = keymap

    def execute(self, previous: PlayerState | None, current: PlayerState) -> list[KeyboardEvent]:
        previous_abilities = previous.abilities if previous else set()
        if Ability.HOVERBOARD in current.abilities and Ability.HOVERBOARD not in previous_abilities:
            return [KeyboardEvent(
                timestamp=time.perf_counter(),
                command=PlayerCommand.HOVERBOARD,
                key=self.keymap.bindings[PlayerCommand.HOVERBOARD],
                type=KeyEventType.TAP,
                reason="Ability HOVERBOARD",
            )]
        return []


class ActionExecutor:
    def __init__(self, keymap: KeyMap):
        self.lane = LaneExecutor(keymap)
        self.posture = PostureExecutor(keymap)
        self.ability = AbilityExecutor(keymap)
        self._previous: PlayerState | None = None

    def execute(self, current: PlayerState) -> list[KeyboardEvent]:
        events = [
            *self.lane.execute(self._previous, current),
            *self.posture.execute(self._previous, current),
            *self.ability.execute(self._previous, current),
        ]
        self._previous = current
        return events

    def reset(self):
        self._previous = None
