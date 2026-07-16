from controller.action import PlayerState
from input.input_state import InputState


def player_state_to_input_state(
    state: PlayerState,
    *,
    provider_name: str,
    tracking: bool,
    calibrated: bool,
    gesture_label: str = "",
    landmarks: list[tuple[float, float]] | None = None,
) -> InputState:
    return InputState(
        provider_name=provider_name,
        tracking=tracking,
        calibrated=calibrated,
        lane=state.lane,
        posture=state.posture,
        abilities=set(state.abilities),
        lane_confidence=state.lane_confidence,
        posture_confidence=state.posture_confidence,
        ability_confidence=state.ability_confidence,
        timestamp=state.timestamp,
        frame_index=state.frame_index,
        debug=state.debug,
        gesture_label=gesture_label,
        landmarks=list(landmarks or []),
    )
