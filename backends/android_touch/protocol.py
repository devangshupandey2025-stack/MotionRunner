from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from core.models.device import DeviceDescriptor, DeviceOrientation
from core.models.touch import TouchCommand, TouchCommandType


PROTOCOL_VERSION = 1


class MessageType(str, Enum):
    HELLO = "HELLO"
    DEVICE_INFO = "DEVICE_INFO"
    TOUCH_COMMAND = "TOUCH_COMMAND"
    ACK = "ACK"
    HEARTBEAT = "HEARTBEAT"
    ERROR = "ERROR"


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class ProtocolEnvelope:
    protocol_version: int
    message_type: MessageType
    sequence_number: int
    timestamp: float
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocolVersion": self.protocol_version,
            "messageType": self.message_type.value,
            "sequenceNumber": self.sequence_number,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProtocolEnvelope":
        required = {"protocolVersion", "messageType", "sequenceNumber", "timestamp", "payload"}
        missing = required.difference(raw)
        if missing:
            raise ProtocolError(f"missing required fields: {', '.join(sorted(missing))}")
        try:
            version = int(raw["protocolVersion"])
            message_type = MessageType(raw["messageType"])
            sequence = int(raw["sequenceNumber"])
            timestamp = float(raw["timestamp"])
        except (TypeError, ValueError) as exc:
            raise ProtocolError(f"invalid envelope fields: {exc}") from exc
        if version < 1:
            raise ProtocolError("protocolVersion must be positive")
        if sequence < 0:
            raise ProtocolError("sequenceNumber must be non-negative")
        if not isinstance(raw["payload"], dict):
            raise ProtocolError("payload must be an object")
        return cls(version, message_type, sequence, timestamp, raw["payload"])


@dataclass(frozen=True)
class CompanionCapabilities:
    companion_version: str
    supported_protocol_versions: tuple[int, ...]
    android_api_level: int
    width_px: int
    height_px: int
    density: float
    orientation: DeviceOrientation
    accessibility_enabled: bool
    supported_features: tuple[str, ...]
    gesture_limitations: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CompanionCapabilities":
        try:
            orientation = DeviceOrientation[str(payload["orientation"])]
            versions = tuple(int(value) for value in payload["supportedProtocolVersions"])
            features = tuple(str(value) for value in payload.get("supportedFeatures", ()))
            limitations = tuple(str(value) for value in payload.get("gestureLimitations", ()))
            instance = cls(
                companion_version=str(payload["companionVersion"]),
                supported_protocol_versions=versions,
                android_api_level=int(payload["androidApiLevel"]),
                width_px=int(payload["widthPx"]),
                height_px=int(payload["heightPx"]),
                density=float(payload["density"]),
                orientation=orientation,
                accessibility_enabled=bool(payload["accessibilityEnabled"]),
                supported_features=features,
                gesture_limitations=limitations,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ProtocolError(f"invalid DEVICE_INFO payload: {exc}") from exc
        if instance.width_px <= 0 or instance.height_px <= 0 or instance.density <= 0:
            raise ProtocolError("device dimensions and density must be positive")
        return instance

    def to_descriptor(self, device_id: str, name: str) -> DeviceDescriptor:
        return DeviceDescriptor(
            device_id=device_id,
            name=name,
            width_px=self.width_px,
            height_px=self.height_px,
            orientation=self.orientation,
        )


def make_envelope(message_type: MessageType, sequence_number: int, payload: dict[str, Any]) -> ProtocolEnvelope:
    return ProtocolEnvelope(PROTOCOL_VERSION, message_type, sequence_number, time.perf_counter(), payload)


def touch_command_envelope(command: TouchCommand, sequence_number: int) -> ProtocolEnvelope:
    return make_envelope(
        MessageType.TOUCH_COMMAND,
        sequence_number,
        {
            "commandType": command.type.name,
            "pointerId": command.pointer_id,
            "x": command.x,
            "y": command.y,
            "commandTimestamp": command.timestamp,
            "commandSequence": command.sequence,
            "confidence": command.confidence,
            "correlationId": command.correlation_id,
            "reason": command.reason,
        },
    )


def command_from_payload(payload: dict[str, Any]) -> TouchCommand:
    try:
        return TouchCommand(
            type=TouchCommandType[str(payload["commandType"])],
            pointer_id=int(payload["pointerId"]),
            x=float(payload["x"]),
            y=float(payload["y"]),
            timestamp=float(payload["commandTimestamp"]),
            sequence=int(payload["commandSequence"]),
            confidence=float(payload.get("confidence", 1.0)),
            correlation_id=str(payload.get("correlationId", "")),
            reason=str(payload.get("reason", "")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProtocolError(f"invalid TOUCH_COMMAND payload: {exc}") from exc
