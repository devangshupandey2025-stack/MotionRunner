from __future__ import annotations

from dataclasses import dataclass, replace
import statistics
import time

import cv2

try:
    from mediapipe.python.solutions import hands as mp_hands
except ModuleNotFoundError:
    import mediapipe as mp

    mp_hands = mp.solutions.hands

from controller.action import Ability, Lane, Posture
from input.input_state import InputState
from input.provider import InputProvider
from utils.config import AppConfig
from utils.performance import InferenceScheduler


@dataclass
class HandCalibrationData:
    center_x: float = 0.5


class HandCalibrator:
    def __init__(self, config: AppConfig):
        self.config = config
        self._samples: list[float] = []
        self._start_time: float | None = None
        self._collecting = False
        self._done = False
        self._result: HandCalibrationData | None = None

    @property
    def countdown_remaining(self) -> int:
        if self._done:
            return 0
        if self._start_time is None:
            return self.config.calibration_countdown_s
        elapsed = time.perf_counter() - self._start_time
        remaining = self.config.calibration_countdown_s - int(elapsed)
        return max(0, remaining)

    @property
    def collecting(self) -> bool:
        return self._collecting and not self._done

    @property
    def progress(self) -> float:
        if not self._collecting:
            return 0.0
        return min(1.0, len(self._samples) / max(1, self.config.hand_calibration_frames))

    @property
    def done(self) -> bool:
        return self._done

    @property
    def result(self) -> HandCalibrationData | None:
        return self._result

    def start(self):
        self._samples = []
        self._start_time = time.perf_counter()
        self._collecting = False
        self._done = False
        self._result = None

    def update(self, observation: "HandObservation" | None) -> HandCalibrationData | None:
        if self._done:
            return self._result
        if self._start_time is None:
            return None
        if self.countdown_remaining > 0:
            return None
        if not self._collecting:
            self._collecting = True
        if observation is None:
            return None

        self._samples.append(observation.palm_x)
        if len(self._samples) >= self.config.hand_calibration_frames:
            self._result = HandCalibrationData(center_x=statistics.median(self._samples))
            self._done = True
            return self._result
        return None


@dataclass
class HandObservation:
    palm_x: float
    open_palm: bool
    pinch_active: bool
    confidence: float
    landmarks: list[tuple[float, float]]
    timestamp: float
    frame_index: int


class HandGestureInterpreter:
    def __init__(self, config: AppConfig):
        self.config = config
        self._pinch_started_at: float | None = None

    def reset(self):
        self._pinch_started_at = None

    def interpret(
        self,
        observation: HandObservation | None,
        calibration: HandCalibrationData | None,
        calibrated: bool,
    ) -> InputState:
        if observation is None:
            self._pinch_started_at = None
            return InputState(provider_name="hand", tracking=False, calibrated=calibrated, debug="Hand not found")

        if not calibrated or calibration is None:
            self._pinch_started_at = None
            return InputState(
                provider_name="hand",
                tracking=True,
                calibrated=False,
                timestamp=observation.timestamp,
                frame_index=observation.frame_index,
                debug="Calibrating hand",
                gesture_label="HAND",
                landmarks=list(observation.landmarks),
            )

        lane = Lane.CENTER
        lane_confidence = 0.0
        gesture_label = "HAND"
        if observation.open_palm:
            gesture_label = "OPEN_PALM"
            offset = (observation.palm_x - calibration.center_x) / max(self.config.hand_horizontal_range, 1e-6)
            if offset <= -self.config.hand_dead_zone:
                lane = Lane.LEFT
                lane_confidence = min(1.0, abs(offset))
            elif offset >= self.config.hand_dead_zone:
                lane = Lane.RIGHT
                lane_confidence = min(1.0, abs(offset))
            else:
                lane_confidence = max(0.0, 1.0 - (abs(offset) / max(self.config.hand_dead_zone, 1e-6)))

        abilities = set()
        ability_confidence = 0.0
        if observation.pinch_active:
            gesture_label = "PINCH"
            if self._pinch_started_at is None:
                self._pinch_started_at = observation.timestamp
            elapsed_ms = (observation.timestamp - self._pinch_started_at) * 1000.0
            ability_confidence = min(1.0, elapsed_ms / max(1, self.config.hoverboard_hold_ms))
            if elapsed_ms >= self.config.hoverboard_hold_ms:
                abilities.add(Ability.HOVERBOARD)
        else:
            self._pinch_started_at = None

        return InputState(
            provider_name="hand",
            tracking=True,
            calibrated=True,
            lane=lane,
            posture=Posture.RUNNING,
            abilities=abilities,
            lane_confidence=lane_confidence,
            posture_confidence=0.5,
            ability_confidence=ability_confidence,
            timestamp=observation.timestamp,
            frame_index=observation.frame_index,
            debug=f"Hand={gesture_label} Lane={lane.name}",
            gesture_label=gesture_label,
            landmarks=list(observation.landmarks),
        )


class HandProvider(InputProvider):
    name = "hand"

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.calibrator = HandCalibrator(config)
        self.interpreter = HandGestureInterpreter(config)
        self._hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=config.hand_detection_confidence,
            min_tracking_confidence=config.hand_tracking_confidence,
        )
        self._frame_index = 0
        self._scheduler = InferenceScheduler(config.processing_mode)
        self._last_observation: HandObservation | None = None

    def reset(self):
        self.calibrator = HandCalibrator(self.config)
        self.calibrator.start()
        self.interpreter.reset()
        self.current_pose = None
        self.hand_landmarks = ()
        self._frame_index = 0
        self._scheduler.reset()
        self._last_observation = None

    def update(self, frame) -> InputState:
        self._frame_index += 1
        preprocess_start = time.perf_counter()
        processed_frame = self._scheduler.should_process()
        observation = None
        self.current_pose = None

        if processed_frame:
            working = frame
            if self.config.processing_width > 0 and self.config.processing_height > 0:
                working = cv2.resize(
                    frame,
                    (self.config.processing_width, self.config.processing_height),
                    interpolation=cv2.INTER_LINEAR,
                )
            rgb = cv2.cvtColor(working, cv2.COLOR_BGR2RGB)
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0
            inference_start = time.perf_counter()
            results = self._hands.process(rgb)
            inference_ms = (time.perf_counter() - inference_start) * 1000.0
            self._scheduler.record_inference(inference_ms)

            if results.multi_hand_landmarks:
                landmarks = results.multi_hand_landmarks[0].landmark
                observation = self._to_observation(landmarks)
                self._last_observation = observation
                self.hand_landmarks = tuple(observation.landmarks)
            else:
                self._last_observation = None
                self.hand_landmarks = ()
        else:
            preprocess_ms = (time.perf_counter() - preprocess_start) * 1000.0
            inference_ms = 0.0
            if self._last_observation is not None:
                observation = replace(
                    self._last_observation,
                    timestamp=time.perf_counter(),
                    frame_index=self._frame_index,
                )
                self.hand_landmarks = tuple(observation.landmarks)
            else:
                self.hand_landmarks = ()

        classify_start = time.perf_counter()
        calibration = self.calibrator.update(observation)
        calibrated = self.calibrator.done or calibration is not None
        state = self.interpreter.interpret(observation, self.calibrator.result or calibration, calibrated)
        classify_ms = (time.perf_counter() - classify_start) * 1000.0
        self.perf_stats.preprocess_ms = preprocess_ms
        self.perf_stats.inference_ms = inference_ms
        self.perf_stats.classify_ms = classify_ms
        self.perf_stats.processed_frame = processed_frame
        self.perf_stats.processing_mode = self._scheduler.active_mode_name
        self.perf_stats.auto_switches = self._scheduler.auto_switches
        return state

    def _to_observation(self, landmarks) -> HandObservation:
        timestamp = time.perf_counter()
        points = [(lm.x, lm.y) for lm in landmarks]
        palm_x = sum(landmarks[index].x for index in (0, 5, 9, 13, 17)) / 5.0
        thumb_tip = landmarks[4]
        index_tip = landmarks[8]
        index_pip = landmarks[6]
        middle_tip = landmarks[12]
        middle_pip = landmarks[10]
        ring_tip = landmarks[16]
        ring_pip = landmarks[14]
        pinky_tip = landmarks[20]
        pinky_pip = landmarks[18]

        pinch_active = ((thumb_tip.x - index_tip.x) ** 2 + (thumb_tip.y - index_tip.y) ** 2) ** 0.5 < self.config.hand_pinch_threshold
        open_palm = (
            index_tip.y < index_pip.y
            and middle_tip.y < middle_pip.y
            and ring_tip.y < ring_pip.y
            and pinky_tip.y < pinky_pip.y
        )

        return HandObservation(
            palm_x=palm_x,
            open_palm=open_palm,
            pinch_active=pinch_active,
            confidence=1.0,
            landmarks=points,
            timestamp=timestamp,
            frame_index=self._frame_index,
        )
