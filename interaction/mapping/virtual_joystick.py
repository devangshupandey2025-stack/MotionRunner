from __future__ import annotations

import math

from core.models.device import DeviceDescriptor
from core.models.pointer import PointerState
from core.models.profile import GameProfile
from core.models.touch import TouchIntent
from interaction.mapping.common import contact_allowed


class VirtualJoystickMapper:
    name = "virtual_joystick"

    def map(self, pointer: PointerState, profile: GameProfile, device: DeviceDescriptor, pointer_id: int = 0) -> TouchIntent:
        profile.validate()
        settings = profile.mapping
        joystick = profile.joystick

        dx = (pointer.x - joystick.neutral_x) * settings.sensitivity_x
        dy = (pointer.y - joystick.neutral_y) * settings.sensitivity_y
        if settings.invert_x:
            dx = -dx
        if settings.invert_y:
            dy = -dy

        magnitude = math.hypot(dx, dy)
        if magnitude < settings.dead_zone:
            dx = 0.0
            dy = 0.0
        elif magnitude > 1.0:
            dx /= magnitude
            dy /= magnitude

        x = joystick.center_x + dx * joystick.radius
        y = joystick.center_y + dy * joystick.radius
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))

        return TouchIntent(
            x=device.content_left + x * device.content_width,
            y=device.content_top + y * device.content_height,
            contact=contact_allowed(pointer, settings),
            pointer_id=pointer_id,
            timestamp=pointer.timestamp,
            sequence=pointer.sequence,
            confidence=pointer.confidence,
            source_id=pointer.source_id,
        )
