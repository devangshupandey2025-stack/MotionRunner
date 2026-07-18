from __future__ import annotations

from dataclasses import dataclass

from core.models.pointer import PointerState


@dataclass(frozen=True)
class PointerFilterSettings:
    smoothing_alpha: float = 0.35
    min_confidence: float = 0.5
    tracking_timeout_s: float = 0.15


class PointerFilter:
    """Applies confidence gating, smoothing, and loss-to-release behavior."""

    def __init__(self, settings: PointerFilterSettings | None = None):
        self.settings = settings or PointerFilterSettings()
        self._last: PointerState | None = None
        self._last_tracking_timestamp: float | None = None

    def reset(self) -> None:
        self._last = None
        self._last_tracking_timestamp = None

    def process(self, pointer: PointerState) -> PointerState:
        alpha = min(1.0, max(0.0, self.settings.smoothing_alpha))
        confident = pointer.tracking and pointer.confidence >= self.settings.min_confidence

        if confident:
            self._last_tracking_timestamp = pointer.timestamp

        timed_out = (
            self._last_tracking_timestamp is not None
            and pointer.timestamp - self._last_tracking_timestamp > self.settings.tracking_timeout_s
        )

        if self._last is None or not confident:
            filtered = PointerState(
                x=pointer.x if confident else (self._last.x if self._last else pointer.x),
                y=pointer.y if confident else (self._last.y if self._last else pointer.y),
                contact=pointer.contact and confident and not timed_out,
                confidence=pointer.confidence if confident else 0.0,
                timestamp=pointer.timestamp,
                sequence=pointer.sequence,
                source_id=pointer.source_id,
                velocity_x=pointer.velocity_x if confident else 0.0,
                velocity_y=pointer.velocity_y if confident else 0.0,
                tracking=confident and not timed_out,
            ).normalized()
            self._last = filtered
            return filtered

        x = self._last.x + alpha * (pointer.x - self._last.x)
        y = self._last.y + alpha * (pointer.y - self._last.y)
        filtered = PointerState(
            x=x,
            y=y,
            contact=pointer.contact and not timed_out,
            confidence=pointer.confidence,
            timestamp=pointer.timestamp,
            sequence=pointer.sequence,
            source_id=pointer.source_id,
            velocity_x=pointer.velocity_x,
            velocity_y=pointer.velocity_y,
            tracking=not timed_out,
        ).normalized()
        self._last = filtered
        return filtered
