# MotionRunner

**Vision-based full-body game controller for endless runner games.**

Move your body to control the game. Lean to switch lanes, jump in real life to jump in-game, squat to slide. No controllers, no phone gyro — just your webcam and MediaPipe.

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run
python main.py
```

Stand in front of your camera. A 3-2-1 countdown will calibrate the system to your body proportions. Once calibration completes, every movement is mapped relative to your own dimensions — not hardcoded pixels.

By default the camera feed is mirrored, so the preview feels like a mirror and left/right gestures line up with what you expect.

**Press Q to quit.**

---

## Controls

| Body Movement | Game Action | How It Works |
|---|---|---|
| Lean left | Move left | Body center shifts left of calibrated rest position |
| Lean right | Move right | Body center shifts right of calibrated rest position |
| Jump in place | Jump | Hip center rapid upward velocity detected |
| Squat down | Slide | Hip height + knee angle + body compression (hysteresis) |
| Both hands above head | Hoverboard | Both wrists above nose held for 500ms |

---

## Architecture

```
                    ┌──────────────────┐
Camera ───► PoseTracker ───► PoseFrame      │
                    │  (derived props)  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   EMAFilter      │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │GestureClassifier  │
                    │  LaneDetector     │
                    │  JumpDetector     │
                    │  SlideDetector    │
                    │  HoverDetector    │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   PlayerState     │
                    │  lane             │
                    │  posture          │
                    │  abilities        │
                    └────────┬─────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
      ActionExecutor     Visualizer     PoseLogger
    KeyboardEvents                    (Milestone 2)
              │
              ▼
    KeyboardController
              │
              ▼
         BlueStacks
```

---

## Project Structure

```
motion-runner/
│
├── main.py                         # Entry point
├── requirements.txt                # Dependencies
├── .gitignore
│
├── camera/
│   └── webcam.py                   # Webcam wrapper (index, resolution)
│
├── vision/
│   ├── landmarks.py                # Landmark dataclass + angle helper
│   ├── pose_frame.py               # PoseFrame with derived properties
│   ├── pose_tracker.py             # MediaPipe Pose → PoseFrame
│   └── pose_smoother.py            # EMA filter (swapable interface)
│
├── controller/
│   ├── action.py                   # PlayerState, Action compatibility, detector result types
│   ├── calibration.py              # Body calibration (median over N frames)
│   ├── action_executor.py          # PlayerState transitions → KeyboardEvent queue
│   ├── keyboard_controller.py      # KeyboardEvent dispatch + held-key cleanup
│   ├── keyboard_events.py          # KeyboardEvent and event type definitions
│   ├── motion_controller.py        # State machine + orchestrator
│   │
│   └── gestures/
│       ├── lane_detector.py        # Body-center delta relative to shoulder width
│       ├── jump_detector.py        # Hip Y velocity
│       ├── slide_detector.py       # Hip Y + knee angle + body compression
│       ├── hoverboard_detector.py  # Both wrists above nose for 500ms
│       └── gesture_classifier.py   # Orchestrates detectors + posture resolver → PlayerState
│
├── ui/
│   └── visualizer.py               # Hybrid layout (feed + sidebar overlay)
│
├── utils/
│   ├── config.py                   # Single source of truth for all thresholds
│   └── cooldown.py                 # Per-action cooldown manager
│
└── debug/
    └── __init__.py                 # (Milestone 1.5) Pose logger
```

---

## Why This Approach Is Different

Most gesture-controlled game projects hardcode pixel thresholds that only work for one person at one distance. This project uses **body-relative calibration**:

During a 3-second calibration, the system records:
- **Shoulder width** — for lane-change sensitivity
- **Body height** — for slide detection ratios
- **Arm length** — for gesture zones
- **Resting hip height** — for jump detection baseline

Every threshold is a *ratio* of your body. It works for kids, adults, tall, short — no code changes.

---

## Milestones

| Milestone | What's Included | Status |
|---|---|---|
| **1** | Camera → Pose → EMA → Calibration → Visualizer → Gesture Debug | ✅ Done |
| **1.5** | Pose logger (CSV export) | ⏳ Next |
| **2** | Keyboard controller → BlueStacks → Play Subway Surfers | ✅ In progress |
| **3** | Settings panel, sensitivity, camera selector | ⏳ |
| **4** | One-Euro filter, Temple Run, Chrome Dino support | ⏳ |

---

## Development

```bash
# Run
python main.py

# Dependencies
mediapipe      # Pose estimation
opencv-python  # Camera + rendering
numpy          # Array operations
pynput         # Keyboard output (Milestone 2)
```

---

## Keyboard Control

Phase 2 converts `PlayerState` into deterministic keyboard events:

```
PlayerState
  → LaneExecutor / PostureExecutor / AbilityExecutor
  → KeyboardEvent queue
  → KeyboardController
```

Keyboard output is transition-driven. Leaning left sends one left-arrow tap when the lane changes to `LEFT`; holding the lean does not repeat. Jump sends one up-arrow tap. Slide holds the down arrow until posture returns to running. Hoverboard sends one space tap when the ability activates.

Default Subway Surfers keymap:

| Command | Key |
|---|---|
| Left lane | Arrow Left |
| Right lane | Arrow Right |
| Jump | Arrow Up |
| Slide | Arrow Down |
| Hoverboard | Space |

Runtime controls:

| Key | Behavior |
|---|---|
| K | Toggle keyboard control on/off |
| Esc | Emergency stop: disable keyboard output and release held keys |
| Q | Quit app |

Test in Notepad before BlueStacks. Start the app, calibrate, press K, then confirm left/right/jump send single taps, slide holds/releases Down correctly, and hoverboard sends one Space tap. Only after Notepad behaves cleanly should you switch focus to BlueStacks.

---

## Adding a New Gesture

1. Create `controller/gestures/new_detector.py`
2. Implement a detector result type and a `detect(pose)` method
3. Add it to `GestureClassifier.classify()` and resolve it into `PlayerState`
4. Update the visualizer or executors that should consume the new state

No other files need to change.
