from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from backends.android_touch import AndroidTouchBackend, WebSocketServerTransport
from backends.mock import MockBackend
from backends.recording import RecordingBackend
from core.ports.output_backend import OutputBackend


class TouchOutputMode(str, Enum):
    MOCK = "mock"
    RECORDING = "recording"
    ANDROID_COMPANION = "android_companion"


@dataclass(frozen=True)
class TouchOutputConfig:
    mode: TouchOutputMode = TouchOutputMode.MOCK
    host: str = "127.0.0.1"
    port: int = 8765
    recording_path: Path | None = None


def create_touch_backend(config: TouchOutputConfig) -> OutputBackend:
    """Explicitly select the touch output without coupling the pipeline to it."""
    if config.mode == TouchOutputMode.MOCK:
        return MockBackend()
    if config.mode == TouchOutputMode.RECORDING:
        return RecordingBackend(config.recording_path)
    if config.mode == TouchOutputMode.ANDROID_COMPANION:
        return AndroidTouchBackend(transport=WebSocketServerTransport(config.host, config.port))
    raise ValueError(f"Unsupported touch output mode: {config.mode}")
