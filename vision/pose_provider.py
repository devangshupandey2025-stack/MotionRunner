import time

from utils.performance import InferenceScheduler
from controller.gestures.gesture_classifier import GestureClassifier
from input.adapters import player_state_to_input_state
from input.input_state import InputState
from input.provider import InputProvider
from utils.config import AppConfig
from vision.pose_smoother import EMAFilter
from vision.pose_tracker import PoseTracker
from controller.calibration import Calibrator


class PoseProvider(InputProvider):
    name = "pose"

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.tracker = PoseTracker(config)
        self.smoother = EMAFilter(config.smoothing_alpha)
        self.calibrator = Calibrator(config)
        self.classifier = GestureClassifier(config)
        self._scheduler = InferenceScheduler(config.processing_mode)
        self._last_detected_pose = None
        self._last_smoothed_pose = None

    def reset(self):
        self.smoother = EMAFilter(self.config.smoothing_alpha)
        self.calibrator = Calibrator(self.config)
        self.classifier = GestureClassifier(self.config)
        self.calibrator.start()
        self.current_pose = None
        self.hand_landmarks = ()
        self._scheduler.reset()
        self._last_detected_pose = None
        self._last_smoothed_pose = None

    def update(self, frame) -> InputState:
        preprocess_start = time.perf_counter()
        processed_frame = self._scheduler.should_process()

        if processed_frame:
            rgb = self.tracker.prepare_input(frame)
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0
            inference_start = time.perf_counter()
            raw_pose = self.tracker.detect_rgb(rgb)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            self._scheduler.record_inference(inference_ms)
            self._last_detected_pose = raw_pose
            self.current_pose = self.smoother.update(raw_pose)
            self._last_smoothed_pose = self.current_pose
        else:
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0
            inference_ms = 0.0
            now = time.perf_counter()
            self.current_pose = self.tracker.reuse(self._last_smoothed_pose, now)

        self.hand_landmarks = ()
        classify_start = time.perf_counter()

        if self.current_pose is None:
            state = InputState(
                provider_name=self.name,
                tracking=False,
                calibrated=self.calibrator.done,
                debug="Pose not found",
            )
            classify_ms = (time.perf_counter() - classify_start) * 1000.0
            self._update_perf(preprocess_ms, inference_ms, classify_ms, processed_frame)
            return state

        if not self.calibrator.done:
            cal_result = self.calibrator.update(self.current_pose)
            if cal_result:
                self.classifier.set_calibration(cal_result)
            state = InputState(
                provider_name=self.name,
                tracking=True,
                calibrated=self.calibrator.done,
                timestamp=self.current_pose.timestamp,
                frame_index=self.current_pose.frame_index,
                debug="Calibrating pose",
            )
            classify_ms = (time.perf_counter() - classify_start) * 1000.0
            self._update_perf(preprocess_ms, inference_ms, classify_ms, processed_frame)
            return state

        player_state = self.classifier.classify(self.current_pose)
        state = player_state_to_input_state(
            player_state,
            provider_name=self.name,
            tracking=True,
            calibrated=True,
            gesture_label=player_state.primary_action.name,
        )
        classify_ms = (time.perf_counter() - classify_start) * 1000.0
        self._update_perf(preprocess_ms, inference_ms, classify_ms, processed_frame)
        return state

    def _update_perf(self, preprocess_ms: float, inference_ms: float, classify_ms: float, processed_frame: bool):
        self.perf_stats.preprocess_ms = preprocess_ms
        self.perf_stats.inference_ms = inference_ms
        self.perf_stats.classify_ms = classify_ms
        self.perf_stats.processed_frame = processed_frame
        self.perf_stats.processing_mode = self._scheduler.active_mode_name
        self.perf_stats.auto_switches = self._scheduler.auto_switches
