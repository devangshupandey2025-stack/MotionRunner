from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from backends.android_touch.protocol import ProtocolEnvelope


@dataclass(frozen=True)
class TransportHealth:
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0


MessageHandler = Callable[["ProtocolEnvelope"], None]


class Transport(ABC):
    """Bidirectional transport for the Android companion protocol.

    Domain code deals exclusively in protocol envelopes; concrete transports own
    sockets, reconnects, framing, and their respective lifecycle.
    """

    @abstractmethod
    def start(self, on_message: MessageHandler) -> None:
        raise NotImplementedError

    @abstractmethod
    def send(self, envelope: "ProtocolEnvelope") -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> TransportHealth:
        raise NotImplementedError
