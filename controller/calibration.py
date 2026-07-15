import time
import statistics

from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from vision.landmarks import Landmark


class CalibrationData:
    def __init__(self):
        self.shoulder_width: float = 0.0
        self.body_height: float = 0.0
        self.arm_length: float = 0.0
        self.body_center_x: float = 0.0
        self.rest_hip_y: float = 0.0

    def is_valid(self) -> bool:
        return self.shoulder_width > 0


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

        return data
