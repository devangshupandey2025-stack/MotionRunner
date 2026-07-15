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

    def _resolve_posture(self, jump_result: JumpResult, slide_result: SlideResult) -> tuple[Posture, float, str]:
        if slide_result.active:
            return Posture.SLIDE, slide_result.confidence, slide_result.debug
        if jump_result.active:
            return Posture.JUMP, jump_result.confidence, jump_result.debug
        return Posture.RUNNING, 0.5, "Running"
