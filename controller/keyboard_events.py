from dataclasses import dataclass
from enum import Enum, auto

from utils.config import PlayerCommand


class KeyEventType(Enum):
    TAP = auto()
    HOLD = auto()
    RELEASE = auto()


@dataclass(frozen=True)
class KeyboardEvent:
    timestamp: float
    command: PlayerCommand
    key: str
    type: KeyEventType
    reason: str
