import time


class CooldownManager:
    def __init__(self, cooldowns: dict):
        self._cooldowns = cooldowns
        self._last_triggered: dict[str, float] = {}

    def can_trigger(self, action: str) -> bool:
        if action not in self._cooldowns:
            return True
        last = self._last_triggered.get(action, 0.0)
        elapsed = (time.perf_counter() - last) * 1000
        return elapsed >= self._cooldowns[action]

    def trigger(self, action: str):
        self._last_triggered[action] = time.perf_counter()

    def remaining_ms(self, action: str) -> float:
        if action not in self._cooldowns:
            return 0.0
        last = self._last_triggered.get(action, 0.0)
        elapsed = (time.perf_counter() - last) * 1000
        remaining = self._cooldowns[action] - elapsed
        return max(0.0, remaining)
