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
    # Camera
    camera_index: int = 0
    camera_width: int = 640
    camera_height: int = 480
    mirror_camera: bool = True

    # MediaPipe
    mp_detection_confidence: float = 0.5
    mp_tracking_confidence: float = 0.5

    # EMA Smoothing
    smoothing_alpha: float = 0.6

    # Lane Detection (as ratio of shoulder_width)
    lane_threshold: float = 0.3

    # Jump Detection (zone-crossing with temporal confirmation)
    jump_line_offset: float = 0.08      # body-height ratio above waist for jump threshold line
    jump_dead_zone: float = 0.02        # hysteresis buffer (body-height ratio) above jump line
    jump_confirmation_time_ms: int = 90 # time above jump line to confirm a jump

    # Duck Detection (visual guide line only)
    duck_line_offset: float = 0.12      # body-height ratio below waist for duck threshold line

    # Slide Detection
    slide_enter_height_ratio: float = 0.82
    slide_exit_height_ratio: float = 0.90
    slide_knee_angle_threshold: float = 135.0
    slide_debounce_frames: int = 2
    slide_max_hold_ms: int = 1500

    # Hoverboard
    hoverboard_hold_ms: int = 500

    # Cooldowns (ms)
    cooldown: dict = field(default_factory=lambda: {
        "LEFT": 500,
        "RIGHT": 500,
        "JUMP": 800,
        "SLIDE": 1000,
        "HOVERBOARD": 2000,
    })

    # Calibration
    calibration_frames: int = 60
    calibration_countdown_s: int = 3

    # Visualizer
    sidebar_width: int = 280

    # Keyboard control
    keymap: KeyMap = field(default_factory=KeyMap)
    control_mode: ControlMode = ControlMode.DEBUG

    # Landmark visibility threshold
    visibility_threshold: float = 0.5

    # LOST state
    lost_frame_threshold: int = 10
