from __future__ import annotations

from typing import Iterable

from core.models.touch import TouchCommand
from core.ports.output_backend import OutputBackend


def replay_commands(commands: Iterable[TouchCommand], backend: OutputBackend) -> int:
    """Replay an already-recorded command stream without camera or MediaPipe."""
    count = 0
    for command in commands:
        backend.send(command)
        count += 1
    return count
