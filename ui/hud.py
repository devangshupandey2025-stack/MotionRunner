import time
from collections import deque
import cv2
import numpy as np

from utils.config import AppConfig
from controller.action import Action, PlayerState, Ability
from ui.theme import DEFAULT_THEME


class HUD:
    def __init__(self, config: AppConfig):
        self.config = config
        self.theme = DEFAULT_THEME
        self._last_action = Action.RUNNING
        self._last_abilities = set()
        self._flash_trigger_time = 0.0
        self._flash_text = ""
        self._flash_color = (255, 255, 255)
        
        self._timeline = deque()
        
    def draw(self, frame, result: PlayerState | None, is_tracking: bool, has_calibrated: bool):
        h, w = frame.shape[:2]
        
        self._update_flash_state(result)
        
        if self.config.show_tracking_quality:
            self._draw_tracking_quality(frame, is_tracking, has_calibrated, w)
            
        if self.config.show_gesture_flash:
            self._draw_gesture_flash(frame, w, h)
            
        if self.config.show_confidence_meters and result:
            self._draw_confidence_meters(frame, result, h)
            
        if self.config.show_gesture_timeline:
            self._draw_timeline(frame, w, h)
            
    def _update_flash_state(self, result: PlayerState | None):
        if not result:
            return
            
        now = time.perf_counter()
        
        if result.primary_action != self._last_action and result.primary_action != Action.RUNNING:
            self._trigger_flash(result.primary_action)
            self._timeline.append((now, self._get_action_color(result.primary_action)))
            
        new_abilities = result.abilities - self._last_abilities
        if Ability.HOVERBOARD in new_abilities:
            self._trigger_flash(Action.HOVERBOARD)
            self._timeline.append((now, self._get_action_color(Action.HOVERBOARD)))
            
        self._last_action = result.primary_action
        self._last_abilities = set(result.abilities)
        
        while self._timeline and now - self._timeline[0][0] > self.config.gesture_timeline_window_s:
            self._timeline.popleft()

    def _trigger_flash(self, action: Action):
        self._flash_trigger_time = time.perf_counter()
        
        # Using [OK] since OpenCV doesn't render checkmarks out of the box in cv2.putText
        if action == Action.JUMP:
            self._flash_text = "UP JUMP [OK]"
            self._flash_color = (0, 255, 255)
        elif action == Action.SLIDE:
            self._flash_text = "DOWN SLIDE [OK]"
            self._flash_color = (255, 100, 0)
        elif action == Action.LEFT:
            self._flash_text = "<- LEFT [OK]"
            self._flash_color = (0, 200, 0)
        elif action == Action.RIGHT:
            self._flash_text = "RIGHT -> [OK]"
            self._flash_color = (0, 200, 0)
        elif action == Action.HOVERBOARD:
            self._flash_text = "HOVERBOARD [OK]"
            self._flash_color = (255, 0, 255)

    def _get_action_color(self, action: Action):
        if action == Action.JUMP: return (0, 255, 255)
        if action == Action.SLIDE: return (255, 100, 0)
        if action == Action.LEFT or action == Action.RIGHT: return (0, 200, 0)
        if action == Action.HOVERBOARD: return (255, 0, 255)
        return (200, 200, 200)

    def _draw_gesture_flash(self, frame, w, h):
        now = time.perf_counter()
        elapsed = (now - self._flash_trigger_time) * 1000.0
        
        if elapsed < self.config.gesture_flash_duration_ms:
            alpha = 1.0 - (elapsed / self.config.gesture_flash_duration_ms)
            if alpha > 0.1:
                text = self._flash_text
                scale = 1.5 + (1.0 - alpha) * 0.5
                
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 3)
                x = (w - tw) // 2
                y = 80
                cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, self._flash_color, 3)

    def _draw_tracking_quality(self, frame, is_tracking: bool, has_calibrated: bool, w):
        if is_tracking and has_calibrated:
            color = self.theme.status_ok
        elif is_tracking:
            color = self.theme.warning
        else:
            color = self.theme.status_fail
            
        cv2.circle(frame, (w - 30, 30), 10, color, -1)
        cv2.circle(frame, (w - 30, 30), 12, (255, 255, 255), 2)

    def _draw_confidence_meters(self, frame, result: PlayerState, h):
        x_start = 20
        y_start = h - 80
        bar_w = 15
        bar_h = 50
        spacing = 25
        
        meters = [
            (result.lane_confidence, (0, 200, 0)),
            (result.posture_confidence, (0, 200, 255)),
            (result.ability_confidence, (255, 0, 255))
        ]
        
        for i, (conf, color) in enumerate(meters):
            x = x_start + i * spacing
            cv2.rectangle(frame, (x, y_start), (x + bar_w, y_start + bar_h), (50, 50, 50), -1)
            
            fill_h = int(bar_h * conf)
            if fill_h > 0:
                cv2.rectangle(frame, (x, y_start + bar_h - fill_h), (x + bar_w, y_start + bar_h), color, -1)

    def _draw_timeline(self, frame, w, h):
        now = time.perf_counter()
        
        y = h - 15
        cv2.rectangle(frame, (0, y), (w, h), (30, 30, 30), -1)
        
        for timestamp, color in self._timeline:
            age = now - timestamp
            x = int(w - (age / self.config.gesture_timeline_window_s) * w)
            if 0 <= x <= w:
                cv2.rectangle(frame, (x - 2, y), (x + 2, h), color, -1)
