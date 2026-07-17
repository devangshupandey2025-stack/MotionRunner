import collections
from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import JumpResult
from controller.calibration import CalibrationData


class JumpDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self._prev_tracking_y: float | None = None
        self._smoothed_tracking_y: float | None = None
        self._prev_time: float | None = None
        self._crossing_start_time: float | None = None
        self._has_triggered = False
        self._jump_line_y: float | None = None
        self._effective_jump_line_y: float | None = None
        self._calibration: CalibrationData | None = None
        self._velocity_history = collections.deque(maxlen=self.config.jump_velocity_window)
        self._last_trigger_time: float = 0.0

    def set_calibration(self, data: CalibrationData):
        self._calibration = data
        self._jump_line_y = data.jump_line_y
        self._effective_jump_line_y = data.effective_jump_line_y
        self._prev_tracking_y = None
        self._smoothed_tracking_y = None
        self._prev_time = None
        self._crossing_start_time = None
        self._has_triggered = False
        self._velocity_history.clear()
        self._last_trigger_time = 0.0

    def update_jump_lines(self, jump_line_y: float, effective_jump_line_y: float):
        """Update threshold lines without resetting detector state."""
        self._jump_line_y = jump_line_y
        self._effective_jump_line_y = effective_jump_line_y

    def detect(self, pose: PoseFrame) -> JumpResult:
        if not self._calibration or self._jump_line_y is None:
            return JumpResult(False, 0.0, debug="No calibration")

        if self.config.jump_use_shoulder:
            tracking_y = (pose.hip_center.y + pose.shoulder_center.y) / 2
        else:
            tracking_y = pose.hip_center.y

        if self._smoothed_tracking_y is None:
            self._smoothed_tracking_y = tracking_y
        else:
            alpha = self.config.jump_hip_smoothing_alpha
            self._smoothed_tracking_y = alpha * tracking_y + (1 - alpha) * self._smoothed_tracking_y

        if self._prev_tracking_y is None:
            self._prev_tracking_y = self._smoothed_tracking_y
            self._prev_time = pose.timestamp
            return JumpResult(False, 0.0, debug="Priming jump baseline")

        dt = pose.timestamp - self._prev_time
        instant_velocity = (self._smoothed_tracking_y - self._prev_tracking_y) / dt if dt > 0 else 0.0
        self._velocity_history.append(instant_velocity)
        
        velocity = sum(self._velocity_history) / len(self._velocity_history)

        self._prev_tracking_y = self._smoothed_tracking_y
        self._prev_time = pose.timestamp

        above_effective = self._smoothed_tracking_y < self._effective_jump_line_y
        above_jump_line = self._smoothed_tracking_y < self._jump_line_y
        moving_upward = velocity < self.config.jump_min_upward_velocity
        elapsed_ms = 0.0
        
        in_cooldown = (pose.timestamp - self._last_trigger_time) * 1000 < self.config.jump_cooldown_ms

        if above_effective:
            if self._crossing_start_time is None:
                # Only start the crossing timer if we are moving upward with enough velocity
                if moving_upward:
                    self._crossing_start_time = pose.timestamp
                    
            if self._crossing_start_time is not None:
                elapsed_ms = (pose.timestamp - self._crossing_start_time) * 1000
                
                if elapsed_ms >= self.config.jump_confirmation_time_ms and not self._has_triggered:
                    self._has_triggered = True
                    
                    if not in_cooldown:
                        self._last_trigger_time = pose.timestamp
                        offset_ratio = (self._jump_line_y - self._smoothed_tracking_y) / self._calibration.body_height
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
        elif self._smoothed_tracking_y > self._jump_line_y + self.config.jump_reset_margin * self._calibration.body_height:
            # Hysteresis reset
            self._crossing_start_time = None
            self._has_triggered = False

        if self._crossing_start_time is not None:
            elapsed_ms = (pose.timestamp - self._crossing_start_time) * 1000

        debug_state = f"cd={int(in_cooldown)}" if in_cooldown else f"above={int(above_jump_line)} effective={int(above_effective)} v={velocity:.4f}"

        return JumpResult(
            False,
            0.0,
            velocity=velocity,
            above_line=above_jump_line,
            above_effective_line=above_effective,
            moving_upward=moving_upward,
            elapsed_ms=elapsed_ms,
            debug=f"Jump idle: {debug_state}",
        )
