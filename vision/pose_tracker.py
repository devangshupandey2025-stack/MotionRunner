import time
import cv2

try:
    from mediapipe.python.solutions import pose as mp_pose
except ModuleNotFoundError as exc:
    try:
        import mediapipe as mp

        mp_pose = mp.solutions.pose
    except (AttributeError, ModuleNotFoundError) as fallback_exc:
        raise ModuleNotFoundError(
            "This project uses MediaPipe's legacy Pose solution API, but the installed "
            "mediapipe package does not expose it. Install a compatible version with "
            "`python -m pip install \"mediapipe==0.10.9\"`."
        ) from fallback_exc

from utils.config import AppConfig
from vision.landmarks import Landmark
from vision.pose_frame import PoseFrame


class PoseTracker:
    def __init__(self, config: AppConfig):
        self.config = config
        self._mp_pose = mp_pose
        self._pose = self._mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            smooth_landmarks=True,
            min_detection_confidence=config.mp_detection_confidence,
            min_tracking_confidence=config.mp_tracking_confidence,
        )
        self._prev_time = time.perf_counter()
        self._fps = 0.0
        self._frame_index = 0
        self._landmark_enums = {
            "NOSE": self._mp_pose.PoseLandmark.NOSE,
            "LEFT_EYE": self._mp_pose.PoseLandmark.LEFT_EYE,
            "RIGHT_EYE": self._mp_pose.PoseLandmark.RIGHT_EYE,
            "LEFT_SHOULDER": self._mp_pose.PoseLandmark.LEFT_SHOULDER,
            "RIGHT_SHOULDER": self._mp_pose.PoseLandmark.RIGHT_SHOULDER,
            "LEFT_ELBOW": self._mp_pose.PoseLandmark.LEFT_ELBOW,
            "RIGHT_ELBOW": self._mp_pose.PoseLandmark.RIGHT_ELBOW,
            "LEFT_WRIST": self._mp_pose.PoseLandmark.LEFT_WRIST,
            "RIGHT_WRIST": self._mp_pose.PoseLandmark.RIGHT_WRIST,
            "LEFT_HIP": self._mp_pose.PoseLandmark.LEFT_HIP,
            "RIGHT_HIP": self._mp_pose.PoseLandmark.RIGHT_HIP,
            "LEFT_KNEE": self._mp_pose.PoseLandmark.LEFT_KNEE,
            "RIGHT_KNEE": self._mp_pose.PoseLandmark.RIGHT_KNEE,
            "LEFT_ANKLE": self._mp_pose.PoseLandmark.LEFT_ANKLE,
            "RIGHT_ANKLE": self._mp_pose.PoseLandmark.RIGHT_ANKLE,
        }

    @property
    def fps(self) -> float:
        return self._fps

    def detect(self, frame) -> PoseFrame | None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self._pose.process(rgb)

        current_time = time.perf_counter()
        self._frame_index += 1
        dt = current_time - self._prev_time
        self._fps = (0.9 * self._fps) + (0.1 / max(dt, 0.001))
        self._prev_time = current_time

        if not results.pose_landmarks:
            return None

        lm = results.pose_landmarks.landmark
        e = self._landmark_enums

        return PoseFrame(
            timestamp=current_time,
            frame_index=self._frame_index,
            fps=self._fps,
            nose=self._to_landmark(lm[e["NOSE"]]),
            left_eye=self._to_landmark(lm[e["LEFT_EYE"]]),
            right_eye=self._to_landmark(lm[e["RIGHT_EYE"]]),
            left_shoulder=self._to_landmark(lm[e["LEFT_SHOULDER"]]),
            right_shoulder=self._to_landmark(lm[e["RIGHT_SHOULDER"]]),
            left_elbow=self._to_landmark(lm[e["LEFT_ELBOW"]]),
            right_elbow=self._to_landmark(lm[e["RIGHT_ELBOW"]]),
            left_wrist=self._to_landmark(lm[e["LEFT_WRIST"]]),
            right_wrist=self._to_landmark(lm[e["RIGHT_WRIST"]]),
            left_hip=self._to_landmark(lm[e["LEFT_HIP"]]),
            right_hip=self._to_landmark(lm[e["RIGHT_HIP"]]),
            left_knee=self._to_landmark(lm[e["LEFT_KNEE"]]),
            right_knee=self._to_landmark(lm[e["RIGHT_KNEE"]]),
            left_ankle=self._to_landmark(lm[e["LEFT_ANKLE"]]),
            right_ankle=self._to_landmark(lm[e["RIGHT_ANKLE"]]),
        )

    def _to_landmark(self, lm) -> Landmark:
        return Landmark(x=lm.x, y=lm.y, z=lm.z, visibility=lm.visibility)
