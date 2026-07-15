from dataclasses import dataclass, field
from enum import Enum, auto


class Action(Enum):
    RUNNING = auto()
    LEFT = auto()
    RIGHT = auto()
    JUMP = auto()
    SLIDE = auto()
    HOVERBOARD = auto()

    @property
    def key(self) -> str | None:
        mapping = {
            Action.RUNNING: None,
            Action.LEFT: "left",
            Action.RIGHT: "right",
            Action.JUMP: "up",
            Action.SLIDE: "down",
            Action.HOVERBOARD: "space",
        }
        return mapping[self]

    @property
    def hold(self) -> bool:
        return self == Action.SLIDE


class Lane(Enum):
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()


class Posture(Enum):
    RUNNING = auto()
    JUMP = auto()
    SLIDE = auto()


class Ability(Enum):
    HOVERBOARD = auto()


@dataclass
class LaneResult:
    direction: Lane
    confidence: float
    offset: float


@dataclass
class JumpResult:
    active: bool
    confidence: float
    velocity: float = 0.0
    above_line: bool = False
    above_effective_line: bool = False
    moving_upward: bool = False
    elapsed_ms: float = 0.0
    debug: str = ""


@dataclass
class SlideResult:
    active: bool
    confidence: float
    height_ratio: float = 1.0
    knee_angle: float = 180.0
    crossed_duck: bool = False
    state: str = "STANDING"
    elapsed_ms: float = 0.0
    is_squatting: bool = False
    is_standing: bool = True
    debug: str = ""


@dataclass
class HoverboardResult:
    active: bool
    confidence: float
    hands_up: bool = False
    elapsed_ms: float = 0.0
    debug: str = ""


@dataclass
class PlayerState:
    lane: Lane
    posture: Posture
    abilities: set[Ability] = field(default_factory=set)
    lane_confidence: float = 0.0
    posture_confidence: float = 0.0
    ability_confidence: float = 0.0
    timestamp: float = 0.0
    frame_index: int = 0
    lane_result: LaneResult | None = None
    jump_result: JumpResult | None = None
    slide_result: SlideResult | None = None
    hoverboard_result: HoverboardResult | None = None
    debug: str = ""

    @property
    def primary_action(self) -> Action:
        # Transitional compatibility only.
        # New code should consume PlayerState directly.
        if self.posture == Posture.SLIDE:
            return Action.SLIDE
        if self.posture == Posture.JUMP:
            return Action.JUMP
        if Ability.HOVERBOARD in self.abilities:
            return Action.HOVERBOARD
        if self.lane == Lane.LEFT:
            return Action.LEFT
        if self.lane == Lane.RIGHT:
            return Action.RIGHT
        return Action.RUNNING
