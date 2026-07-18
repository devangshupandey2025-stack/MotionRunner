from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from core.models.pointer import PointerState
from core.ports.pointer_provider import PointerProvider


@dataclass(frozen=True)
class HandPointerSettings:
    min_confidence: float = 0.5
    mirror_x: bool = False
    source_id: str = "hand.primary"


class HandPointerProvider(PointerProvider):
    """Converts hand observations into a continuous virtual finger."""

    name = "hand_pointer"

    def __init__(self, settings: HandPointerSettings | None = None):
        self.settings = settings or HandPointerSettings()
        self._sequence = 0
        self._last: PointerState | None = None

    def reset(self) -> None:
        self._sequence = 0
        self._last = None

    def sample(self, observation: Any | None) -> PointerState:
        self._sequence += 1
        timestamp = time.perf_counter()

        if observation is None:
            pointer = PointerState(
                x=self._last.x if self._last else 0.5,
                y=self._last.y if self._last else 0.5,
                contact=False,
                confidence=0.0,
                timestamp=timestamp,
                sequence=self._sequence,
                source_id=self.settings.source_id,
                tracking=False,
            )
            self._last = pointer
            return pointer

        x, y = self._palm_center(observation)
        if self.settings.mirror_x:
            x = 1.0 - x

        obs_timestamp = getattr(observation, "timestamp", timestamp)
        confidence = float(getattr(observation, "confidence", 1.0))
        tracking = confidence >= self.settings.min_confidence
        contact = bool(getattr(observation, "pinch_active", False)) and tracking

        velocity_x = 0.0
        velocity_y = 0.0
        if self._last is not None:
            dt = max(1e-6, obs_timestamp - self._last.timestamp)
            velocity_x = (x - self._last.x) / dt
            velocity_y = (y - self._last.y) / dt

        pointer = PointerState(
            x=x,
            y=y,
            contact=contact,
            confidence=confidence,
            timestamp=obs_timestamp,
            sequence=self._sequence,
            source_id=self.settings.source_id,
            velocity_x=velocity_x,
            velocity_y=velocity_y,
            tracking=tracking,
        ).normalized()
        self._last = pointer
        return pointer

    def _palm_center(self, observation: Any) -> tuple[float, float]:
        landmarks = list(getattr(observation, "landmarks", []) or [])
        if landmarks:
            palm_indices = (0, 5, 9, 13, 17)
            selected = [landmarks[index] for index in palm_indices if index < len(landmarks)]
            if selected:
                return (
                    sum(point[0] for point in selected) / len(selected),
                    sum(point[1] for point in selected) / len(selected),
                )
        return float(getattr(observation, "palm_x", 0.5)), float(getattr(observation, "palm_y", 0.5))
