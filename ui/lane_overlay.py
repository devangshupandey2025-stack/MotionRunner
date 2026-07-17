import cv2
import numpy as np
from controller.motion_event import TrackingResult
from controller.state_manager import StateManager
from utils.config import AppConfig

class LaneOverlay:
    def __init__(self, config: AppConfig):
        self.config = config
        
    def draw(self, canvas: np.ndarray, tracking_result: TrackingResult, state_manager: StateManager, calibrator, fps: float):
        if not tracking_result or not calibrator or not calibrator.done:
            return
            
        h, w = canvas.shape[:2]
        positions = calibrator.result.lane_positions
        if not positions:
            return
            
        # Draw Lane Boundaries
        boundaries = []
        for i in range(len(positions) - 1):
            bx = (positions[i] + positions[i+1]) / 2.0
            boundaries.append(bx)
            cv2.line(canvas, (int(bx * w), 0), (int(bx * w), h), (200, 200, 200), 1)
            
        # Highlight current physical lane
        overlay = canvas.copy()
        phys_lane = state_manager.physical_lane
        if phys_lane != -1:
            x1 = 0 if phys_lane == 0 else int(boundaries[phys_lane - 1] * w)
            x2 = w if phys_lane == len(positions) - 1 else int(boundaries[phys_lane] * w)
            cv2.rectangle(overlay, (x1, 0), (x2, h), (100, 255, 100), -1)
            cv2.addWeighted(overlay, 0.15, canvas, 0.85, 0, canvas)
            
        # Draw user tracking point
        cx = int(tracking_result.filtered_x * w)
        cy = int(h * 0.8) # Draw near bottom
        cv2.circle(canvas, (cx, cy), 10, (0, 0, 255), -1)
        cv2.circle(canvas, (cx, cy), 4, (255, 255, 255), -1)
        
        # Debug Text
        y = 30
        x = 30
        color = (0, 255, 255)
        
        lines = [
            f"Tracking Source : {tracking_result.tracking_source}",
            f"Tracking Confidence : {tracking_result.confidence:.0%}",
            f"Raw X : {tracking_result.raw_x:.2f}",
            f"Filtered X : {tracking_result.filtered_x:.2f}",
            f"Physical Lane : {phys_lane if phys_lane != -1 else 'UNKNOWN'}",
            f"Game Lane : {state_manager.game_lane}",
            f"FPS : {fps:.0f}"
        ]
        
        for line in lines:
            # Draw background for text
            (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(canvas, (x - 5, y - th - 5), (x + tw + 5, y + 5), (0, 0, 0, 180), -1)
            cv2.putText(canvas, line, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y += 20
