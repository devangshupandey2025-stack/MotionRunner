import time
import winsound
from enum import Enum, auto

from utils.config import AppConfig
from controller.calibration import Calibrator, CalibrationData, CalibrationQuality
from vision.pose_frame import PoseFrame


class WizardState(Enum):
    WELCOME = auto()
    POSITIONING = auto()
    COUNTDOWN = auto()
    COLLECTING = auto()
    QUALITY_CHECK = auto()
    PREVIEW = auto()
    DONE = auto()


class CalibrationWizard:
    def __init__(self, config: AppConfig):
        self.config = config
        self.calibrator = Calibrator(config)
        self.state = WizardState.WELCOME
        self.quality: CalibrationQuality | None = None
        
        self._state_start_time = time.perf_counter()
        self._last_countdown_sec = -1
        self._pose_stable_start = 0.0
        self.preview_jump_detected = False

    @property
    def calibration_result(self) -> CalibrationData | None:
        return self.calibrator.result

    def reset(self):
        self.calibrator.start()
        self._transition(WizardState.WELCOME)
        self.quality = None
        self._last_countdown_sec = -1
        self._pose_stable_start = 0.0
        self.preview_jump_detected = False

    def update(self, pose: PoseFrame | None) -> WizardState:
        now = time.perf_counter()
        elapsed = now - self._state_start_time

        if self.state == WizardState.WELCOME:
            if elapsed > 2.0:  # Briefly show welcome message
                self._transition(WizardState.POSITIONING)
                
        elif self.state == WizardState.POSITIONING:
            if elapsed > self.config.calibration_timeout_s:
                self.quality = CalibrationQuality(False, False, False, False)
                self._transition(WizardState.QUALITY_CHECK)
                return self.state

            if pose is not None and self._is_pose_visible(pose):
                if self._pose_stable_start == 0.0:
                    self._pose_stable_start = now
                elif now - self._pose_stable_start >= self.config.calibration_positioning_stable_ms / 1000.0:
                    self._transition(WizardState.COUNTDOWN)
                    self.calibrator.start()  # Prepares the calibrator
            else:
                self._pose_stable_start = 0.0
                
        elif self.state == WizardState.COUNTDOWN:
            remaining = self.calibrator.countdown_remaining
            if remaining != self._last_countdown_sec:
                self._last_countdown_sec = remaining
                if remaining > 0 and self.config.calibration_audio_enabled:
                    self._beep(winsound.MB_ICONASTERISK)
            
            # The calibrator updates its own countdown_remaining logic.
            # Wait until it reaches 0
            if remaining <= 0:
                if self.config.calibration_audio_enabled:
                    self._beep(winsound.MB_OK)
                self._transition(WizardState.COLLECTING)
                
        elif self.state == WizardState.COLLECTING:
            result = self.calibrator.update(pose)
            if self.calibrator.done:
                if result:
                    self.quality = result.quality_report(self.config)
                    if self.quality.overall_ok:
                        self._transition(WizardState.PREVIEW)
                    else:
                        self._transition(WizardState.QUALITY_CHECK)
                else:
                    self.quality = CalibrationQuality(False, False, False, False)
                    self._transition(WizardState.QUALITY_CHECK)
                    
        elif self.state == WizardState.QUALITY_CHECK:
            # We stay here until user presses retry or accepts
            pass
            
        elif self.state == WizardState.PREVIEW:
            # Check for jump to flash green
            if pose and self.calibrator.result:
                hip_y = pose.hip_center.y
                if hip_y < self.calibrator.result.jump_line_y:
                    if not self.preview_jump_detected:
                        self.preview_jump_detected = True
                        if self.config.calibration_audio_enabled:
                            self._beep(winsound.MB_ICONASTERISK)
            
            if elapsed >= self.config.calibration_preview_duration_s:
                if self.config.calibration_audio_enabled:
                    self._beep(winsound.MB_OK)
                self._transition(WizardState.DONE)
                
        return self.state
        
    def retry(self):
        self.reset()
        self._transition(WizardState.POSITIONING)
        
    def advance_from_preview(self):
        if self.state == WizardState.PREVIEW:
            if self.config.calibration_audio_enabled:
                self._beep(winsound.MB_OK)
            self._transition(WizardState.DONE)

    def _transition(self, new_state: WizardState):
        self.state = new_state
        self._state_start_time = time.perf_counter()

    def _is_pose_visible(self, pose: PoseFrame) -> bool:
        return (
            pose.left_shoulder.visibility > self.config.visibility_threshold
            and pose.right_shoulder.visibility > self.config.visibility_threshold
            and pose.left_hip.visibility > self.config.visibility_threshold
            and pose.right_hip.visibility > self.config.visibility_threshold
        )
        
    def _beep(self, sound_type):
        try:
            winsound.MessageBeep(sound_type)
        except Exception:
            pass
