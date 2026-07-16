from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import time

from utils.config import ProcessingMode


@dataclass
class StageSample:
    capture_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    classify_ms: float = 0.0
    visualize_ms: float = 0.0
    display_ms: float = 0.0
    total_ms: float = 0.0


@dataclass
class PipelineStats:
    capture_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    classify_ms: float = 0.0
    visualize_ms: float = 0.0
    display_ms: float = 0.0
    total_ms: float = 0.0
    fps: float = 0.0
    processed_frame: bool = True
    processing_mode: str = ProcessingMode.EVERY_FRAME.name
    auto_switches: int = 0


class RollingProfiler:
    def __init__(self, window: int = 30):
        self._window = max(1, window)
        self._samples: deque[StageSample] = deque(maxlen=self._window)

    def add(self, sample: StageSample):
        self._samples.append(sample)

    def snapshot(self) -> PipelineStats:
        if not self._samples:
            return PipelineStats()

        count = len(self._samples)
        sample = PipelineStats(
            capture_ms=sum(item.capture_ms for item in self._samples) / count,
            preprocess_ms=sum(item.preprocess_ms for item in self._samples) / count,
            inference_ms=sum(item.inference_ms for item in self._samples) / count,
            classify_ms=sum(item.classify_ms for item in self._samples) / count,
            visualize_ms=sum(item.visualize_ms for item in self._samples) / count,
            display_ms=sum(item.display_ms for item in self._samples) / count,
            total_ms=sum(item.total_ms for item in self._samples) / count,
        )
        sample.fps = 1000.0 / sample.total_ms if sample.total_ms > 0 else 0.0
        return sample


class LoopTimer:
    def __init__(self):
        self._start = time.perf_counter()
        self._marks: dict[str, float] = {"start": self._start}

    def mark(self, name: str):
        self._marks[name] = time.perf_counter()

    def elapsed_ms(self, start: str, end: str) -> float:
        return max(0.0, (self._marks[end] - self._marks[start]) * 1000.0)

    def total_ms(self) -> float:
        return max(0.0, (self._marks.get("end", time.perf_counter()) - self._start) * 1000.0)


class InferenceScheduler:
    def __init__(self, mode: ProcessingMode):
        self._mode = mode
        self._frame_count = 0
        self._auto_interval = 1
        self._auto_switches = 0
        self._recent_inference_ms: deque[float] = deque(maxlen=12)

    @property
    def active_mode_name(self) -> str:
        if self._mode != ProcessingMode.AUTO:
            return self._mode.name
        return f"AUTO({self._auto_interval})"

    @property
    def auto_switches(self) -> int:
        return self._auto_switches

    def reset(self):
        self._frame_count = 0
        self._auto_interval = 1
        self._auto_switches = 0
        self._recent_inference_ms.clear()

    def should_process(self) -> bool:
        self._frame_count += 1
        interval = self._current_interval()
        return ((self._frame_count - 1) % interval) == 0

    def record_inference(self, inference_ms: float):
        self._recent_inference_ms.append(inference_ms)
        if self._mode == ProcessingMode.AUTO:
            self._update_auto_interval()

    def _current_interval(self) -> int:
        if self._mode == ProcessingMode.EVERY_2_FRAMES:
            return 2
        if self._mode == ProcessingMode.EVERY_3_FRAMES:
            return 3
        if self._mode == ProcessingMode.AUTO:
            return self._auto_interval
        return 1

    def _update_auto_interval(self):
        if len(self._recent_inference_ms) < 3:
            return

        avg_ms = sum(self._recent_inference_ms) / len(self._recent_inference_ms)
        previous = self._auto_interval
        if self._auto_interval == 1:
            if avg_ms > 18.0:
                self._auto_interval = 2
        elif self._auto_interval == 2:
            if avg_ms > 28.0:
                self._auto_interval = 3
            elif avg_ms < 11.0:
                self._auto_interval = 1
        else:
            if avg_ms < 20.0:
                self._auto_interval = 2

        if previous != self._auto_interval:
            self._auto_switches += 1


@dataclass
class ProviderPerfStats:
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    classify_ms: float = 0.0
    processed_frame: bool = True
    processing_mode: str = ProcessingMode.EVERY_FRAME.name
    auto_switches: int = 0


@dataclass
class ProfilingReport:
    before: PipelineStats = field(default_factory=PipelineStats)
    after: PipelineStats = field(default_factory=PipelineStats)

    def format_lines(self) -> list[str]:
        return [
            "Before:",
            f"Capture        {self.before.capture_ms:.1f} ms",
            f"Preprocess     {self.before.preprocess_ms:.1f} ms",
            f"Inference      {self.before.inference_ms:.1f} ms",
            f"Classification {self.before.classify_ms:.1f} ms",
            f"Visualization  {self.before.visualize_ms:.1f} ms",
            f"Display        {self.before.display_ms:.1f} ms",
            f"Overall FPS    {self.before.fps:.1f}",
            "After:",
            f"Capture        {self.after.capture_ms:.1f} ms",
            f"Preprocess     {self.after.preprocess_ms:.1f} ms",
            f"Inference      {self.after.inference_ms:.1f} ms",
            f"Classification {self.after.classify_ms:.1f} ms",
            f"Visualization  {self.after.visualize_ms:.1f} ms",
            f"Display        {self.after.display_ms:.1f} ms",
            f"Overall FPS    {self.after.fps:.1f}",
        ]
