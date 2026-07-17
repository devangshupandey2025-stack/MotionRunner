from utils.config import AppConfig
from controller.motion_event import TrackingResult, MotionEvent


class LaneTracker:
    """Boundary-based lane classification.

    Instead of finding the nearest lane center (which creates a double-gate
    with hysteresis), we compute explicit boundaries between lanes and
    classify purely by region.

    For 3 lanes with positions [left_x, center_x, right_x]:

        left_boundary  = (left_x + center_x) / 2
        right_boundary = (center_x + right_x) / 2

        x < left_boundary   -> LEFT  (lane 0)
        x > right_boundary  -> RIGHT (lane 2)
        otherwise           -> CENTER (lane 1)

    Hysteresis is applied *at* each boundary so that small oscillations
    don't cause rapid lane flipping.
    """

    def __init__(self, config: AppConfig, calibration=None):
        self.config = config
        self.calibration = calibration
        self._current_lane = -1  # -1 = UNKNOWN
        self._last_change_time = 0.0
        self._boundaries: list[float] = []
        self._hysteresis: float = 0.0

        if calibration:
            self._recompute_boundaries()

    def set_calibration(self, cal):
        self.calibration = cal
        self._recompute_boundaries()

    def _recompute_boundaries(self):
        """Pre-compute the N-1 boundaries between N lane positions."""
        positions = self.calibration.lane_positions
        if not positions or len(positions) < 2:
            self._boundaries = []
            self._hysteresis = 0.0
            return

        self._boundaries = [
            (positions[i] + positions[i + 1]) / 2.0
            for i in range(len(positions) - 1)
        ]

        # Hysteresis buffer: a fraction of the average gap width
        total_span = abs(positions[-1] - positions[0])
        self._hysteresis = total_span * self.config.lane_buffer_percentage / 2.0

    def track(self, result: TrackingResult) -> MotionEvent | None:
        if not self.calibration or not self.calibration.lane_positions:
            return None

        if not self._boundaries:
            self._recompute_boundaries()
            if not self._boundaries:
                return None

        new_lane = self._current_lane

        if result.confidence < self.config.lane_lost_confidence_threshold:
            new_lane = -1
        else:
            x = result.filtered_x

            if self._current_lane == -1:
                # First classification — snap without hysteresis
                new_lane = self._classify(x, hysteresis=0.0)
            else:
                # Apply hysteresis around each boundary
                new_lane = self._classify(x, hysteresis=self._hysteresis)

        # Emit event on change
        if new_lane != self._current_lane:
            elapsed = (result.timestamp - self._last_change_time) * 1000.0

            # Allow UNKNOWN immediately, but cooldown normal changes
            if new_lane == -1 or elapsed >= self.config.lane_change_cooldown_ms:
                if new_lane != -1:
                    self._last_change_time = result.timestamp

                event = MotionEvent(
                    type="lane_changed",
                    previous=self._current_lane,
                    current=new_lane,
                    confidence=result.confidence,
                    timestamp=result.timestamp,
                )
                self._current_lane = new_lane
                return event

        return None

    def _classify(self, x: float, hysteresis: float) -> int:
        """Classify x into a lane index using boundary regions.

        With hysteresis=0, this is a simple boundary check:
            x < boundary[0]  -> lane 0
            x < boundary[1]  -> lane 1
            ...
            else              -> last lane

        With hysteresis > 0, the boundary shifts depending on which
        direction the player would be moving.  If the player is currently
        in lane i and would need to cross boundary[j] to reach lane j,
        the boundary is pushed *toward* lane j so the player must move
        a bit further past the midpoint to commit.
        """
        n_lanes = len(self._boundaries) + 1

        for i in range(len(self._boundaries)):
            boundary = self._boundaries[i]

            if self._current_lane <= i:
                # Player is on the left side — require crossing further right
                # to stay in current lane (shift boundary right)
                effective = boundary + hysteresis
            else:
                # Player is on the right side — require crossing further left
                # to move left (shift boundary left)
                effective = boundary - hysteresis

            if x < effective:
                return i

        return n_lanes - 1
