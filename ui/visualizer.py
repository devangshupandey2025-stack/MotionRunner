import time

import cv2
import numpy as np

from utils.config import AppConfig
from utils.config import ControlMode, InputMode
from vision.pose_frame import PoseFrame
from controller.action import Ability, Action, Lane, PlayerState, Posture
from controller.calibration_wizard import WizardState
from ui.theme import DEFAULT_THEME, GUIDE_THEME
from ui.hud import HUD
from ui.perf_overlay import PerfOverlay


SKELETON = [
    ("left_eye", "nose"),
    ("right_eye", "nose"),
    ("left_eye", "left_shoulder"),
    ("right_eye", "right_shoulder"),
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]

LANDMARK_KEYS = [
    "nose", "left_eye", "right_eye",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
]

ACTION_COLORS = {
    Action.RUNNING: (200, 200, 200),
    Action.LEFT: (0, 200, 0),
    Action.RIGHT: (0, 200, 0),
    Action.JUMP: (0, 255, 255),
    Action.SLIDE: (255, 100, 0),
    Action.HOVERBOARD: (255, 0, 255),
}

STATE_COLORS = {
    "INITIALIZING": DEFAULT_THEME.state_initializing,
    "CALIBRATING": DEFAULT_THEME.state_calibrating,
    "TRACKING": DEFAULT_THEME.state_tracking,
    "LOST": DEFAULT_THEME.state_lost,
    "ERROR": DEFAULT_THEME.state_error,
}


class Visualizer:
    def __init__(self, config: AppConfig):
        self.config = config
        self.theme = DEFAULT_THEME
        self.guide = GUIDE_THEME
        self.hud = HUD(config)
        self.perf_overlay = PerfOverlay(config)
        self._disp_lane_conf = 0.0
        self._disp_posture_conf = 0.0
        self._disp_ability_conf = 0.0
        self._smooth_alpha = 0.15

    def draw(
        self,
        frame,
        pose: PoseFrame | None,
        result: PlayerState | None,
        app_state,
        calibrator,
        wizard=None,
        keyboard=None,
        keyboard_enabled: bool = False,
        perf_overlay_enabled: bool = False,
        control_mode: ControlMode | None = None,
        input_state=None,
        input_mode: InputMode | None = None,
        hand_landmarks: tuple[tuple[float, float], ...] = (),
        perf_stats=None,
    ) -> np.ndarray:
        h, w = frame.shape[:2]
        show_sidebar = self.config.show_sidebar
        show_overlays = self.config.show_pose_overlay
        sw = self.config.sidebar_width if show_sidebar else 0
        if show_sidebar:
            canvas = np.full((h, w + sw, 3), self.theme.sidebar_bg, dtype=np.uint8)
            canvas[:h, :w] = frame
        else:
            canvas = frame.copy()

        frame_view = canvas[:h, :w]

        if pose and show_overlays:
            self._draw_lane_zones(frame_view, pose, w, h)
            self._draw_skeleton(frame_view, pose, w, h)
            self._draw_landmarks(frame_view, pose, w, h)
            self._draw_lane_guides(frame_view, pose, w, h)
            if self.config.show_guides:
                self._draw_guide_lines(frame_view, pose, calibrator, w, h)
            self._draw_hip_center(frame_view, pose, w, h)
        elif hand_landmarks and self.config.show_hand_landmarks:
            self._draw_hand_landmarks(frame_view, hand_landmarks, w, h)

        is_tracking = input_state.tracking if input_state else False
        has_calibrated = calibrator.done if calibrator else False
        self.hud.draw(frame_view, result, is_tracking, has_calibrated)
        
        if perf_overlay_enabled:
            self.perf_overlay.draw(frame_view, perf_stats)

        if wizard and wizard.state != WizardState.DONE:
            self._draw_wizard_overlay(frame_view, wizard, pose, w, h)

        if show_sidebar:
            sidebar = canvas[:h, w:]
            self._draw_sidebar(sidebar, result, app_state, calibrator, pose, keyboard, keyboard_enabled, control_mode, input_state, input_mode, perf_stats)

        return canvas

    def _draw_wizard_overlay(self, canvas, wizard, pose: PoseFrame | None, w, h):
        state = wizard.state
        
        # Darken background slightly
        overlay = canvas.copy()
        cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.4, canvas, 0.6, 0, canvas)
        
        if state == WizardState.WELCOME:
            self._text(canvas, "CALIBRATION WIZARD", (w // 2, h // 2 - 30), self.theme.highlight, 1.0, center=True)
            self._text(canvas, "Stand in frame, feet shoulder-width apart", (w // 2, h // 2 + 10), self.theme.text, 0.6, center=True)
            
        elif state == WizardState.POSITIONING:
            self._text(canvas, "POSITIONING", (w // 2, 40), self.theme.highlight, 0.8, center=True)
            self._text(canvas, "Ensure full body is visible", (w // 2, 70), self.theme.text, 0.6, center=True)
            
            if pose:
                critical_lms = [
                    pose.left_shoulder, pose.right_shoulder,
                    pose.left_hip, pose.right_hip,
                    pose.left_ankle, pose.right_ankle
                ]
                for lm in critical_lms:
                    cx, cy = int(lm.x * w), int(lm.y * h)
                    color = self.theme.status_ok if lm.visibility > self.config.visibility_threshold else self.theme.status_fail
                    cv2.circle(canvas, (cx, cy), 8, color, -1)
                    
        elif state == WizardState.COUNTDOWN:
            remaining = wizard.calibrator.countdown_remaining
            self._text(canvas, str(remaining), (w // 2, h // 2), self.theme.highlight, 4.0, center=True)
            
        elif state == WizardState.COLLECTING:
            self._text(canvas, "COLLECTING", (w // 2, 40), self.theme.highlight, 0.8, center=True)
            prog = wizard.calibrator.progress
            bar_w = int(w * 0.6)
            bar_x = (w - bar_w) // 2
            bar_y = h - 60
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + 15), self.theme.bar_bg, -1)
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + int(bar_w * prog), bar_y + 15), self.theme.bar_fg, -1)
            
        elif state == WizardState.QUALITY_CHECK:
            self._text(canvas, "CALIBRATION FAILED", (w // 2, 40), self.theme.error, 0.8, center=True)
            if wizard.quality:
                q = wizard.quality
                y = 100
                checks = [
                    ("Shoulder width", q.shoulder_width_ok),
                    ("Body height", q.body_height_ok),
                    ("Hip centered", q.hip_centered),
                ]
                for label, ok in checks:
                    color = self.theme.status_ok if ok else self.theme.status_fail
                    self._text(canvas, f"[{'OK' if ok else 'FAIL'}] {label}", (w // 2, y), color, 0.6, center=True)
                    y += 30
            self._text(canvas, "Press R to retry", (w // 2, h - 50), self.theme.highlight, 0.6, center=True)
            
        elif state == WizardState.PREVIEW:
            self._text(canvas, "PREVIEW", (w // 2, 40), self.theme.highlight, 0.8, center=True)
            self._text(canvas, "Jump now to test!", (w // 2, 70), self.theme.warning, 0.7, center=True)
            self._text(canvas, "Press any key to finish", (w // 2, h - 30), self.theme.text, 0.5, center=True)
            
            cal = wizard.calibrator.result
            if cal:
                jump_y = int(cal.jump_line_y * h)
                rest_y = int(cal.rest_hip_y * h)
                duck_y = int(cal.duck_line_y * h)
                
                j_color = self.guide.jump_active if wizard.preview_jump_detected else self.guide.jump
                j_thick = 3 if wizard.preview_jump_detected else 2
                
                cv2.line(canvas, (0, jump_y), (w, jump_y), j_color, j_thick)
                cv2.putText(canvas, "JUMP", (w - 65, jump_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, j_color, j_thick)
                
                cv2.line(canvas, (0, rest_y), (w, rest_y), self.guide.waist, 2)
                cv2.putText(canvas, "WAIST", (w - 65, rest_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.guide.waist, 2)
                
                cv2.line(canvas, (0, duck_y), (w, duck_y), self.guide.duck, 2)
                cv2.putText(canvas, "DUCK", (w - 65, duck_y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.guide.duck, 2)

    def _draw_lane_zones(self, canvas, pose: PoseFrame, w, h):
        third = w // 3
        x = pose.body_center.x
        if x < 1 / 3:
            x1, x2 = 0, third
        elif x > 2 / 3:
            x1, x2 = third * 2, w
        else:
            x1, x2 = third, third * 2

        overlay = canvas.copy()
        cv2.rectangle(overlay, (x1, 0), (x2, h), self.theme.lane_zone, -1)
        cv2.addWeighted(overlay, 0.12, canvas, 0.88, 0, canvas)

    def _draw_skeleton(self, canvas, pose: PoseFrame, w, h):
        for a_name, b_name in SKELETON:
            a = getattr(pose, a_name)
            b = getattr(pose, b_name)
            if a.visibility < self.config.visibility_threshold or b.visibility < self.config.visibility_threshold:
                continue
            pt1 = (int(a.x * w), int(a.y * h))
            pt2 = (int(b.x * w), int(b.y * h))
            cv2.line(canvas, pt1, pt2, self.theme.bone, 2)

    def _draw_landmarks(self, canvas, pose: PoseFrame, w, h):
        for key in LANDMARK_KEYS:
            lm = getattr(pose, key)
            if lm.visibility < self.config.visibility_threshold:
                continue
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(canvas, (cx, cy), 4, self.theme.landmark, -1)

    def _draw_hand_landmarks(self, canvas, hand_landmarks, w, h):
        for x, y in hand_landmarks:
            cv2.circle(canvas, (int(x * w), int(y * h)), 5, self.theme.landmark, -1)

    def _draw_lane_guides(self, canvas, pose: PoseFrame, w, h):
        cx = int(pose.body_center.x * w)
        cv2.line(canvas, (cx, 0), (cx, h), self.theme.lane_line, 2)

        third = w // 3
        cv2.line(canvas, (third, 0), (third, h), self.theme.lane_boundary, 1)
        cv2.line(canvas, (third * 2, 0), (third * 2, h), self.theme.lane_boundary, 1)

    def _draw_guide_lines(self, canvas, pose: PoseFrame, calibrator, w, h):
        if not calibrator:
            return

        if not calibrator.done:
            if pose:
                live_y = int(pose.hip_center.y * h)
                cv2.line(canvas, (0, live_y), (w, live_y), self.guide.waist_live, 2)
                cv2.putText(canvas, "WAIST (live)", (w - 120, live_y - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.guide.waist_live, 1)
            return

        cal = calibrator.result
        rest_y = int(cal.rest_hip_y * h)
        jump_y = int((cal.rest_hip_y - self.config.jump_line_offset * cal.body_height) * h)
        duck_y = int((cal.rest_hip_y + self.config.duck_line_offset * cal.body_height) * h)

        hip_y = pose.hip_center.y if pose else None

        j_active = hip_y is not None and hip_y < cal.rest_hip_y - self.config.jump_line_offset * cal.body_height
        j_color = self.guide.jump_active if j_active else self.guide.jump
        j_thick = 2 if j_active else 1
        cv2.line(canvas, (0, jump_y), (w, jump_y), j_color, j_thick)
        cv2.putText(canvas, "JUMP", (w - 55, jump_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, j_color, j_thick)

        cv2.line(canvas, (0, rest_y), (w, rest_y), self.guide.waist, 2)
        cv2.putText(canvas, "WAIST", (w - 60, rest_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.guide.waist, 1)

        d_active = hip_y is not None and hip_y > cal.rest_hip_y + self.config.duck_line_offset * cal.body_height
        d_color = self.guide.duck_active if d_active else self.guide.duck
        d_thick = 2 if d_active else 1
        cv2.line(canvas, (0, duck_y), (w, duck_y), d_color, d_thick)
        cv2.putText(canvas, "DUCK", (w - 60, duck_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, d_color, d_thick)

    def _draw_hip_center(self, canvas, pose: PoseFrame, w, h):
        hc = pose.hip_center
        if hc.visibility < self.config.visibility_threshold:
            return
        cx, cy = int(hc.x * w), int(hc.y * h)

        cv2.circle(canvas, (cx, cy), 8, self.theme.hip_center_ring, 2)
        cv2.circle(canvas, (cx, cy), 4, self.theme.hip_center, -1)

        label = self._lane_label(pose)
        (tw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        lx = min(max(cx - tw // 2, 5), w - tw - 5)
        cv2.putText(canvas, label, (lx, cy - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.theme.hip_center, 1)

    def _lane_label(self, pose):
        x = pose.body_center.x
        if x < 1 / 3:
            return "<- LEFT"
        if x > 2 / 3:
            return "RIGHT ->"
        return "CENTER"

    def _draw_action_tag(self, canvas, result, w):
        if result is None:
            return
        color = ACTION_COLORS.get(result.primary_action, self.theme.text)
        label = result.primary_action.name
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        x, y = 10, 30
        cv2.rectangle(canvas, (x - 4, y - th - 4), (x + tw + 4, y + 6), (0, 0, 0, 180), -1)
        cv2.putText(canvas, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

    def _draw_sidebar(self, sidebar, result, app_state, calibrator, pose, keyboard, keyboard_enabled, control_mode, input_state, input_mode, perf_stats):
        sw = sidebar.shape[1]
        y = 20

        preset = getattr(self.config, "active_preset", "")
        header = f"MOTIONRUNNER - {preset}" if preset else "MOTIONRUNNER"
        self._text(sidebar, header, (sw // 2, y), self.theme.highlight, 0.55, center=True)
        y += 35
        self._hr(sidebar, y, sw)
        y += 25

        state_color = STATE_COLORS.get(app_state.name, self.theme.text)
        cv2.circle(sidebar, (20, y - 4), 5, state_color, -1)
        self._text(sidebar, app_state.name, (35, y), self.theme.text, 0.55)
        y += 25
        if input_mode:
            self._text(sidebar, f"Input: {input_mode.name}", (15, y), self.theme.highlight, 0.45)
            y += 20
        if input_state and input_state.gesture_label:
            self._text(sidebar, f"Gesture: {input_state.gesture_label}", (15, y), self.theme.text, 0.42)
            y += 18
        self._hr(sidebar, y, sw)
        y += 20

        if calibrator:
            self._text(sidebar, "Calibration:", (15, y), self.theme.dim, 0.5)
            y += 18
            if not calibrator.done:
                countdown = calibrator.countdown_remaining
                if countdown > 0:
                    self._text(sidebar, f"  Stand naturally... {countdown}", (15, y), self.theme.warning, 0.55)
                elif calibrator.collecting:
                    prog = calibrator.progress
                    bar_w = sw - 30
                    fill = int(bar_w * prog)
                    cv2.rectangle(sidebar, (15, y - 2), (15 + bar_w, y + 10), self.theme.bar_bg, -1)
                    cv2.rectangle(sidebar, (15, y - 2), (15 + fill, y + 10), self.theme.bar_fg, -1)
                    self._text(sidebar, f"{int(prog * 100)}%", (15, y + 25), self.theme.text, 0.45)
                    y += 30
                y += 5
            else:
                self._text(sidebar, "  Done", (15, y), self.theme.success, 0.5)
                y += 25
        else:
            y += 5

        if app_state.name in ("TRACKING", "LOST") and result:
            y = self._draw_action_panel(sidebar, result, y, sw)

        y = self._draw_keyboard_panel(sidebar, keyboard, keyboard_enabled, control_mode, y, sw)

        if pose:
            y += 5
            self._text(sidebar, f"FPS: {pose.fps:.0f}", (15, y), self.theme.text, 0.5)
            y += 25

        if perf_stats:
            self._text(sidebar, "Performance", (15, y), self.theme.dim, 0.45)
            y += 16
            self._text(sidebar, f"FPS: {perf_stats.fps:.0f}", (15, y), self.theme.highlight, 0.45)
            y += 16
            self._text(sidebar, f"Latency: {perf_stats.total_ms:.1f}ms", (15, y), self.theme.text, 0.4)
            y += 16
            self._text(sidebar, f"Mode: {perf_stats.processing_mode}", (15, y), self.theme.text, 0.38)
            y += 16

        if result and result.debug:
            self._text(sidebar, result.debug, (15, y), self.theme.dim, 0.4)
            y += 18

        y = sidebar.shape[0] - 75
        self._hr(sidebar, y, sw)
        y += 14

        has_pose = pose is not None
        has_cal = calibrator.done if calibrator else False
        tracking_ok = input_state.tracking if input_state else has_pose
        tracking_label = "Pose" if input_mode == InputMode.POSE else "Hand"
        for label, ok in [(tracking_label, tracking_ok), ("Smoothing", True), ("Calibration", has_cal)]:
            dot = self.theme.status_ok if ok else self.theme.status_fail
            cv2.circle(sidebar, (20, y - 3), 3, dot, -1)
            self._text(sidebar, label, (30, y), self.theme.text, 0.4)
            y += 16

    def _draw_action_panel(self, sidebar, result, y, sw):
        self._text(sidebar, "PLAYER STATE", (15, y), self.theme.dim, 0.45)
        y += 18

        self._disp_lane_conf = self._smooth(self._disp_lane_conf, result.lane_confidence)
        self._disp_posture_conf = self._smooth(self._disp_posture_conf, result.posture_confidence)
        self._disp_ability_conf = self._smooth(self._disp_ability_conf, result.ability_confidence)

        abilities_label = ", ".join(sorted(a.name for a in result.abilities)) if result.abilities else "NONE"
        rows = [
            ("Lane", result.lane.name, self._disp_lane_conf, ACTION_COLORS.get(self._lane_to_action(result.lane), self.theme.text)),
            ("Posture", result.posture.name, self._disp_posture_conf, ACTION_COLORS.get(result.primary_action, self.theme.text)),
            ("Ability", abilities_label, self._disp_ability_conf, ACTION_COLORS[Action.HOVERBOARD] if result.abilities else self.theme.text),
        ]

        for label, value, confidence, color in rows:
            self._text(sidebar, f"{label}: {value}", (15, y), color, 0.45)
            self._text(sidebar, f"{confidence:.0%}", (sw - 48, y), self.theme.dim, 0.38)
            y += 18

        primary = result.primary_action
        self._text(sidebar, f"Primary: {primary.name}", (15, y), ACTION_COLORS.get(primary, self.theme.text), 0.4)
        return y + 22

    def _lane_to_action(self, lane: Lane) -> Action:
        if lane == Lane.LEFT:
            return Action.LEFT
        if lane == Lane.RIGHT:
            return Action.RIGHT
        return Action.RUNNING

    def _draw_keyboard_panel(self, sidebar, keyboard, enabled, control_mode, y, sw):
        self._hr(sidebar, y, sw)
        y += 12
        self._text(sidebar, "KEYBOARD", (15, y), self.theme.dim, 0.45)
        y += 18

        status = "ENABLED" if enabled else "DISABLED"
        status_color = self.theme.success if enabled else self.theme.dim
        mode_label = control_mode.name if control_mode else "DEBUG"
        self._text(sidebar, f"Mode: {mode_label}", (15, y), self.theme.text, 0.42)
        y += 17
        self._text(sidebar, status, (15, y), status_color, 0.55)
        y += 21

        held = ", ".join(keyboard.held_labels) if keyboard and keyboard.held_labels else "NONE"
        self._text(sidebar, f"Held: {held}", (15, y), self.theme.text, 0.4)
        y += 17

        last_event = keyboard.last_event if keyboard else None
        if last_event:
            age_ms = max(0.0, (time.perf_counter() - last_event.timestamp) * 1000)
            label = f"{last_event.key.upper()} {last_event.type.name} - {age_ms:.0f}ms"
            self._text(sidebar, label, (15, y), self.theme.highlight, 0.4)
            y += 17
            self._text(sidebar, last_event.reason, (15, y), self.theme.dim, 0.38)
            y += 16
        else:
            self._text(sidebar, "Last: NONE", (15, y), self.theme.dim, 0.4)
            y += 17

        if keyboard:
            for event in list(keyboard.event_history)[-3:]:
                self._text(sidebar, f"{event.command.name}: {event.type.name}", (15, y), self.theme.dim, 0.35)
                y += 14

        return y + 8

    def _conf_bar(self, sidebar, y, sw, confidence):
        bar_w = sw - 30
        bar_h = 12
        fill = int(bar_w * confidence)
        cv2.rectangle(sidebar, (15, y), (15 + bar_w, y + bar_h), self.theme.bar_bg, -1)
        cv2.rectangle(sidebar, (15, y), (15 + fill, y + bar_h), self.theme.bar_fg, -1)

        pct = f"{confidence:.0%}"
        (tw, _), _ = cv2.getTextSize(pct, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(sidebar, pct, (15 + (bar_w - tw) // 2, y + bar_h - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        return y + bar_h + 4

    def _smooth(self, current, target):
        return current * (1 - self._smooth_alpha) + target * self._smooth_alpha

    def _hr(self, img, y, sw):
        cv2.line(img, (15, y), (sw - 15, y), self.theme.separator, 1)

    def _text(self, img, text, pos, color, scale, center=False):
        if center:
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
            pos = (pos[0] - tw // 2, pos[1])
        cv2.putText(img, text, pos, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1)
