from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class MappingMode(Enum):
    ABSOLUTE = auto()
    VIRTUAL_JOYSTICK = auto()


@dataclass(frozen=True)
class ActiveRegion:
    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0

    def validate(self) -> None:
        if not 0.0 <= self.left < self.right <= 1.0:
            raise ValueError("ActiveRegion horizontal bounds must be within 0..1 and left < right")
        if not 0.0 <= self.top < self.bottom <= 1.0:
            raise ValueError("ActiveRegion vertical bounds must be within 0..1 and top < bottom")


@dataclass(frozen=True)
class MappingSettings:
    mode: MappingMode = MappingMode.ABSOLUTE
    active_region: ActiveRegion = ActiveRegion()
    invert_x: bool = False
    invert_y: bool = False
    sensitivity_x: float = 1.0
    sensitivity_y: float = 1.0
    dead_zone: float = 0.0
    smoothing_alpha: float = 0.35
    min_confidence: float = 0.5


@dataclass(frozen=True)
class VirtualJoystickSettings:
    center_x: float = 0.5
    center_y: float = 0.8
    radius: float = 0.15
    neutral_x: float = 0.5
    neutral_y: float = 0.5


@dataclass(frozen=True)
class GameProfile:
    game_id: str = "default"
    name: str = "Default"
    schema_version: int = 1
    mapping: MappingSettings = MappingSettings()
    joystick: VirtualJoystickSettings = VirtualJoystickSettings()

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ValueError(f"Unsupported GameProfile schema: {self.schema_version}")
        if not self.game_id:
            raise ValueError("GameProfile.game_id is required")
        self.mapping.active_region.validate()
        if self.mapping.sensitivity_x <= 0 or self.mapping.sensitivity_y <= 0:
            raise ValueError("Mapping sensitivity must be positive")
        if not 0.0 <= self.mapping.dead_zone < 1.0:
            raise ValueError("Mapping dead_zone must be in [0, 1)")
        if self.mapping.min_confidence < 0.0 or self.mapping.min_confidence > 1.0:
            raise ValueError("Mapping min_confidence must be within 0..1")
        if self.joystick.radius <= 0:
            raise ValueError("Virtual joystick radius must be positive")
