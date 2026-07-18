# MotionRunner

**Vision-based webcam controller for endless runner games.**

Use full-body pose tracking or hand tracking to drive keyboard input for endless
runners like Subway Surfers. No controllers, no phone gyro — just your webcam and
MediaPipe.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python main.py
```

> **Python:** 3.8–3.12 (required by MediaPipe). A webcam is required.

On launch, MotionRunner looks for a saved calibration profile under
`~/.motionrunner/profiles/default.json`. If found, you can press **Enter** to reuse
it or **R** to recalibrate. In pose mode a multi-step **Calibration Wizard** guides
you through standing still, then leaning left and right to record lane positions.
Once calibration completes, every threshold is expressed as a *ratio of your own
body* — not hardcoded pixels — so it works for kids, adults, tall, and short
players alike.

The active input mode is controlled in `utils/config.py` via `InputMode`:

- `InputMode.POSE` — full-body controls (lean / jump / squat / hands-up).
- `InputMode.HAND` — hand steering plus pinch-hold hoverboard.

The camera feed is mirrored by default so the preview feels like a mirror and
left/right gestures line up with what you expect.

**Press Q to quit.**

---

## Controls

### Pose mode

| Body Movement | Game Action | How It Works |
|---|---|---|
| Lean left | Move left | Body center shifts left of calibrated rest position |
| Lean right | Move right | Body center shifts right of calibrated rest position |
| Jump in place | Jump | Hip center rapid upward velocity, confirmed over a short window |
| Squat down | Slide | Hip height + knee angle + body compression (hysteresis) |
| Both hands above head | Hoverboard | Both wrists above nose held for 500 ms |

### Hand mode

| Hand Gesture | Game Action | How It Works |
|---|---|---|
| Open palm left/right | Move left/right | Palm center shifts relative to calibrated neutral hand position |
| Pinch hold | Hoverboard | Thumb–index pinch held for 500 ms |

### Runtime controls

| Key | Behavior |
|---|---|
| `Q` | Quit the app |
| `K` | Toggle keyboard control on/off |
| `Esc` | Emergency stop: disable keyboard output and release held keys |
| `P` | Toggle the performance overlay (per-stage timings + FPS) |
| `Ctrl+D` | Toggle Diagnostic Mode (records a CSV of per-frame metrics) |
| `[` / `]` | Cycle to the previous / next preset |
| `S` | Save settings and calibration to disk |
| `R` | Retry quality check, or recalibrate when already tracking |

---

## Architecture

```
Camera
  -> PoseProvider or HandProvider          (MediaPipe inference + EMA smoothing)
  -> InputState / PlayerState output        (provider-normalized control state)
  -> PositionTracker -> LaneTracker         (virtual lane tracking V2)
  -> StateManager                           (lane-change event resolution)
  -> ActionExecutor                         (PlayerState -> KeyboardEvent queue)
  -> KeyboardController                     (pynput dispatch + held-key cleanup)
  -> BlueStacks / endless runner
```

### Virtual Lane Tracking (V2)

Rather than finding the nearest lane center, lane classification is
**boundary-based** with hysteresis. During calibration the wizard records the
left/center/right positions of your body; `LaneTracker` computes the midpoints
between them and classifies by region. A hysteresis buffer (a fraction of the
lane span) prevents rapid flipping when you hover near a boundary, and a lane
change cooldown suppresses spurious double-taps.

`PositionTracker` selects the best available tracking landmark (hip → shoulder →
nose) with debouncing, so lane tracking stays responsive even when the lower body
is briefly occluded.

### Adaptive Baseline

While the player is idle (not jumping or sliding) for `adaptive_idle_ms`, the
standing hip baseline slowly drifts toward the observed position. This compensates
for players shifting their stance or camera tilt over a long session without
requiring recalibration. Jump/slide threshold lines are recomputed from the
adapted baseline each update.

### Inference Scheduling

MediaPipe inference is the most expensive stage. `ProcessingMode.AUTO` (default)
monitors recent inference latency and dynamically skips frames (every 2nd or 3rd
frame) to hold a target frame rate, reusing the last smoothed pose on skipped
frames. `EVERY_FRAME`, `EVERY_2_FRAMES`, and `EVERY_3_FRAMES` modes are also
available for fixed scheduling.

---

## Project Structure

```
motion-runner/
│
├── main.py                         # Entry point + main loop + key handling
├── requirements.txt                # Dependencies
├── .gitignore
│
├── camera/
│   └── webcam.py                   # Webcam wrapper (index, resolution, mirror)
│
├── vision/
│   ├── landmarks.py                # Landmark dataclass + angle helper
│   ├── pose_frame.py               # PoseFrame with derived properties
│   ├── pose_tracker.py             # MediaPipe Pose -> PoseFrame
│   ├── pose_smoother.py            # EMA filter (swappable interface)
│   ├── pose_provider.py            # Pose pipeline: tracker + smoother + wizard + classifier
│   └── hand_provider.py            # Hand pipeline: MediaPipe Hands + pinch/palm interpreter
│
├── controller/
│   ├── action.py                   # PlayerState, Lane/Posture/Ability, detector result types
│   ├── calibration.py              # Body calibration (median over N frames) + CalibrationData
│   ├── calibration_wizard.py       # Multi-step calibration flow with audio cues
│   ├── action_executor.py          # PlayerState transitions -> KeyboardEvent queue
│   ├── keyboard_controller.py      # KeyboardEvent dispatch + held-key cleanup
│   ├── keyboard_events.py          # KeyboardEvent and event type definitions
│   ├── app_controller.py           # Runtime state machine + provider orchestration
│   ├── position_tracker.py         # Best-landmark selection (hip/shoulder/nose)
│   ├── lane_tracker.py             # Boundary-based lane classification + hysteresis
│   ├── state_manager.py            # Lane-change event resolution -> game lane
│   ├── motion_event.py             # TrackingResult + MotionEvent dataclasses
│   │
│   └── gestures/
│       ├── lane_detector.py        # Body-center delta relative to shoulder width
│       ├── jump_detector.py        # Hip Y velocity + confirmation window
│       ├── slide_detector.py       # Hip Y + knee angle + body compression
│       ├── hoverboard_detector.py  # Both wrists above nose held for 500 ms
│       └── gesture_classifier.py   # Orchestrates detectors + adaptive baseline -> PlayerState
│
├── input/
│   ├── input_state.py              # Provider-normalized control state
│   ├── provider.py                 # Minimal InputProvider interface
│   ├── adapters.py                 # PlayerState <-> InputState compatibility helpers
│   └── keyboard_provider.py        # Keyboard-driven provider (testing fallback)
│
├── ui/
│   ├── visualizer.py               # Hybrid layout (feed + sidebar overlay)
│   ├── hud.py                      # HUD: gesture flash, confidence meters, timeline
│   ├── lane_overlay.py             # Virtual lane + tracking-source overlay
│   ├── perf_overlay.py             # Per-stage performance overlay
│   └── theme.py                    # Colors and layout constants
│
├── utils/
│   ├── config.py                   # Single source of truth: thresholds, modes, presets, persistence
│   ├── cooldown.py                 # Per-action cooldown manager
│   ├── performance.py             # LoopTimer, RollingProfiler, InferenceScheduler
│   └── diagnostic.py               # CSV diagnostic logger (per-frame metrics)
│
├── presets/                        # Tunable parameter sets (cycle with [ / ])
│   ├── default.json                # "Normal"
│   ├── sensitive.json
│   ├── stable.json
│   └── diagnostic_test.json
│
├── debug/
│   └── __init__.py                 # Pose logger hooks
│
└── tests/
    ├── test_action_executor.py
    ├── test_hand_provider.py
    ├── test_input_adapters.py
    └── test_performance_pipeline.py
```

---

## Configuration & Persistence

`utils/config.py` holds every tunable threshold as a single `AppConfig`
dataclass — camera settings, detection/tracking confidences, smoothing, lane and
jump/slide tuning, calibration wizard options, HUD toggles, and the virtual lane
tracker parameters.

**Settings** (only values that differ from defaults) are saved to
`~/.motionrunner/settings.json` and restored on launch.

**Calibration profiles** are saved to `~/.motionrunner/profiles/default.json` and
can be reused on the next run (press Enter at the prompt, or R to recalibrate).
Older `~/.motionrunner/calibration.json` files are still imported for backwards
compatibility.

**Presets** live in `presets/*.json` and override any `AppConfig` fields. Cycle
them live with `[` and `]`. Add a new preset by dropping a JSON file in the
`presets/` directory.

---

## Why This Approach Is Different

Most gesture-controlled game projects hardcode pixel thresholds that only work
for one person at one distance. MotionRunner uses **body-relative calibration**.

During calibration the system records:

- **Shoulder width** — for lane-change sensitivity
- **Body height** — for slide-detection ratios
- **Arm length** — for gesture zones
- **Resting hip height** — for jump-detection baseline
- **Left / center / right body positions** — for boundary-based lane tracking

Every threshold is a *ratio* of your body. It works for kids, adults, tall,
short — no code changes.

---

## Keyboard Control

Keyboard output is **transition-driven**:

- Leaning left sends one left-arrow tap when the lane changes to `LEFT`; holding
  the lean does not repeat.
- Jump sends one up-arrow tap.
- Slide holds the down arrow until posture returns to running.
- Hoverboard sends one space tap when the ability activates.

Default Subway Surfers keymap (configurable via `KeyMap` in `utils/config.py`):

| Command | Key |
|---|---|
| Left lane | Arrow Left |
| Right lane | Arrow Right |
| Jump | Arrow Up |
| Slide | Arrow Down |
| Hoverboard | Space |

> **Tip:** Test in Notepad before BlueStacks. Start the app, calibrate, press
> **K**, then confirm left/right/jump send single taps, slide holds/releases Down
> correctly, and hoverboard sends one Space tap. Only after Notepad behaves cleanly
> should you switch focus to BlueStacks.

---

## Diagnostics & Performance

- **Performance overlay** (`P`): shows per-stage timings (capture, preprocess,
  inference, classification, visualization, display), overall FPS, the active
  processing mode, and the number of AUTO mode switches.
- **Diagnostic Mode** (`Ctrl+D`): records up to 3000 frames of per-frame metrics
  to a CSV under `~/.motionrunner/diagnostics/`, including raw/smoothed hip Y,
  instant and averaged velocity, threshold flags, confirmation time, and any
  detected event. Useful for tuning jump/slide detectors.

---

## Dependencies

| Package | Purpose |
|---|---|
| `mediapipe` | Pose + hand landmark estimation |
| `opencv-python` | Camera capture + rendering |
| `numpy` | Array operations for overlays |
| `pynput` | Keyboard output to the OS / BlueStacks |

`winsound` (used for calibration audio cues) is part of the Python standard
library on Windows and requires no installation.

---

## Development

```bash
# Run
python main.py

# Run the test suite
python -m unittest discover -s tests
```

---

## Adding a New Gesture

1. Create `controller/gestures/new_detector.py`.
2. Implement a detector result type and a `detect(pose)` method.
3. Add it to `GestureClassifier.classify()` and resolve it into `PlayerState`.
4. Update the visualizer or executors that should consume the new state.

No other files need to change.

---

## Milestones

| Milestone | What's Included | Status |
|---|---|---|
| **1** | Camera → Pose → EMA → Calibration → Visualizer → Gesture debug | ✅ Done |
| **1.5** | Diagnostic pose/metrics logger (CSV export) | ✅ Done |
| **2** | Keyboard controller → BlueStacks → Play Subway Surfers | ✅ Done |
| **3** | Provider abstraction + hand controls + calibration wizard + presets + HUD + settings persistence | ✅ Done |
| **4** | One-Euro filter, Temple Run, Chrome Dino support | ⏳ Next |
