from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.models.pointer import PointerState


class PointerProvider(ABC):
    name: str

    @abstractmethod
    def sample(self, observation: Any | None) -> PointerState:
        raise NotImplementedError
