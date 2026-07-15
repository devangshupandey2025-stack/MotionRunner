from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import HoverboardResult
from controller.calibration import CalibrationData


class HoverboardDetector:
    def __init__(self, config: AppConfig):
        self.config = config
        self._hands_up_since: float | None = None
        self._has_triggered = False
        self._calibration: CalibrationData | None = None

    def set_calibration(self, data: CalibrationData):
        self._calibration = data

    def detect(self, pose: PoseFrame) -> HoverboardResult:
        if not self._calibration:
            return HoverboardResult(False, 0.0, debug="No calibration")

        hands_up = (
            pose.left_wrist.y < pose.nose.y
            and pose.right_wrist.y < pose.nose.y
            and pose.left_wrist.visibility > self.config.visibility_threshold
            and pose.right_wrist.visibility > self.config.visibility_threshold
        )

        elapsed_ms = 0.0
        if hands_up:
            if self._hands_up_since is None:
                self._hands_up_since = pose.timestamp
            elif not self._has_triggered:
                elapsed_ms = (pose.timestamp - self._hands_up_since) * 1000
                if elapsed_ms >= self.config.hoverboard_hold_ms:
                    self._has_triggered = True
                    return HoverboardResult(
                        True,
                        0.85,
                        hands_up=hands_up,
                        elapsed_ms=elapsed_ms,
                        debug=f"Hands held: {elapsed_ms:.0f}ms",
                    )
        else:
            self._hands_up_since = None
            self._has_triggered = False

        if hands_up and self._hands_up_since is not None:
            elapsed_ms = (pose.timestamp - self._hands_up_since) * 1000

        return HoverboardResult(
            False,
            0.0,
            hands_up=hands_up,
            elapsed_ms=elapsed_ms,
            debug=f"Hover idle: hands={'1' if hands_up else '0'} held={elapsed_ms:.0f}ms",
        )
