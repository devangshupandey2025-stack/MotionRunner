from __future__ import annotations

from dataclasses import dataclass

from core.models.touch import TouchCommand, TouchCommandType, TouchIntent


@dataclass
class TouchState:
    active: bool = False
    last_sequence: int = -1
    last_x: float = 0.0
    last_y: float = 0.0


class TouchStateMachine:
    """Serializes touch intents into valid ordered touch commands."""

    def __init__(self):
        self._states: dict[int, TouchState] = {}

    def reset(self) -> None:
        self._states.clear()

    def apply(self, intent: TouchIntent) -> list[TouchCommand]:
        state = self._states.setdefault(intent.pointer_id, TouchState())
        if intent.sequence <= state.last_sequence:
            return []

        state.last_sequence = intent.sequence
        if intent.contact:
            command_type = TouchCommandType.MOVE if state.active else TouchCommandType.BEGIN
            state.active = True
            state.last_x = intent.x
            state.last_y = intent.y
            return [self._command(command_type, intent)]

        if state.active:
            state.active = False
            state.last_x = intent.x
            state.last_y = intent.y
            return [self._command(TouchCommandType.END, intent)]

        state.last_x = intent.x
        state.last_y = intent.y
        return []

    def cancel_all(self, *, timestamp: float, sequence: int, reason: str = "cancel_all") -> list[TouchCommand]:
        commands: list[TouchCommand] = []
        for pointer_id, state in self._states.items():
            if not state.active:
                continue
            state.active = False
            state.last_sequence = max(state.last_sequence, sequence)
            commands.append(
                TouchCommand(
                    type=TouchCommandType.CANCEL,
                    pointer_id=pointer_id,
                    x=state.last_x,
                    y=state.last_y,
                    timestamp=timestamp,
                    sequence=sequence,
                    reason=reason,
                )
            )
        return commands

    def _command(self, command_type: TouchCommandType, intent: TouchIntent) -> TouchCommand:
        return TouchCommand(
            type=command_type,
            pointer_id=intent.pointer_id,
            x=intent.x,
            y=intent.y,
            timestamp=intent.timestamp,
            sequence=intent.sequence,
            confidence=intent.confidence,
            correlation_id=f"{intent.source_id}:{intent.sequence}",
        )
