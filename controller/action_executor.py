import time

from controller.action import Ability, Lane, PlayerState, Posture
from controller.keyboard_events import KeyboardEvent, KeyEventType
from utils.config import KeyMap, PlayerCommand


class LaneExecutor:
    def __init__(self, keymap: KeyMap):
        self.keymap = keymap

    def execute(self, previous_game_lane: int, desired_game_lane: int) -> list[KeyboardEvent]:
        if previous_game_lane == desired_game_lane:
            return []

        events = []
        difference = desired_game_lane - previous_game_lane
        
        if difference < 0:
            # Move left
            for _ in range(abs(difference)):
                events.append(self._tap(PlayerCommand.LEFT, f"Lane {previous_game_lane} -> {desired_game_lane}"))
        elif difference > 0:
            # Move right
            for _ in range(difference):
                events.append(self._tap(PlayerCommand.RIGHT, f"Lane {previous_game_lane} -> {desired_game_lane}"))
                
        return events

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
        """Compatibility API for the legacy desktop keyboard backend."""

        events: list[KeyboardEvent] = []
        if self._previous is not None and self._previous.lane != current.lane:
            if current.lane == Lane.LEFT:
                events.append(self.lane._tap(PlayerCommand.LEFT, "Lane LEFT"))
            elif current.lane == Lane.RIGHT:
                events.append(self.lane._tap(PlayerCommand.RIGHT, "Lane RIGHT"))

        events.extend(self.posture.execute(self._previous, current))
        events.extend(self.ability.execute(self._previous, current))
        self._previous = current
        return events

    def execute_posture_ability(self, current: PlayerState) -> list[KeyboardEvent]:
        events = [
            *self.posture.execute(self._previous, current),
            *self.ability.execute(self._previous, current),
        ]
        self._previous = current
        return events

    def execute_lane(self, previous_game_lane: int, desired_game_lane: int) -> list[KeyboardEvent]:
        return self.lane.execute(previous_game_lane, desired_game_lane)

    def reset(self):
        self._previous = None
