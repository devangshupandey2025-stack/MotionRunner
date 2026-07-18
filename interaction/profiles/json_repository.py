from __future__ import annotations

import json
from pathlib import Path

from core.models.device import DeviceDescriptor, DeviceOrientation
from core.models.profile import (
    ActiveRegion,
    GameProfile,
    MappingMode,
    MappingSettings,
    VirtualJoystickSettings,
)
from core.ports.profile_repository import ProfileRepository


class JsonProfileRepository(ProfileRepository):
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def load_game_profile(self, game_id: str) -> GameProfile:
        path = self.root / "games" / f"{game_id}.json"
        data = self._load(path)
        mapping_data = data.get("mapping", {})
        joystick_data = data.get("joystick", {})
        profile = GameProfile(
            game_id=data.get("game_id", game_id),
            name=data.get("name", game_id),
            schema_version=int(data.get("schema_version", 1)),
            mapping=MappingSettings(
                mode=MappingMode[mapping_data.get("mode", "ABSOLUTE")],
                active_region=ActiveRegion(**mapping_data.get("active_region", {})),
                invert_x=bool(mapping_data.get("invert_x", False)),
                invert_y=bool(mapping_data.get("invert_y", False)),
                sensitivity_x=float(mapping_data.get("sensitivity_x", 1.0)),
                sensitivity_y=float(mapping_data.get("sensitivity_y", 1.0)),
                dead_zone=float(mapping_data.get("dead_zone", 0.0)),
                smoothing_alpha=float(mapping_data.get("smoothing_alpha", 0.35)),
                min_confidence=float(mapping_data.get("min_confidence", 0.5)),
            ),
            joystick=VirtualJoystickSettings(**joystick_data),
        )
        profile.validate()
        return profile

    def load_device_profile(self, device_id: str) -> DeviceDescriptor:
        path = self.root / "devices" / f"{device_id}.json"
        data = self._load(path)
        return DeviceDescriptor(
            device_id=data.get("device_id", device_id),
            name=data.get("name", device_id),
            width_px=int(data["width_px"]),
            height_px=int(data["height_px"]),
            orientation=DeviceOrientation[data.get("orientation", "PORTRAIT")],
            content_left=int(data.get("content_left", 0)),
            content_top=int(data.get("content_top", 0)),
            content_right=data.get("content_right"),
            content_bottom=data.get("content_bottom"),
        )

    def _load(self, path: Path) -> dict:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
