from dataclasses import dataclass
from .landmarks import Landmark, angle_between


@dataclass
class PoseFrame:
    timestamp: float
    frame_index: int
    fps: float

    nose: Landmark
    left_eye: Landmark
    right_eye: Landmark
    left_shoulder: Landmark
    right_shoulder: Landmark
    left_elbow: Landmark
    right_elbow: Landmark
    left_wrist: Landmark
    right_wrist: Landmark
    left_hip: Landmark
    right_hip: Landmark
    left_knee: Landmark
    right_knee: Landmark
    left_ankle: Landmark
    right_ankle: Landmark

    @property
    def hip_center(self) -> Landmark:
        return self.left_hip.midpoint(self.right_hip)

    @property
    def shoulder_center(self) -> Landmark:
        return self.left_shoulder.midpoint(self.right_shoulder)

    @property
    def body_center(self) -> Landmark:
        return self.shoulder_center.midpoint(self.hip_center)

    @property
    def shoulder_width(self) -> float:
        return self.left_shoulder.distance_to(self.right_shoulder)

    @property
    def body_height(self) -> float:
        return self.nose.distance_to(self.hip_center)

    @property
    def left_knee_angle(self) -> float:
        return angle_between(self.left_hip, self.left_knee, self.left_ankle)

    @property
    def right_knee_angle(self) -> float:
        return angle_between(self.right_hip, self.right_knee, self.right_ankle)

    @property
    def min_knee_angle(self) -> float:
        return min(self.left_knee_angle, self.right_knee_angle)
