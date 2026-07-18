from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TouchCommandType(Enum):
    BEGIN = auto()
    MOVE = auto()
    END = auto()
    CANCEL = auto()


@dataclass(frozen=True)
class TouchIntent:
    """Mapped desired touch state before transport-specific serialization."""

    x: float
    y: float
    contact: bool
    pointer_id: int
    timestamp: float
    sequence: int
    confidence: float = 1.0
    source_id: str = "primary"


@dataclass(frozen=True)
class TouchCommand:
    """Ordered touch command sent to an output backend."""

    type: TouchCommandType
    pointer_id: int
    x: float
    y: float
    timestamp: float
    sequence: int
    confidence: float = 1.0
    correlation_id: str = ""
    reason: str = ""

    @property
    def is_terminal(self) -> bool:
        return self.type in (TouchCommandType.END, TouchCommandType.CANCEL)
