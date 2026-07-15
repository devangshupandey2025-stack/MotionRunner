from collections import deque
from typing import Iterable

from pynput.keyboard import Controller, Key

from controller.keyboard_events import KeyboardEvent, KeyEventType
from utils.config import AppConfig


class KeyboardController:
    def __init__(self, config: AppConfig):
        self.config = config
        self._keyboard = Controller()
        self._held_keys: dict[str, object] = {}
        self._held_labels: set[str] = set()
        self._history: deque[KeyboardEvent] = deque(maxlen=8)

    @property
    def held_labels(self) -> tuple[str, ...]:
        return tuple(sorted(self._held_labels))

    @property
    def event_history(self) -> tuple[KeyboardEvent, ...]:
        return tuple(self._history)

    @property
    def last_event(self) -> KeyboardEvent | None:
        return self._history[-1] if self._history else None

    def dispatch(self, events: Iterable[KeyboardEvent]):
        for event in events:
            key = self._parse_key(event.key)
            label = self._label(event.key)
            if event.type == KeyEventType.TAP:
                self._keyboard.press(key)
                self._keyboard.release(key)
                self._history.append(event)
            elif event.type == KeyEventType.HOLD:
                if label not in self._held_keys:
                    self._keyboard.press(key)
                    self._held_keys[label] = key
                    self._held_labels.add(label)
                    self._history.append(event)
            elif event.type == KeyEventType.RELEASE:
                held_key = self._held_keys.pop(label, None)
                if held_key is not None:
                    self._keyboard.release(held_key)
                    self._held_labels.discard(label)
                    self._history.append(event)

    def release_all(self):
        for label, key in list(self._held_keys.items()):
            self._keyboard.release(key)
            self._held_keys.pop(label, None)
            self._held_labels.discard(label)

    def shutdown(self):
        self.release_all()
        self._held_keys.clear()
        self._held_labels.clear()

    def _parse_key(self, key: str):
        special = {
            "left": Key.left,
            "right": Key.right,
            "up": Key.up,
            "down": Key.down,
            "space": Key.space,
        }
        return special.get(key.lower(), key)

    def _label(self, key: str) -> str:
        return key.upper()
