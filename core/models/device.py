from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class DeviceOrientation(Enum):
    PORTRAIT = auto()
    LANDSCAPE = auto()
    REVERSE_PORTRAIT = auto()
    REVERSE_LANDSCAPE = auto()


@dataclass(frozen=True)
class DeviceDescriptor:
    device_id: str
    name: str
    width_px: int
    height_px: int
    orientation: DeviceOrientation = DeviceOrientation.PORTRAIT
    content_left: int = 0
    content_top: int = 0
    content_right: int | None = None
    content_bottom: int | None = None

    @property
    def content_width(self) -> int:
        right = self.content_right if self.content_right is not None else self.width_px
        return max(0, right - self.content_left)

    @property
    def content_height(self) -> int:
        bottom = self.content_bottom if self.content_bottom is not None else self.height_px
        return max(0, bottom - self.content_top)


@dataclass
class DeviceSession:
    descriptor: DeviceDescriptor
    backend_name: str
    connected: bool = False
    metadata: dict[str, str] = field(default_factory=dict)
