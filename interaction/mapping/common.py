from __future__ import annotations

from core.models.pointer import PointerState
from core.models.profile import MappingSettings


def apply_axis_settings(value: float, *, invert: bool, sensitivity: float) -> float:
    centered = value - 0.5
    scaled = centered * sensitivity
    adjusted = 0.5 + scaled
    if invert:
        adjusted = 1.0 - adjusted
    return min(1.0, max(0.0, adjusted))


def contact_allowed(pointer: PointerState, settings: MappingSettings) -> bool:
    return pointer.contact and pointer.tracking and pointer.confidence >= settings.min_confidence
