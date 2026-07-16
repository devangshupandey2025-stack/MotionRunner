from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import JumpResult
from controller.calibration import CalibrationData


class JumpDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self._prev_hip_y: float | None = None
        self._prev_time: float | None = None
        self._crossing_start_time: float | None = None
        self._has_triggered = False
        self._jump_line_y: float | None = None
        self._effective_jump_line_y: float | None = None
        self._calibration: CalibrationData | None = None

    def set_calibration(self, data: CalibrationData):
        self._calibration = data
        self._jump_line_y = data.jump_line_y
        self._effective_jump_line_y = data.effective_jump_line_y
        self._prev_hip_y = None
        self._prev_time = None
        self._crossing_start_time = None
        self._has_triggered = False

    def detect(self, pose: PoseFrame) -> JumpResult:
        if not self._calibration or self._jump_line_y is None:
            return JumpResult(False, 0.0, debug="No calibration")

        hip_y = pose.hip_center.y

        if self._prev_hip_y is None:
            self._prev_hip_y = hip_y
            self._prev_time = pose.timestamp
            return JumpResult(False, 0.0, debug="Priming jump baseline")

        dt = pose.timestamp - self._prev_time
        velocity = (hip_y - self._prev_hip_y) / dt if dt > 0 else 0.0
        self._prev_hip_y = hip_y
        self._prev_time = pose.timestamp

        above_effective = hip_y < self._effective_jump_line_y
        above_jump_line = hip_y < self._jump_line_y
        moving_upward = velocity < 0
        elapsed_ms = 0.0

        if above_effective and moving_upward:
            if self._crossing_start_time is None:
                self._crossing_start_time = pose.timestamp
            elapsed_ms = (pose.timestamp - self._crossing_start_time) * 1000
            if elapsed_ms >= self.config.jump_confirmation_time_ms and not self._has_triggered:
                self._has_triggered = True
                offset_ratio = (self._jump_line_y - hip_y) / self._calibration.body_height
                confidence = min(1.0, offset_ratio / self.config.jump_line_offset)
                return JumpResult(
                    True,
                    confidence,
                    velocity=velocity,
                    above_line=above_jump_line,
                    above_effective_line=above_effective,
                    moving_upward=moving_upward,
                    elapsed_ms=elapsed_ms,
                    debug=f"Jump: {elapsed_ms:.0f}ms v={velocity:.4f}",
                )
        elif not above_jump_line:
            self._crossing_start_time = None
            self._has_triggered = False

        if self._crossing_start_time is not None:
            elapsed_ms = (pose.timestamp - self._crossing_start_time) * 1000

        return JumpResult(
            False,
            0.0,
            velocity=velocity,
            above_line=above_jump_line,
            above_effective_line=above_effective,
            moving_upward=moving_upward,
            elapsed_ms=elapsed_ms,
            debug=f"Jump idle: above={int(above_jump_line)} effective={int(above_effective)} v={velocity:.4f}",
        )
