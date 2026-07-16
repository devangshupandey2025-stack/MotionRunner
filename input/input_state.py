from dataclasses import dataclass, field

from controller.action import Ability, Lane, PlayerState, Posture


@dataclass
class InputState:
    provider_name: str
    tracking: bool = False
    calibrated: bool = False
    lane: Lane = Lane.CENTER
    posture: Posture = Posture.RUNNING
    abilities: set[Ability] = field(default_factory=set)
    lane_confidence: float = 0.0
    posture_confidence: float = 0.0
    ability_confidence: float = 0.0
    timestamp: float = 0.0
    frame_index: int = 0
    debug: str = ""
    gesture_label: str = ""
    landmarks: list[tuple[float, float]] = field(default_factory=list)

    def to_player_state(self) -> PlayerState:
        return PlayerState(
            lane=self.lane,
            posture=self.posture,
            abilities=set(self.abilities),
            lane_confidence=self.lane_confidence,
            posture_confidence=self.posture_confidence,
            ability_confidence=self.ability_confidence,
            timestamp=self.timestamp,
            frame_index=self.frame_index,
            debug=self.debug,
        )
