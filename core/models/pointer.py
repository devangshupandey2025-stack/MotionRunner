from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PointerState:
    """Platform-neutral virtual pointer produced by vision."""

    x: float
    y: float
    contact: bool
    confidence: float
    timestamp: float
    sequence: int
    source_id: str = "primary"
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    tracking: bool = True

    def normalized(self) -> "PointerState":
        return PointerState(
            x=min(1.0, max(0.0, self.x)),
            y=min(1.0, max(0.0, self.y)),
            contact=self.contact,
            confidence=min(1.0, max(0.0, self.confidence)),
            timestamp=self.timestamp,
            sequence=self.sequence,
            source_id=self.source_id,
            velocity_x=self.velocity_x,
            velocity_y=self.velocity_y,
            tracking=self.tracking,
        )
