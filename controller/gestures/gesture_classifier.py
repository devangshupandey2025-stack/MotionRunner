from utils.config import AppConfig
from vision.pose_frame import PoseFrame
from controller.action import Ability, JumpResult, Lane, LaneResult, PlayerState, Posture, SlideResult
from controller.calibration import CalibrationData
from controller.gestures.lane_detector import LaneDetector
from controller.gestures.jump_detector import JumpDetector
from controller.gestures.slide_detector import SlideDetector
from controller.gestures.hoverboard_detector import HoverboardDetector


class GestureClassifier:
    def __init__(self, config: AppConfig):
        self.config = config
        self.lane = LaneDetector(config)
        self.jump = JumpDetector(config)
        self.slide = SlideDetector(config)
        self.hover = HoverboardDetector(config)
        self._calibration: CalibrationData | None = None
        self._last_lane_result: LaneResult | None = None
        # Adaptive baseline state
        self._adaptive_hip_y: float | None = None
        self._idle_since: float | None = None

    @property
    def has_calibration(self) -> bool:
        return self._calibration is not None

    @property
    def lane_result(self) -> LaneResult | None:
        return self._last_lane_result

    def set_calibration(self, data: CalibrationData):
        self._calibration = data
        self.lane.set_calibration(data)
        self.jump.set_calibration(data)
        self.slide.set_calibration(data)
        self.hover.set_calibration(data)
        # Seed the adaptive baseline from calibration
        self._adaptive_hip_y = data.rest_hip_y
        self._idle_since = None

    def classify(self, pose: PoseFrame) -> PlayerState:
        if not self._calibration:
            return PlayerState(
                lane=Lane.CENTER,
                posture=Posture.RUNNING,
                timestamp=pose.timestamp,
                frame_index=pose.frame_index,
                debug="No calibration",
            )

        lane_result = self.lane.classify(pose)
        self._last_lane_result = lane_result

        if lane_result is None:
            lane_result = LaneResult(Lane.CENTER, 0.0, 0.0)

        slide_result = self.slide.detect(pose)
        jump_result = self.jump.detect(pose)
        hover_result = self.hover.detect(pose)
        posture, posture_confidence, posture_debug = self._resolve_posture(jump_result, slide_result)

        # Update adaptive baseline when player is idle
        if self.config.adaptive_baseline_enabled:
            self._update_adaptive_baseline(pose, jump_result, slide_result)

        abilities = {Ability.HOVERBOARD} if hover_result.active else set()
        ability_confidence = hover_result.confidence if hover_result.active else 0.0

        debug_parts = [
            posture_debug,
            f"Lane={lane_result.direction.name}({lane_result.confidence:.0%})",
            f"Ability={'HOVERBOARD' if hover_result.active else 'NONE'}",
        ]

        return PlayerState(
            lane=lane_result.direction,
            posture=posture,
            abilities=abilities,
            lane_confidence=lane_result.confidence,
            posture_confidence=posture_confidence,
            ability_confidence=ability_confidence,
            timestamp=pose.timestamp,
            frame_index=pose.frame_index,
            lane_result=lane_result,
            jump_result=jump_result,
            slide_result=slide_result,
            hoverboard_result=hover_result,
            debug=" | ".join(debug_parts),
        )

    def _update_adaptive_baseline(self, pose: PoseFrame, jump_result: JumpResult, slide_result: SlideResult):
        """Slowly adapt the standing hip baseline while the player is idle.

        Only updates when the player is clearly not jumping or sliding for
        at least ``adaptive_idle_ms``.  Recomputes and pushes threshold
        lines to the jump and slide detectors each time it updates.
        """
        is_idle = not jump_result.active and not slide_result.active

        if not is_idle:
            self._idle_since = None
            return

        # Start or continue the idle timer
        if self._idle_since is None:
            self._idle_since = pose.timestamp
            return

        idle_ms = (pose.timestamp - self._idle_since) * 1000
        if idle_ms < self.config.adaptive_idle_ms:
            return

        # Player has been idle long enough — update the baseline
        hip_y = pose.hip_center.y
        alpha = self.config.adaptive_baseline_alpha
        self._adaptive_hip_y = alpha * hip_y + (1 - alpha) * self._adaptive_hip_y

        # Recompute threshold lines from the adapted baseline
        cal = self._calibration
        jump_line_y = self._adaptive_hip_y - self.config.jump_line_offset * cal.body_height
        effective_jump_line_y = jump_line_y - self.config.jump_dead_zone * cal.body_height
        duck_line_y = self._adaptive_hip_y + self.config.duck_line_offset * cal.body_height

        self.jump.update_jump_lines(jump_line_y, effective_jump_line_y)
        self.slide.update_duck_line(duck_line_y)

    def _resolve_posture(self, jump_result: JumpResult, slide_result: SlideResult) -> tuple[Posture, float, str]:
        if slide_result.active:
            return Posture.SLIDE, slide_result.confidence, slide_result.debug
        if jump_result.active:
            return Posture.JUMP, jump_result.confidence, jump_result.debug
        return Posture.RUNNING, 0.5, "Running"

