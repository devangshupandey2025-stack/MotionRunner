import csv
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class DiagnosticRow:
    frame_index: int = 0
    fps: float = 0.0
    frame_source: str = "REAL"
    capture_latency: float = 0.0
    inference_latency: float = 0.0
    detector_latency: float = 0.0
    render_latency: float = 0.0
    keyboard_latency: float = 0.0
    loop_latency: float = 0.0
    
    hip_raw_y: float = 0.0
    hip_smoothed_y: float = 0.0
    hip_ema_lag_px: float = 0.0
    velocity_instant: float = 0.0
    velocity_averaged: float = 0.0
    above_threshold: bool = False
    moving_upward: bool = False
    confirmation_ms: float = 0.0
    
    event: str = ""


class DiagnosticLogger:
    def __init__(self, max_frames=3000):
        self.max_frames = max_frames
        self.rows: list[DiagnosticRow] = []
        self.active = False
        
        home = Path.home()
        self.out_dir = home / ".motionrunner" / "diagnostics"
        
    def toggle(self):
        self.active = not self.active
        if self.active:
            self.rows.clear()
            print(f"Diagnostics ENABLED. Recording up to {self.max_frames} frames.")
        else:
            print("Diagnostics DISABLED.")
            if self.rows:
                self.flush()
                
    def record(self, row: DiagnosticRow):
        if not self.active:
            return
        self.rows.append(row)
        if len(self.rows) >= self.max_frames:
            self.flush()
            self.active = False
            
    def flush(self):
        if not self.rows:
            return
            
        self.out_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        csv_path = self.out_dir / f"diagnostics_{timestamp}.csv"
        json_path = self.out_dir / f"summary_{timestamp}.json"
        
        # Write CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=asdict(self.rows[0]).keys())
            writer.writeheader()
            for row in self.rows:
                writer.writerow(asdict(row))
                
        # Compute summary
        count = len(self.rows)
        avg_capture = sum(r.capture_latency for r in self.rows) / count if count else 0
        avg_inference = sum(r.inference_latency for r in self.rows) / count if count else 0
        avg_detector = sum(r.detector_latency for r in self.rows) / count if count else 0
        avg_render = sum(r.render_latency for r in self.rows) / count if count else 0
        avg_loop = sum(r.loop_latency for r in self.rows) / count if count else 0
        avg_keyboard = sum(r.keyboard_latency for r in self.rows) / count if count else 0
        avg_fps = sum(r.fps for r in self.rows) / count if count else 0
        
        reused = sum(1 for r in self.rows if r.frame_source == "REUSED")
        reused_pct = (reused / count) * 100 if count > 0 else 0
        
        jump_events = [r for r in self.rows if "Jump Fired" in r.event]
        
        jump_latencies = []
        for i, row in enumerate(self.rows):
            if "Jump Fired" in row.event:
                # Backtrack to find when crossing started
                for j in range(i, -1, -1):
                    if "Threshold Crossed" in self.rows[j].event:
                        latency = sum(self.rows[k].loop_latency for k in range(j, i+1))
                        jump_latencies.append(latency)
                        break
        
        avg_jump_latency = sum(jump_latencies) / len(jump_latencies) if jump_latencies else 0.0
        max_jump_latency = max(jump_latencies) if jump_latencies else 0.0
        
        summary = {
            "avg_capture_ms": round(avg_capture, 2),
            "avg_inference_ms": round(avg_inference, 2),
            "avg_detector_ms": round(avg_detector, 2),
            "avg_render_ms": round(avg_render, 2),
            "avg_loop_ms": round(avg_loop, 2),
            "avg_keyboard_ms": round(avg_keyboard, 2),
            "avg_fps": round(avg_fps, 2),
            "reused_frames": reused,
            "reused_pct": round(reused_pct, 1),
            "jump_count": len(jump_events),
            "avg_jump_delay_ms": round(avg_jump_latency, 2),
            "max_jump_delay_ms": round(max_jump_latency, 2)
        }
        
        with open(json_path, 'w') as f:
            json.dump(summary, f, indent=2)
            
        print("\n========== MotionRunner Diagnostics ==========")
        print(f"Average FPS           : {summary['avg_fps']}")
        print(f"Capture               : {summary['avg_capture_ms']} ms")
        print(f"Inference             : {summary['avg_inference_ms']} ms")
        print(f"Jump Detector         : {summary['avg_detector_ms']} ms")
        print(f"Rendering             : {summary['avg_render_ms']} ms")
        print(f"Keyboard              : {summary['avg_keyboard_ms']} ms")
        print(f"Loop                  : {summary['avg_loop_ms']} ms")
        print()
        print(f"Jump Detection Delay  : {summary['avg_jump_delay_ms']} ms (avg), {summary['max_jump_delay_ms']} ms (max)")
        print(f"Jump Count            : {summary['jump_count']}")
        print(f"Frame Reuse           : {summary['reused_pct']}%")
        print("==============================================\n")
        print(f"Saved to: {self.out_dir}")
        
        self.rows.clear()
