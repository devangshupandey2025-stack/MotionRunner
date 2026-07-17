from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.motion_event import TrackingResult


class PositionTracker:
    """Selects the best tracking landmark and outputs its X coordinate.

    The input PoseFrame is already EMA-smoothed by PoseProvider's
    LandmarkFilter, so we do NOT apply a second EMA here — that would
    create double-smoothing and make the position too sluggish to cross
    lane boundaries.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self._lost_frames_hip = 0
        self._lost_frames_shoulder = 0

    def track(self, pose: PoseFrame) -> TrackingResult:
        raw_x = 0.5
        confidence = 0.0
        source = "UNKNOWN"

        # Determine best tracking point with debouncing
        hip_conf = min(pose.left_hip.visibility, pose.right_hip.visibility)
        shoulder_conf = min(pose.left_shoulder.visibility, pose.right_shoulder.visibility)

        if hip_conf > self.config.lane_lost_confidence_threshold:
            self._lost_frames_hip = 0
        else:
            self._lost_frames_hip += 1

        if shoulder_conf > self.config.lane_lost_confidence_threshold:
            self._lost_frames_shoulder = 0
        else:
            self._lost_frames_shoulder += 1

        if self._lost_frames_hip < 5:
            raw_x = pose.hip_center.x
            confidence = hip_conf
            source = "HIP"
        elif self._lost_frames_shoulder < 5:
            raw_x = pose.shoulder_center.x
            confidence = shoulder_conf
            source = "SHOULDER"
        else:
            raw_x = pose.nose.x
            confidence = pose.nose.visibility
            source = "NOSE"

        # No second EMA — pose is already smoothed upstream
        return TrackingResult(
            raw_x=raw_x,
            filtered_x=raw_x,
            tracking_source=source,
            confidence=confidence,
            timestamp=pose.timestamp,
        )

