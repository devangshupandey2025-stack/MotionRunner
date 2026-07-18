from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from core.models.device import DeviceSession
from core.models.touch import TouchCommand


@dataclass(frozen=True)
class BackendHealth:
    healthy: bool
    message: str = ""
    latency_ms: float = 0.0


class OutputBackend(ABC):
    name: str

    @abstractmethod
    def connect(self, session: DeviceSession) -> None:
        raise NotImplementedError

    @abstractmethod
    def send(self, command: TouchCommand) -> None:
        raise NotImplementedError

    @abstractmethod
    def cancel_all(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def health(self) -> BackendHealth:
        raise NotImplementedError
