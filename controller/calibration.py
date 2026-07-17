import time
import statistics

from dataclasses import dataclass

from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from vision.landmarks import Landmark

@dataclass
class CalibrationQuality:
    shoulder_width_ok: bool
    body_height_ok: bool
    hip_centered: bool
    overall_ok: bool


class CalibrationData:
    def __init__(self):
        self.shoulder_width: float = 0.0
        self.body_height: float = 0.0
        self.arm_length: float = 0.0
        self.body_center_x: float = 0.0
        self.rest_hip_y: float = 0.0
        self.inverse_shoulder_width: float = 0.0
        self.jump_line_y: float = 0.0
        self.effective_jump_line_y: float = 0.0
        self.duck_line_y: float = 0.0
        self.lane_positions: list[float] = []

    def is_valid(self) -> bool:
        return self.shoulder_width > 0

    def recompute_lines(self, config: AppConfig):
        if self.body_height > 0:
            self.jump_line_y = self.rest_hip_y - config.jump_line_offset * self.body_height
            self.effective_jump_line_y = self.jump_line_y - config.jump_dead_zone * self.body_height
            self.duck_line_y = self.rest_hip_y + config.duck_line_offset * self.body_height

    def to_dict(self) -> dict:
        return {
            "shoulder_width": self.shoulder_width,
            "body_height": self.body_height,
            "arm_length": self.arm_length,
            "body_center_x": self.body_center_x,
            "rest_hip_y": self.rest_hip_y,
            "inverse_shoulder_width": self.inverse_shoulder_width,
            "jump_line_y": self.jump_line_y,
            "effective_jump_line_y": self.effective_jump_line_y,
            "duck_line_y": self.duck_line_y,
            "lane_positions": self.lane_positions,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CalibrationData":
        data = cls()
        for k, v in d.items():
            if hasattr(data, k):
                setattr(data, k, v)
                
        # Backward compatibility for V2 Virtual Lane Tracking
        if not data.lane_positions and data.body_center_x > 0:
            cx = data.body_center_x
            data.lane_positions = [cx - 0.15, cx, cx + 0.15]
            
        return data

    def quality_report(self, config: AppConfig) -> CalibrationQuality:
        w_ok = self.shoulder_width > config.calibration_min_shoulder_width
        h_ok = self.body_height > config.calibration_min_body_height
        y_ok = 0.3 <= self.rest_hip_y <= 0.8
        
        return CalibrationQuality(
            shoulder_width_ok=w_ok,
            body_height_ok=h_ok,
            hip_centered=y_ok,
            overall_ok=w_ok and h_ok and y_ok
        )


class Calibrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self._frames: list[PoseFrame] = []
        self._start_time: float | None = None
        self._collecting = False
        self._done = False
        self._result: CalibrationData | None = None

    @property
    def countdown_remaining(self) -> int:
        if self._done:
            return 0
        if self._start_time is None:
            return self.config.calibration_countdown_s
        elapsed = time.perf_counter() - self._start_time
        remaining = self.config.calibration_countdown_s - int(elapsed)
        return max(0, remaining)

    @property
    def collecting(self) -> bool:
        return self._collecting and not self._done

    @property
    def progress(self) -> float:
        if not self._collecting:
            return 0.0
        return len(self._frames) / self.config.calibration_frames

    @property
    def done(self) -> bool:
        return self._done

    @property
    def result(self) -> CalibrationData | None:
        return self._result

    def start(self):
        self._frames = []
        self._start_time = time.perf_counter()
        self._collecting = False
        self._done = False
        self._result = None

    def update(self, pose: PoseFrame | None) -> CalibrationData | None:
        if self._done:
            return self._result

        if self._start_time is None:
            return None

        if self.countdown_remaining > 0:
            return None

        if not self._collecting:
            self._collecting = True

        if pose is None:
            return None

        if not self._is_valid_pose(pose):
            return None

        self._frames.append(pose)

        if len(self._frames) >= self.config.calibration_frames:
            self._result = self._compute()
            
            # Synthesize lane_positions for backward compatibility if not running extended wizard
            # A full wizard run will override these later.
            cx = self._result.body_center_x
            self._result.lane_positions = [cx - 0.15, cx, cx + 0.15]
            
            self._done = True
            return self._result

        return None

    def _is_valid_pose(self, pose: PoseFrame) -> bool:
        return (
            pose.left_shoulder.visibility > self.config.visibility_threshold
            and pose.right_shoulder.visibility > self.config.visibility_threshold
            and pose.left_hip.visibility > self.config.visibility_threshold
            and pose.right_hip.visibility > self.config.visibility_threshold
        )

    def _compute(self) -> CalibrationData:
        data = CalibrationData()

        shoulder_widths = [
            f.left_shoulder.distance_to(f.right_shoulder)
            for f in self._frames
        ]
        body_heights = [
            f.nose.distance_to(f.hip_center)
            for f in self._frames
        ]
        arm_lengths = [
            f.left_shoulder.distance_to(f.left_wrist)
            for f in self._frames
        ]
        body_center_xs = [
            f.body_center.x
            for f in self._frames
        ]
        rest_hip_ys = [
            f.hip_center.y
            for f in self._frames
        ]

        data.shoulder_width = statistics.median(shoulder_widths)
        data.body_height = statistics.median(body_heights)
        data.arm_length = statistics.median(arm_lengths)
        data.body_center_x = statistics.median(body_center_xs)
        data.rest_hip_y = statistics.median(rest_hip_ys)
        data.inverse_shoulder_width = 1.0 / data.shoulder_width if data.shoulder_width else 0.0
        data.jump_line_y = data.rest_hip_y - self.config.jump_line_offset * data.body_height
        data.effective_jump_line_y = data.jump_line_y - self.config.jump_dead_zone * data.body_height
        data.duck_line_y = data.rest_hip_y + self.config.duck_line_offset * data.body_height

        return data
