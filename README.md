# MotionRunner

**Vision-based webcam controller for endless runner games.**

Use full-body pose tracking or hand tracking to drive Android swipe input for
endless runners like Subway Surfers. No controllers, no phone gyro - just your
webcam, MediaPipe, and ADB touchscreen gestures.

---

## Quick Start

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Verify Android device access
adb devices

# 4. Run the expo build
.\start_expo.bat
```

> **Python:** 3.8-3.12 is required by MediaPipe. A webcam and one authorized
> Android device are required for the expo Android-swipe backend.

`start_expo.bat` starts `scrcpy` for phone viewing and then launches
`python main.py`. `scrcpy` is optional for input; the game controls are sent
directly to Android through `adb shell input swipe`.

---

## Required Software

Install these before running the expo setup on Windows:

| Software | Why It Is Needed |
|---|---|
| **Python 3.8-3.12** | Runs MotionRunner and supports the pinned MediaPipe package |
| **Git** | Clones the repository and manages the expo branch |
| **Android Studio** | Provides Android SDK management and USB driver tooling |
| **Android SDK Platform-Tools** | Provides `adb.exe`, which sends touchscreen swipes to the phone |
| **scrcpy** | Mirrors the phone screen on the laptop/projector for the demo |
| **USB driver for the phone** | Lets Windows detect the Android device over ADB |
| **Webcam** | Captures the player for pose or hand tracking |
| **Android phone with the game installed** | Runs Subway Surfers or another endless runner |

### Android Studio / ADB Setup

1. Install Android Studio.
2. Open Android Studio, then install **Android SDK Platform-Tools** from SDK
   Manager.
3. Add Platform-Tools to your Windows `Path`. Common locations are:

```text
C:\Users\<you>\AppData\Local\Android\Sdk\platform-tools
```

4. On the phone, enable **Developer options** and **USB debugging**.
5. Connect the phone by USB and accept the RSA authorization prompt.
6. Verify that exactly one authorized device is connected:

```powershell
adb devices
```

Expected output should look like:

```text
List of devices attached
R9ZYA01CHJA     device
```

If the device says `unauthorized`, unlock the phone and accept the USB debugging
prompt. If zero or multiple devices are listed, MotionRunner will pause Android
output and send no gestures.

### scrcpy Setup

Install scrcpy and make sure `scrcpy.exe` is on your Windows `Path`:

```powershell
scrcpy --version
```

If `scrcpy` is installed in a folder such as
`C:\scrcpy\scrcpy-win64-v4.1\scrcpy-win64-v4.1`, add that folder to `Path`.
For a one-terminal temporary setup:

```powershell
$env:Path = "C:\scrcpy\scrcpy-win64-v4.1\scrcpy-win64-v4.1;$env:Path"
```

You should also be able to run:

```powershell
scrcpy
```

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
| `M` | Toggle Android swipe output on/off |
| `Esc` | Emergency stop: disable Android swipe output and clear queued gestures |
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
  -> AndroidSwipeController                 (ordered ADB swipe queue)
  -> Android phone / endless runner
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
│   ├── android_swipe_controller.py # PlayerState/lane events -> ADB swipes
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

The keyboard backend is legacy code kept intact for desktop/emulator workflows.
The expo branch does not instantiate it from `main.py`; Android gameplay input
comes from `AndroidSwipeController` and ADB swipes.

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

> **Tip:** This section applies only if you deliberately wire the legacy keyboard
> backend. For the expo branch, press **M** to enable Android swipe output.

---

## Android Swipe Control

The expo backend sends native Android touch gestures through ADB:

- Lane changes use horizontal swipes from screen center toward 30% or 70% width.
- Jump uses an upward swipe from screen center toward 35% height.
- Slide uses a downward swipe from screen center toward 65% height.
- Direct two-lane transitions send two ordered swipes.
- A background ADB worker keeps the camera loop responsive.

Before enabling output, confirm:

```powershell
adb devices
adb shell wm size
```

Then run MotionRunner, complete calibration, start the game manually on the
phone, and press **M** when ready. The Windows cursor and scrcpy window position
do not affect gameplay.

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
| `pynput` | Legacy keyboard and mouse backend support |

External tools such as Android Studio, Android SDK Platform-Tools, `adb`, and
`scrcpy` are not installed by `pip`; install them separately as described in
Required Software.

`winsound` (used for calibration audio cues) is part of the Python standard
library on Windows and requires no installation.

---

## Development

```bash
# Run
python main.py

# Expo launcher with scrcpy mirror
.\start_expo.bat

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
