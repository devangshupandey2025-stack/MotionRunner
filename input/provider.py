from abc import ABC, abstractmethod

from input.input_state import InputState
from utils.performance import ProviderPerfStats


class InputProvider(ABC):
    name: str

    def __init__(self):
        self.current_pose = None
        self.hand_landmarks: tuple[tuple[float, float], ...] = ()
        self.calibrator = None
        self.perf_stats = ProviderPerfStats()

    @abstractmethod
    def reset(self):
        raise NotImplementedError

    @abstractmethod
    def update(self, frame) -> InputState:
        raise NotImplementedError
