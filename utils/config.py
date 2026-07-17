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
    jump_hip_smoothing_alpha: float = 0.25
    jump_velocity_window: int = 5
    jump_min_upward_velocity: float = -0.01
    jump_cooldown_ms: int = 400
    jump_reset_margin: float = 0.03
    jump_use_shoulder: bool = True
    duck_line_offset: float = 0.12
    slide_enter_height_ratio: float = 0.82
    slide_exit_height_ratio: float = 0.90
    slide_knee_angle_threshold: float = 135.0
    slide_debounce_frames: int = 2
    slide_max_hold_ms: int = 1500
    slide_hip_smoothing_alpha: float = 0.3
    slide_cooldown_ms: int = 400
    adaptive_baseline_enabled: bool = True
    adaptive_baseline_alpha: float = 0.005
    adaptive_idle_ms: int = 500
    hoverboard_hold_ms: int = 500

    cooldown: dict = field(default_factory=lambda: {
        "LEFT": 500,
        "RIGHT": 500,
        "JUMP": 800,
        "SLIDE": 1000,
        "HOVERBOARD": 2000,
    })

    # --- Calibration Settings ---
    calibration_duration_ms: int = 3000
    calibration_wizard_enabled: bool = True
    calibration_positioning_stable_ms: int = 1000
    calibration_preview_duration_s: int = 3
    calibration_min_shoulder_width: float = 0.05
    calibration_min_body_height: float = 0.15
    calibration_timeout_s: int = 20
    calibration_audio_enabled: bool = True

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

    # --- Virtual Lane Tracking Settings ---
    lane_count: int = 3
    lane_buffer_percentage: float = 0.15
    lane_smoothing_alpha: float = 0.2
    lane_change_cooldown_ms: int = 120
    lane_lost_confidence_threshold: float = 0.4

    # --- HUD Settings ---
    show_gesture_flash: bool = True
    show_confidence_meters: bool = True
    show_tracking_quality: bool = True
    show_gesture_timeline: bool = False
    show_baseline_drift: bool = True
    gesture_flash_duration_ms: int = 300
    gesture_timeline_window_s: int = 5

    active_preset: str = "Normal"
    _current_preset_file: str = "default"

    def get_available_presets(self) -> list[str]:
        import os
        d = "presets"
        if not os.path.exists(d): return []
        return sorted([f[:-5] for f in os.listdir(d) if f.endswith(".json")])
        
    def cycle_preset(self, forward: bool = True):
        presets = self.get_available_presets()
        if not presets: return
        
        try:
            idx = presets.index(self._current_preset_file)
        except ValueError:
            idx = 0
            
        if forward:
            next_idx = (idx + 1) % len(presets)
        else:
            next_idx = (idx - 1) % len(presets)
            
        self.load_preset(presets[next_idx])
        
    def load_preset(self, name: str):
        import os
        import json
        path = os.path.join("presets", f"{name}.json")
        if not os.path.exists(path):
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
                self.active_preset = data.pop("name", name.capitalize())
                self._current_preset_file = name
                for k, v in data.items():
                    if hasattr(self, k):
                        setattr(self, k, v)
        except Exception as e:
            print(f"Failed to load preset {name}: {e}")

    def _get_settings_dir(self) -> str:
        import os
        from pathlib import Path
        home = Path.home()
        settings_dir = home / ".motionrunner"
        settings_dir.mkdir(parents=True, exist_ok=True)
        return str(settings_dir)

    def save_settings(self):
        import os
        import json
        from dataclasses import asdict
        
        default_config = AppConfig()
        current_dict = asdict(self)
        default_dict = asdict(default_config)
        
        diff = {"schema": 1}
        for k, v in current_dict.items():
            if k.startswith("_"): continue
            # Only save if changed from default, except don't save dynamic fields if they shouldn't persist
            # Wait, keymap is a custom object, and enums might not serialize easily.
            # We will handle enums by converting to string.
            if isinstance(v, Enum):
                v_val = v.name
                def_val = default_dict[k].name
                if v_val != def_val:
                    diff[k] = v_val
            elif isinstance(v, (int, float, bool, str)) and v != default_dict[k]:
                diff[k] = v
                
        settings_path = os.path.join(self._get_settings_dir(), "settings.json")
        try:
            with open(settings_path, "w") as f:
                json.dump(diff, f, indent=2)
            print(f"Settings saved to {settings_path}")
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def load_settings(self):
        import os
        import json
        settings_path = os.path.join(self._get_settings_dir(), "settings.json")
        if not os.path.exists(settings_path):
            return
            
        try:
            with open(settings_path, "r") as f:
                data = json.load(f)
                
            for k, v in data.items():
                if k == "schema": continue
                if hasattr(self, k):
                    attr = getattr(self, k)
                    if isinstance(attr, Enum):
                        # Find enum type
                        enum_type = type(attr)
                        try:
                            setattr(self, k, enum_type[v])
                        except KeyError:
                            pass
                    else:
                        setattr(self, k, v)
        except Exception as e:
            print(f"Failed to load settings: {e}")

    def save_calibration(self, cal_data):
        import os
        import json
        if not cal_data:
            return
            
        profiles_dir = os.path.join(self._get_settings_dir(), "profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        # For now, default to "default.json". In the future, we can make it dynamic.
        cal_path = os.path.join(profiles_dir, "default.json")
        try:
            with open(cal_path, "w") as f:
                json.dump(cal_data.to_dict(), f, indent=2)
            print(f"Calibration profile saved to {cal_path}")
        except Exception as e:
            print(f"Failed to save calibration profile: {e}")

    def load_calibration(self):
        import os
        import json
        profiles_dir = os.path.join(self._get_settings_dir(), "profiles")
        cal_path = os.path.join(profiles_dir, "default.json")
        
        # Fallback to older calibration.json for backwards compatibility
        if not os.path.exists(cal_path):
            cal_path = os.path.join(self._get_settings_dir(), "calibration.json")
            
        if not os.path.exists(cal_path):
            return None
            
        try:
            with open(cal_path, "r") as f:
                data = json.load(f)
            from controller.calibration import CalibrationData
            return CalibrationData.from_dict(data)
        except Exception as e:
            print(f"Failed to load calibration profile: {e}")
            return None
