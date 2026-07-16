from controller.action import Ability, Lane, Posture
from input.input_state import InputState
from input.provider import InputProvider


class KeyboardProvider(InputProvider):
    name = "keyboard"

    def __init__(self):
        super().__init__()
        self._state = InputState(provider_name=self.name, tracking=True, calibrated=True)

    def inject(
        self,
        *,
        lane: Lane = Lane.CENTER,
        posture: Posture = Posture.RUNNING,
        hoverboard: bool = False,
        debug: str = "Keyboard provider",
    ):
        abilities = {Ability.HOVERBOARD} if hoverboard else set()
        self._state = InputState(
            provider_name=self.name,
            tracking=True,
            calibrated=True,
            lane=lane,
            posture=posture,
            abilities=abilities,
            lane_confidence=1.0,
            posture_confidence=1.0,
            ability_confidence=1.0 if hoverboard else 0.0,
            debug=debug,
            gesture_label="KEYBOARD",
        )

    def reset(self):
        self._state = InputState(provider_name=self.name, tracking=True, calibrated=True)

    def update(self, frame) -> InputState:
        return self._state
