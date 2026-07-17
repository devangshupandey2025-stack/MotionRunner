from enum import Enum, auto

from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import SlideResult
from controller.calibration import CalibrationData


class SlideState(Enum):
    STANDING = auto()
    DEBOUNCING = auto()
    SLIDING = auto()


class SlideDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self._state = SlideState.STANDING
        self._debounce_count = 0
        self._slide_start_time = 0.0
        self._calibration: CalibrationData | None = None
        self._duck_line_y: float | None = None
        self._smoothed_hip_y: float | None = None
        self._smoothed_height_ratio: float | None = None
        self._last_exit_time: float = 0.0

    def set_calibration(self, data: CalibrationData):
        self._calibration = data
        self._duck_line_y = data.duck_line_y
        self._smoothed_hip_y = None
        self._smoothed_height_ratio = None
        self._last_exit_time = 0.0

    def update_duck_line(self, duck_line_y: float):
        """Update duck threshold without resetting detector state."""
        self._duck_line_y = duck_line_y

    def reset(self):
        self._state = SlideState.STANDING
        self._debounce_count = 0

    def detect(self, pose: PoseFrame) -> SlideResult:
        if not self._calibration:
            return SlideResult(False, 0.0, debug="No calibration")

        raw_height_ratio = pose.body_height / self._calibration.body_height
        raw_hip_y = pose.hip_center.y
        alpha = self.config.slide_hip_smoothing_alpha

        if self._smoothed_height_ratio is None or self._smoothed_hip_y is None:
            self._smoothed_height_ratio = raw_height_ratio
            self._smoothed_hip_y = raw_hip_y
        else:
            self._smoothed_height_ratio = alpha * raw_height_ratio + (1 - alpha) * self._smoothed_height_ratio
            self._smoothed_hip_y = alpha * raw_hip_y + (1 - alpha) * self._smoothed_hip_y

        height_ratio = self._smoothed_height_ratio
        knee_angle = pose.min_knee_angle
        crossed_duck = self._duck_line_y is not None and self._smoothed_hip_y > self._duck_line_y

        compression_squat = (
            height_ratio < self.config.slide_enter_height_ratio
            and knee_angle < self.config.slide_knee_angle_threshold
        )
        is_squatting = compression_squat or crossed_duck
        is_standing = height_ratio > self.config.slide_exit_height_ratio

        elapsed_ms = 0.0
        active = False
        confidence = 0.0
        
        in_cooldown = (pose.timestamp - self._last_exit_time) * 1000 < self.config.slide_cooldown_ms

        debug = (
            f"Slide idle: h={height_ratio:.2f} k={knee_angle:.0f} "
            f"duck={'1' if crossed_duck else '0'} squat={'1' if is_squatting else '0'}"
        )

        if self._state == SlideState.STANDING:
            if is_squatting and not in_cooldown:
                self._state = SlideState.DEBOUNCING
                self._debounce_count = 0
                debug = f"Slide debounce start: h={height_ratio:.2f} k={knee_angle:.0f}°"
            elif in_cooldown:
                debug = f"Slide cooldown"

        elif self._state == SlideState.DEBOUNCING:
            if is_squatting:
                self._debounce_count += 1
                if self._debounce_count >= self.config.slide_debounce_frames:
                    self._state = SlideState.SLIDING
                    self._slide_start_time = pose.timestamp
                    active = True
                    confidence = 0.9
                    debug = f"Slide enter: h={height_ratio:.2f} k={knee_angle:.0f}° d={'1' if crossed_duck else '0'}"
                else:
                    debug = f"Slide debouncing: {self._debounce_count}/{self.config.slide_debounce_frames}"
            else:
                self._state = SlideState.STANDING
                debug = "Slide debounce reset"

        elif self._state == SlideState.SLIDING:
            elapsed_ms = (pose.timestamp - self._slide_start_time) * 1000

            if is_standing or elapsed_ms > self.config.slide_max_hold_ms:
                self._state = SlideState.STANDING
                self._last_exit_time = pose.timestamp
                debug = f"Slide exit: {elapsed_ms:.0f}ms"
                elapsed_ms = 0.0
            else:
                active = True
                confidence = min(0.95, max(0.6, 1.0 - height_ratio))
                if crossed_duck:
                    confidence = min(0.95, confidence + 0.10)
                debug = f"Sliding: {elapsed_ms:.0f}ms h={height_ratio:.2f} d={'1' if crossed_duck else '0'}"

        return SlideResult(
            active,
            confidence,
            height_ratio=height_ratio,
            knee_angle=knee_angle,
            crossed_duck=bool(crossed_duck),
            state=self._state.name,
            elapsed_ms=elapsed_ms,
            is_squatting=is_squatting,
            is_standing=is_standing,
            debug=debug,
        )
