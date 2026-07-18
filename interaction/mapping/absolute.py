from __future__ import annotations

from core.models.device import DeviceDescriptor
from core.models.pointer import PointerState
from core.models.profile import GameProfile
from core.models.touch import TouchIntent
from interaction.mapping.common import apply_axis_settings, contact_allowed


class AbsoluteMapper:
    name = "absolute"

    def map(self, pointer: PointerState, profile: GameProfile, device: DeviceDescriptor, pointer_id: int = 0) -> TouchIntent:
        profile.validate()
        settings = profile.mapping
        region = settings.active_region

        x = apply_axis_settings(pointer.x, invert=settings.invert_x, sensitivity=settings.sensitivity_x)
        y = apply_axis_settings(pointer.y, invert=settings.invert_y, sensitivity=settings.sensitivity_y)
        mapped_x = region.left + x * (region.right - region.left)
        mapped_y = region.top + y * (region.bottom - region.top)

        return TouchIntent(
            x=device.content_left + mapped_x * device.content_width,
            y=device.content_top + mapped_y * device.content_height,
            contact=contact_allowed(pointer, settings),
            pointer_id=pointer_id,
            timestamp=pointer.timestamp,
            sequence=pointer.sequence,
            confidence=pointer.confidence,
            source_id=pointer.source_id,
        )
