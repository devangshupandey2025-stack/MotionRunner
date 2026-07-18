from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from core.models.device import DeviceSession
from core.models.touch import TouchCommand, TouchCommandType
from core.ports.output_backend import BackendHealth, OutputBackend


class RecordingBackend(OutputBackend):
    name = "recording"

    def __init__(self, output_path: str | Path | None = None):
        self.output_path = Path(output_path) if output_path is not None else None
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
            raise RuntimeError("RecordingBackend is not connected")
        self.commands.append(command)
        if command.type in (TouchCommandType.BEGIN, TouchCommandType.MOVE):
            self._active[command.pointer_id] = command
        elif command.is_terminal:
            self._active.pop(command.pointer_id, None)

    def cancel_all(self) -> None:
        now = time.perf_counter()
        for pointer_id, last in list(self._active.items()):
            self.send(
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

    def flush(self) -> None:
        if self.output_path is None:
            return
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for command in self.commands:
            row = asdict(command)
            row["type"] = command.type.name
            rows.append(row)
        self.output_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    @staticmethod
    def load_commands(input_path: str | Path) -> list[TouchCommand]:
        """Load a recording without coupling replay tooling to a backend instance."""
        rows = json.loads(Path(input_path).read_text(encoding="utf-8"))
        return [
            TouchCommand(
                type=TouchCommandType[row["type"]],
                pointer_id=int(row["pointer_id"]),
                x=float(row["x"]),
                y=float(row["y"]),
                timestamp=float(row["timestamp"]),
                sequence=int(row["sequence"]),
                confidence=float(row.get("confidence", 1.0)),
                correlation_id=str(row.get("correlation_id", "")),
                reason=str(row.get("reason", "")),
            )
            for row in rows
        ]

    def health(self) -> BackendHealth:
        return BackendHealth(healthy=self.connected, message=f"{len(self.commands)} commands recorded")
