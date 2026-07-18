from __future__ import annotations

from core.ports.transport import MessageHandler, Transport, TransportHealth
from backends.android_touch.protocol import ProtocolEnvelope


class InMemoryTransport(Transport):
    """Deterministic transport retained for unit tests and local inspection."""

    def __init__(self):
        self.messages: list[ProtocolEnvelope] = []
        self._handler: MessageHandler | None = None
        self.started = False

    def start(self, on_message: MessageHandler) -> None:
        self._handler = on_message
        self.started = True

    def send(self, envelope: ProtocolEnvelope) -> None:
        if not self.started:
            raise RuntimeError("Transport has not been started")
        self.messages.append(envelope)

    def receive(self, envelope: ProtocolEnvelope) -> None:
        if self._handler is None:
            raise RuntimeError("Transport has not been started")
        self._handler(envelope)

    def close(self) -> None:
        self.started = False

    def health(self) -> TransportHealth:
        return TransportHealth(self.started, "in-memory transport")
