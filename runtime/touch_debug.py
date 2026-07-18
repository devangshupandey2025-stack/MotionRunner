from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.models.touch import TouchCommand


@dataclass(frozen=True)
class TouchTracePoint:
    pointer_id: int
    x: float
    y: float
    command_type: str
    sequence: int
    timestamp: float


def build_touch_trace(commands: Iterable[TouchCommand]) -> list[TouchTracePoint]:
    """Backend-independent data source for an OpenCV/UI touch debug overlay."""
    return [
        TouchTracePoint(
            pointer_id=command.pointer_id,
            x=command.x,
            y=command.y,
            command_type=command.type.name,
            sequence=command.sequence,
            timestamp=command.timestamp,
        )
        for command in commands
    ]
