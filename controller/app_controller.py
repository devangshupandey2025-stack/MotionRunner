from enum import Enum, auto

from controller.action import Lane, PlayerState, Posture
from input.input_state import InputState
from utils.config import AppConfig, InputMode
from vision.hand_provider import HandProvider
from vision.pose_provider import PoseProvider
from utils.performance import PipelineStats

from controller.position_tracker import PositionTracker
from controller.lane_tracker import LaneTracker
from controller.state_manager import StateManager


class AppState(Enum):
    INITIALIZING = auto()
    CALIBRATING = auto()
    TRACKING = auto()
    LOST = auto()
    ERROR = auto()


class AppController:
    def __init__(self, config: AppConfig):
        self.config = config
        self.input_mode = config.input_mode
        self.state = AppState.INITIALIZING
        self.provider = self._create_provider()
        self.calibrator = self.provider.calibrator
        self.wizard = getattr(self.provider, "wizard", None)
        self.last_input = InputState(provider_name=self.provider.name, debug="Starting")
        self.last_result = PlayerState(Lane.CENTER, Posture.RUNNING, debug="Starting")
        self.pose = None
        self.hand_landmarks: tuple[tuple[float, float], ...] = ()
        self.perf_stats = PipelineStats()
        
        self.position_tracker = PositionTracker(config)
        self.lane_tracker = LaneTracker(config)
        self.state_manager = StateManager(config)
        self.latest_tracking_result = None
        self.events_this_frame = []
        
        self._error_msg = ""
        self._lost_frame_count = 0
        self._preloaded_cal = None

    def inject_calibration(self, cal_data):
        self._preloaded_cal = cal_data

    @property
    def error_msg(self) -> str:
        return self._error_msg

    def update(self, frame):
        if self.state == AppState.INITIALIZING:
            self.provider.reset()
            self.calibrator = self.provider.calibrator
            self.wizard = getattr(self.provider, "wizard", None)
            
            if self._preloaded_cal:
                self.calibrator._result = self._preloaded_cal
                self.calibrator._done = True
                if self.wizard:
                    self.wizard.state = WizardState.DONE
                if hasattr(self.provider, 'classifier'):
                    self.provider.classifier.set_calibration(self._preloaded_cal)
                self.lane_tracker.set_calibration(self._preloaded_cal)
                self.state = AppState.TRACKING
                return
                
            self.state = AppState.CALIBRATING
            return

        if self.state == AppState.ERROR:
            return

        try:
            self.last_input = self.provider.update(frame)
            self.calibrator = self.provider.calibrator
            self.wizard = getattr(self.provider, "wizard", None)
            self.pose = self.provider.current_pose
            self.hand_landmarks = tuple(self.provider.hand_landmarks)
            self.perf_stats.preprocess_ms = self.provider.perf_stats.preprocess_ms
            self.perf_stats.inference_ms = self.provider.perf_stats.inference_ms
            self.perf_stats.classify_ms = self.provider.perf_stats.classify_ms
            self.perf_stats.processed_frame = self.provider.perf_stats.processed_frame
            self.perf_stats.processing_mode = self.provider.perf_stats.processing_mode
            self.perf_stats.auto_switches = self.provider.perf_stats.auto_switches

            if self.state == AppState.CALIBRATING:
                if self.last_input.calibrated:
                    self.last_result = self.last_input.to_player_state()
                    # Feed calibration to the V2 lane tracking pipeline
                    cal = self.calibrator.result
                    if cal:
                        self.lane_tracker.set_calibration(cal)
                    self.state = AppState.TRACKING
                return

            if self.state in (AppState.TRACKING, AppState.LOST):
                self.events_this_frame.clear()
                
                if self.last_input.tracking:
                    self._lost_frame_count = 0
                    if self.state == AppState.LOST:
                        self.state = AppState.TRACKING
                        self.state_manager.reset()
                    self.last_result = self.last_input.to_player_state()
                    
                    if self.pose:
                        self.latest_tracking_result = self.position_tracker.track(self.pose)
                        lane_event = self.lane_tracker.track(self.latest_tracking_result)
                        
                        if lane_event:
                            state_result = self.state_manager.process_event(lane_event)
                            if state_result:
                                self.events_this_frame.append(state_result) # Tuple of (previous_game_lane, desired_game_lane)
                else:
                    self._lost_frame_count += 1
                    if self._lost_frame_count >= self.config.lost_frame_threshold:
                        self.state = AppState.LOST

        except Exception as exc:
            self.state = AppState.ERROR
            self._error_msg = str(exc)

    def _create_provider(self):
        if self.input_mode == InputMode.HAND:
            return HandProvider(self.config)
        return PoseProvider(self.config)
