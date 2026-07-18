from __future__ import annotations

import time
from dataclasses import dataclass

from core.models.device import DeviceSession
from core.models.touch import TouchCommand
from core.ports.transport import Transport
from backends.android_touch.protocol import (
    PROTOCOL_VERSION,
    CompanionCapabilities,
    MessageType,
    ProtocolEnvelope,
    ProtocolError,
    make_envelope,
    touch_command_envelope,
)
from backends.android_touch.websocket_transport import WebSocketServerTransport


@dataclass(frozen=True)
class CompanionStatus:
    connected: bool
    ready: bool
    message: str
    latency_ms: float = 0.0


class CompanionClient:
    """Host protocol coordinator for a single Android companion session."""

    def __init__(self, transport: Transport | None = None, heartbeat_timeout_s: float = 5.0):
        self.transport = transport or WebSocketServerTransport()
        self.heartbeat_timeout_s = heartbeat_timeout_s
        self.session: DeviceSession | None = None
        self.capabilities: CompanionCapabilities | None = None
        self._next_sequence = 1
        self._pending: dict[int, float] = {}
        self._last_heartbeat_at = 0.0
        self._last_error = ""
        self._hello_received = False

    def connect(self, session: DeviceSession) -> None:
        self.session = session
        self.transport.start(self._on_message)

    def send_touch(self, command: TouchCommand) -> None:
        self._require_ready()
        envelope = touch_command_envelope(command, self._allocate_sequence())
        self._pending[envelope.sequence_number] = time.perf_counter()
        self.transport.send(envelope)

    def cancel_all(self) -> None:
        if self.ready:
            self._send(MessageType.TOUCH_COMMAND, {
                "commandType": "CANCEL_ALL",
                "pointerId": -1,
                "x": 0.0,
                "y": 0.0,
                "commandTimestamp": time.perf_counter(),
                "commandSequence": self._allocate_sequence(),
                "confidence": 1.0,
                "correlationId": "",
                "reason": "host_cancel_all",
            })

    def close(self) -> None:
        self.transport.close()
        if self.session is not None:
            self.session.connected = False
        self.capabilities = None

    @property
    def ready(self) -> bool:
        if self.capabilities is None or not self._hello_received:
            return False
        if not self.capabilities.accessibility_enabled:
            return False
        return self.transport.health().healthy and not self._heartbeat_expired()

    def status(self) -> CompanionStatus:
        transport_health = self.transport.health()
        if self._last_error:
            return CompanionStatus(False, False, self._last_error)
        if self.capabilities is not None and not self.capabilities.accessibility_enabled:
            return CompanionStatus(True, False, "Accessibility service is disabled")
        if self._heartbeat_expired():
            return CompanionStatus(False, False, "companion heartbeat timed out")
        return CompanionStatus(transport_health.healthy, self.ready, transport_health.message, self._mean_pending_latency())

    def _on_message(self, envelope: ProtocolEnvelope) -> None:
        try:
            if envelope.protocol_version != PROTOCOL_VERSION:
                raise ProtocolError(f"unsupported protocol version {envelope.protocol_version}")
            if envelope.message_type == MessageType.HELLO:
                self._hello_received = True
                self._last_heartbeat_at = time.perf_counter()
                self._send(
                    MessageType.HELLO,
                    {
                        "hostVersion": "0.1.0",
                        "supportedProtocolVersions": [PROTOCOL_VERSION],
                        "requestedDeviceId": self.session.descriptor.device_id if self.session else "",
                    },
                )
            elif envelope.message_type == MessageType.DEVICE_INFO:
                self._accept_capabilities(envelope)
            elif envelope.message_type == MessageType.ACK:
                acknowledged = int(envelope.payload["ackSequenceNumber"])
                self._pending.pop(acknowledged, None)
                self._last_heartbeat_at = time.perf_counter()
            elif envelope.message_type == MessageType.HEARTBEAT:
                self._last_heartbeat_at = time.perf_counter()
                self._send(MessageType.ACK, {"ackSequenceNumber": envelope.sequence_number})
            elif envelope.message_type == MessageType.ERROR:
                self._last_error = str(envelope.payload.get("message", "companion error"))
        except (KeyError, TypeError, ValueError, ProtocolError) as exc:
            self._last_error = str(exc)

    def _accept_capabilities(self, envelope: ProtocolEnvelope) -> None:
        if not self._hello_received:
            raise ProtocolError("DEVICE_INFO received before HELLO")
        capabilities = CompanionCapabilities.from_payload(envelope.payload)
        if PROTOCOL_VERSION not in capabilities.supported_protocol_versions:
            raise ProtocolError("companion does not support host protocol version")
        if "single_pointer" not in capabilities.supported_features:
            raise ProtocolError("companion does not support single_pointer touch")
        self.capabilities = capabilities
        self._last_heartbeat_at = time.perf_counter()
        if self.session is not None:
            self.session.connected = capabilities.accessibility_enabled
            self.session.metadata.update({
                "companion_version": capabilities.companion_version,
                "android_api_level": str(capabilities.android_api_level),
                "accessibility_enabled": str(capabilities.accessibility_enabled),
            })
        self._send(MessageType.ACK, {"ackSequenceNumber": envelope.sequence_number})

    def _send(self, message_type: MessageType, payload: dict) -> None:
        envelope = make_envelope(message_type, self._allocate_sequence(), payload)
        self.transport.send(envelope)

    def _allocate_sequence(self) -> int:
        sequence = self._next_sequence
        self._next_sequence += 1
        return sequence

    def _heartbeat_expired(self) -> bool:
        return self._last_heartbeat_at > 0 and (time.perf_counter() - self._last_heartbeat_at) > self.heartbeat_timeout_s

    def _require_ready(self) -> None:
        status = self.status()
        if not status.ready:
            raise RuntimeError(f"Android companion is not ready: {status.message}")

    def _mean_pending_latency(self) -> float:
        if not self._pending:
            return 0.0
        now = time.perf_counter()
        return sum((now - sent) * 1000 for sent in self._pending.values()) / len(self._pending)
