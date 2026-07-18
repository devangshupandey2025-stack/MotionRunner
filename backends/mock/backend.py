from __future__ import annotations

import time

from core.models.device import DeviceSession
from core.models.touch import TouchCommand, TouchCommandType
from core.ports.output_backend import BackendHealth, OutputBackend


class MockBackend(OutputBackend):
    name = "mock"

    def __init__(self):
        self.session: DeviceSession | None = None
        self.commands: list[TouchCommand] = []
        self._active: dict[int, TouchCommand] = {}
        self.connected = False

    def connect(self, session: DeviceSession) -> None:
        self.session = session
        self.connected = True
        session.connected = True

    def send(self, command: TouchCommand) -> None:
        if not self.connected:
            raise RuntimeError("MockBackend is not connected")
        self.commands.append(command)
        if command.type in (TouchCommandType.BEGIN, TouchCommandType.MOVE):
            self._active[command.pointer_id] = command
        elif command.is_terminal:
            self._active.pop(command.pointer_id, None)

    def cancel_all(self) -> None:
        now = time.perf_counter()
        for pointer_id, last in list(self._active.items()):
            self.commands.append(
                TouchCommand(
                    type=TouchCommandType.CANCEL,
                    pointer_id=pointer_id,
                    x=last.x,
                    y=last.y,
                    timestamp=now,
                    sequence=last.sequence + 1,
                    reason="backend_cancel_all",
                )
            )
            self._active.pop(pointer_id, None)

    def health(self) -> BackendHealth:
        return BackendHealth(healthy=self.connected, message="connected" if self.connected else "disconnected")
