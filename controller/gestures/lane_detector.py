from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import Lane, LaneResult
from controller.calibration import CalibrationData


class LaneDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self._calibration: CalibrationData | None = None

    def set_calibration(self, data: CalibrationData):
        self._calibration = data

    def _compute_offset(self, pose: PoseFrame) -> float | None:
        if not self._calibration:
            return None
        delta_x = pose.body_center.x - self._calibration.body_center_x
        return delta_x / self._calibration.shoulder_width

    def classify(self, pose: PoseFrame) -> LaneResult | None:
        offset = self._compute_offset(pose)
        if offset is None:
            return None
        if offset < -self.config.lane_threshold:
            direction = Lane.LEFT
        elif offset > self.config.lane_threshold:
            direction = Lane.RIGHT
        else:
            direction = Lane.CENTER
        confidence = min(1.0, abs(offset) / (self.config.lane_threshold * 2))
        return LaneResult(direction, confidence, offset)
