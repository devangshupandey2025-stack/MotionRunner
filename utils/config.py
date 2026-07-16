from dataclasses import dataclass, field
from enum import Enum, auto


class PlayerCommand(Enum):
    LEFT = auto()
    RIGHT = auto()
    JUMP = auto()
    SLIDE = auto()
    HOVERBOARD = auto()


class ControlMode(Enum):
    DEBUG = auto()
    GAME = auto()


class InputMode(Enum):
    POSE = auto()
    HAND = auto()


class ProcessingMode(Enum):
    AUTO = auto()
    EVERY_FRAME = auto()
    EVERY_2_FRAMES = auto()
    EVERY_3_FRAMES = auto()


@dataclass
class KeyMap:
    bindings: dict[PlayerCommand, str] = field(default_factory=lambda: {
        PlayerCommand.LEFT: "left",
        PlayerCommand.RIGHT: "right",
        PlayerCommand.JUMP: "up",
        PlayerCommand.SLIDE: "down",
        PlayerCommand.HOVERBOARD: "space",
    })


@dataclass
class AppConfig:
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    mirror_camera: bool = True

    mp_detection_confidence: float = 0.5
    mp_tracking_confidence: float = 0.5

    smoothing_alpha: float = 0.6

    lane_threshold: float = 0.3
    jump_line_offset: float = 0.08
    jump_dead_zone: float = 0.02
    jump_confirmation_time_ms: int = 90
    duck_line_offset: float = 0.12
    slide_enter_height_ratio: float = 0.82
    slide_exit_height_ratio: float = 0.90
    slide_knee_angle_threshold: float = 135.0
    slide_debounce_frames: int = 2
    slide_max_hold_ms: int = 1500
    hoverboard_hold_ms: int = 500

    cooldown: dict = field(default_factory=lambda: {
        "LEFT": 500,
        "RIGHT": 500,
        "JUMP": 800,
        "SLIDE": 1000,
        "HOVERBOARD": 2000,
    })

    calibration_frames: int = 60
    calibration_countdown_s: int = 3

    sidebar_width: int = 280
    keymap: KeyMap = field(default_factory=KeyMap)
    control_mode: ControlMode = ControlMode.DEBUG
    visibility_threshold: float = 0.5
    lost_frame_threshold: int = 10

    input_mode: InputMode = InputMode.POSE
    hand_detection_confidence: float = 0.5
    hand_tracking_confidence: float = 0.5
    hand_smoothing_alpha: float = 0.35
    hand_dead_zone: float = 0.18
    hand_horizontal_range: float = 0.22
    hand_pinch_threshold: float = 0.06
    hand_calibration_frames: int = 45
    pose_model_complexity: int = 0
    processing_mode: ProcessingMode = ProcessingMode.AUTO
    processing_width: int = 0
    processing_height: int = 0
    show_pose_overlay: bool = True
    show_sidebar: bool = True
    show_guides: bool = True
    show_hand_landmarks: bool = True
