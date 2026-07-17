from dataclasses import dataclass
from typing import Any

@dataclass
class TrackingResult:
    raw_x: float
    filtered_x: float
    tracking_source: str
    confidence: float
    timestamp: float

@dataclass
class MotionEvent:
    type: str
    previous: Any = None
    current: Any = None
    confidence: float = 1.0
    timestamp: float = 0.0
