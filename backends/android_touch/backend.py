from __future__ import annotations

from core.models.device import DeviceSession
from core.models.touch import TouchCommand
from core.ports.output_backend import BackendHealth, OutputBackend
from core.ports.transport import Transport
from backends.android_touch.companion_client import CompanionClient


class AndroidTouchBackend(OutputBackend):
    name = "android_touch"

    def __init__(self, client: CompanionClient | None = None, transport: Transport | None = None):
        if client is not None and transport is not None:
            raise ValueError("Provide either client or transport, not both")
        self.client = client or CompanionClient(transport)
        self.session: DeviceSession | None = None

    def connect(self, session: DeviceSession) -> None:
        self.session = session
        self.client.connect(session)

    def send(self, command: TouchCommand) -> None:
        self.client.send_touch(command)

    def cancel_all(self) -> None:
        self.client.cancel_all()

    def health(self) -> BackendHealth:
        status = self.client.status()
        return BackendHealth(
            healthy=status.ready,
            message=status.message,
            latency_ms=status.latency_ms,
        )

    def close(self) -> None:
        self.client.close()
