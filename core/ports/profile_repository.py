from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.device import DeviceDescriptor
from core.models.profile import GameProfile


class ProfileRepository(ABC):
    @abstractmethod
    def load_game_profile(self, game_id: str) -> GameProfile:
        raise NotImplementedError

    @abstractmethod
    def load_device_profile(self, device_id: str) -> DeviceDescriptor:
        raise NotImplementedError
