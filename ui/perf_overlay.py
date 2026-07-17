import cv2
import numpy as np

from utils.config import AppConfig
from utils.performance import PipelineStats
from ui.theme import DEFAULT_THEME


class PerfOverlay:
    def __init__(self, config: AppConfig):
        self.config = config
        self.theme = DEFAULT_THEME
        self._history_len = 120
        self._fps_history = []
        
    def draw(self, frame, stats: PipelineStats | None):
        if not stats:
            return
            
        self._fps_history.append(stats.total_ms)
        if len(self._fps_history) > self._history_len:
            self._fps_history.pop(0)
            
        h, w = frame.shape[:2]
        pad = 20
        box_w = 300
        box_h = 160
        x = pad
        y = pad
        
        overlay = frame.copy()
        cv2.rectangle(overlay, (x, y), (x + box_w, y + box_h), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.8, frame, 0.2, 0, frame)
        
        cv2.putText(frame, f"End-to-End: {stats.total_ms:.1f}ms", (x + 10, y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, self.theme.highlight, 2)
        cv2.putText(frame, f"Mode: {stats.processing_mode} (Switches: {stats.auto_switches})", (x + 10, y + 55), cv2.FONT_HERSHEY_SIMPLEX, 0.45, self.theme.text, 1)
        
        graph_x = x + 10
        graph_y = y + 70
        graph_w = box_w - 20
        graph_h = 50
        
        cv2.rectangle(frame, (graph_x, graph_y), (graph_x + graph_w, graph_y + graph_h), (40, 40, 40), -1)
        
        target_y = graph_y + graph_h - int((33.0 / 100.0) * graph_h)
        if graph_y <= target_y <= graph_y + graph_h:
            cv2.line(frame, (graph_x, target_y), (graph_x + graph_w, target_y), (0, 0, 200), 1)
            
        if len(self._fps_history) > 1:
            pts = []
            for i, ms in enumerate(self._fps_history):
                px = graph_x + int((i / self._history_len) * graph_w)
                py = graph_y + graph_h - int((min(ms, 100.0) / 100.0) * graph_h)
                pts.append((px, py))
            
            pts = np.array(pts, np.int32)
            cv2.polylines(frame, [pts], False, (0, 255, 0), 1)
            
        bar_y = graph_y + graph_h + 15
        bar_h = 10
        total = max(1.0, stats.total_ms)
        
        stages = [
            (stats.capture_ms, (100, 100, 200)),
            (stats.preprocess_ms, (150, 150, 200)),
            (stats.inference_ms, (200, 100, 100)),
            (stats.classify_ms, (200, 150, 100)),
            (stats.visualize_ms, (100, 200, 100)),
            (stats.display_ms, (100, 200, 150))
        ]
        
        cx = graph_x
        for ms, color in stages:
            cw = int((ms / total) * graph_w)
            if cw > 0:
                cv2.rectangle(frame, (cx, bar_y), (cx + cw, bar_y + bar_h), color, -1)
                cx += cw
