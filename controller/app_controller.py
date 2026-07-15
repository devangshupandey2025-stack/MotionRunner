from enum import Enum, auto

from utils.config import AppConfig
from vision.pose_tracker import PoseTracker
from vision.pose_frame import PoseFrame
from vision.pose_smoother import EMAFilter
from controller.calibration import Calibrator
from controller.action import Lane, PlayerState, Posture
from controller.gestures.gesture_classifier import GestureClassifier


class AppState(Enum):
    INITIALIZING = auto()
    CALIBRATING = auto()
    TRACKING = auto()
    LOST = auto()
    ERROR = auto()


class AppController:
    def __init__(self, config: AppConfig):
        self.config = config
        self.state = AppState.INITIALIZING
        self.calibrator = Calibrator(config)
        self.tracker = PoseTracker(config)
        self.smoother = EMAFilter(config.smoothing_alpha)
        self.classifier = GestureClassifier(config)
        self.last_result = PlayerState(Lane.CENTER, Posture.RUNNING, debug="Starting")
        self.pose: PoseFrame | None = None
        self._error_msg = ""
        self._lost_frame_count = 0

    @property
    def error_msg(self) -> str:
        return self._error_msg

    def update(self, frame):
        if self.state == AppState.INITIALIZING:
            self.state = AppState.CALIBRATING
            self.calibrator.start()
            return

        if self.state == AppState.ERROR:
            return

        try:
            raw_pose = self.tracker.detect(frame)
            self.pose = self.smoother.update(raw_pose)

            if self.state == AppState.CALIBRATING:
                cal_result = self.calibrator.update(self.pose)
                if cal_result:
                    self.classifier.set_calibration(cal_result)
                    self.state = AppState.TRACKING

            elif self.state in (AppState.TRACKING, AppState.LOST):
                if self.pose:
                    self._lost_frame_count = 0
                    if self.state == AppState.LOST:
                        self.state = AppState.TRACKING
                    self.last_result = self.classifier.classify(self.pose)
                else:
                    self._lost_frame_count += 1
                    if self._lost_frame_count >= self.config.lost_frame_threshold:
                        self.state = AppState.LOST

        except Exception as e:
            self.state = AppState.ERROR
            self._error_msg = str(e)
