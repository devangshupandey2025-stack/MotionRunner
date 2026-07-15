from abc import ABC, abstractmethod
from vision.pose_frame import PoseFrame
from vision.landmarks import Landmark


class LandmarkFilter(ABC):
    @abstractmethod
    def update(self, frame: PoseFrame | None) -> PoseFrame | None:
        ...


class EMAFilter(LandmarkFilter):
    def __init__(self, alpha: float):
        self.alpha = alpha
        self._prev: PoseFrame | None = None

    def update(self, frame: PoseFrame | None) -> PoseFrame | None:
        if frame is None:
            self._prev = None
            return None

        if self._prev is None:
            self._prev = frame
            return frame

        smoothed = PoseFrame(
            timestamp=frame.timestamp,
            frame_index=frame.frame_index,
            fps=frame.fps,
            nose=self._ema(self._prev.nose, frame.nose),
            left_eye=self._ema(self._prev.left_eye, frame.left_eye),
            right_eye=self._ema(self._prev.right_eye, frame.right_eye),
            left_shoulder=self._ema(self._prev.left_shoulder, frame.left_shoulder),
            right_shoulder=self._ema(self._prev.right_shoulder, frame.right_shoulder),
            left_elbow=self._ema(self._prev.left_elbow, frame.left_elbow),
            right_elbow=self._ema(self._prev.right_elbow, frame.right_elbow),
            left_wrist=self._ema(self._prev.left_wrist, frame.left_wrist),
            right_wrist=self._ema(self._prev.right_wrist, frame.right_wrist),
            left_hip=self._ema(self._prev.left_hip, frame.left_hip),
            right_hip=self._ema(self._prev.right_hip, frame.right_hip),
            left_knee=self._ema(self._prev.left_knee, frame.left_knee),
            right_knee=self._ema(self._prev.right_knee, frame.right_knee),
            left_ankle=self._ema(self._prev.left_ankle, frame.left_ankle),
            right_ankle=self._ema(self._prev.right_ankle, frame.right_ankle),
        )

        self._prev = smoothed
        return smoothed

    def _ema(self, prev: Landmark, current: Landmark) -> Landmark:
        return Landmark(
            x=self.alpha * current.x + (1 - self.alpha) * prev.x,
            y=self.alpha * current.y + (1 - self.alpha) * prev.y,
            z=self.alpha * current.z + (1 - self.alpha) * prev.z,
            visibility=current.visibility,
        )
