from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    sidebar_bg: tuple = (25, 25, 35)
    panel_bg: tuple = (35, 35, 45)

    bone: tuple = (255, 255, 0)
    landmark: tuple = (255, 255, 255)

    hip_center: tuple = (0, 165, 255)
    hip_center_ring: tuple = (0, 100, 200)

    lane_line: tuple = (100, 100, 100)
    lane_boundary: tuple = (80, 80, 80)
    lane_zone: tuple = (0, 200, 100)

    text: tuple = (220, 220, 220)
    dim: tuple = (100, 100, 100)
    highlight: tuple = (0, 200, 255)
    warning: tuple = (0, 100, 255)
    success: tuple = (0, 200, 100)
    error: tuple = (0, 0, 200)

    bar_bg: tuple = (50, 50, 60)
    bar_fg: tuple = (0, 200, 100)
    separator: tuple = (60, 60, 70)

    state_initializing: tuple = (200, 100, 0)
    state_calibrating: tuple = (0, 215, 255)
    state_tracking: tuple = (0, 200, 0)
    state_lost: tuple = (0, 165, 255)
    state_error: tuple = (0, 0, 200)

    status_ok: tuple = (0, 200, 0)
    status_fail: tuple = (0, 0, 200)




@dataclass(frozen=True)
class GuideTheme:
    jump: tuple = (255, 200, 0)            # Blue (BGR) — jump line at rest
    jump_active: tuple = (255, 255, 0)     # Cyan — hip above jump line
    waist: tuple = (0, 200, 0)             # Green — calibrated waist
    waist_live: tuple = (0, 215, 255)      # Yellow — during calibration (live preview)
    duck: tuple = (0, 0, 200)              # Red — duck line at rest
    duck_active: tuple = (0, 165, 255)     # Orange — hip below duck line


DEFAULT_THEME = Theme()
GUIDE_THEME = GuideTheme()
