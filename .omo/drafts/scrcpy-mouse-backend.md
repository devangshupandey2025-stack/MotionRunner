---
slug: scrcpy-mouse-backend
status: drafting
intent: clear
review_required: false
pending-action: write .omo/plans/scrcpy-mouse-backend.md
approach: Replace keyboard output backend with a mouse output backend on a new expo branch. Leave the entire vision/calibration/detector pipeline untouched. Add a MotionIntent adapter, a MouseController, and a scrcpy window finder; rewire main.py to use them; replace the visualizer keyboard panel with a mouse panel. Reuse pynput (already a dep) and ctypes (stdlib) — no new dependencies.
---

# Draft: scrcpy-mouse-backend

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
<!-- id | outcome (one line) | status: active|deferred | evidence path -->

| id | outcome (one line) | status | evidence path |
| --- | --- | --- | --- |
| C1 motion_intent | Lightweight frozen dataclass `MotionIntent(lane, jump_active, slide_active, hoverboard_active, timestamp, frame_index)` populated from existing `PlayerState`. Decouples detectors from output. | active | controller/action.py:94-122 (PlayerState); controller/motion_intent.py (new) |
| C2 mouse_controller | New `MouseController` consuming `MotionIntent`, moving the Windows cursor continuously inside scrcpy bounds using pynput `mouse.position = (x,y)` each frame. Velocity model: `delta = speed × dt`, clamped to bounds. | active | controller/keyboard_controller.py (reference pattern); controller/mouse_controller.py (new) |
| C3 scrcpy_window | New `ScrcpyWindow` locator: ctypes `FindWindowW` by title → `GetClientRect` + `ClientToScreen` → inner rect for clamping. Manual fallback from config. | active | controller/scrcpy_window.py (new); research cited in Findings |
| C4 config | Extend `AppConfig` with `cursor_speed_x`, `cursor_speed_y`, `scrcpy_window_bounds`, `mouse_update_rate`, `scrcpy_window_title`, `mouse_emergency_keys`. Add to `presets/default.json`. | active | utils/config.py:42-138 (AppConfig); presets/default.json |
| C5 main_loop | Rewire `main.py`: drop `KeyboardController` + `ActionExecutor` instantiation; build `MotionIntent` from `controller.last_result` each TRACKING frame; dispatch to `MouseController`; F8 toggle, F9 reset, Esc freeze-and-release. | active | main.py:32-65, 141-188 (key handling + dispatch); main.py:194-198 (cleanup) |
| C6 visualizer+tests | Replace `_draw_keyboard_panel` with `_draw_mouse_panel` (cursor x,y, lane, jump, slide, ACTIVE/PAUSED). Add unit tests for MotionIntent mapping, cursor clamping, continuous movement. | active | ui/visualizer.py:355-505 (keyboard panel + sidebar); tests/test_action_executor.py (pattern) |

## Open assumptions (announced defaults)
<!-- Record any default you adopt instead of asking, so the user can veto it at the gate. -->
<!-- assumption | adopted default | rationale | reversible? -->

| assumption | adopted default | rationale | reversible? |
| --- | --- | --- | --- |
| Mouse library | pynput 1.7.x `mouse.Controller` (already a dependency) | Research confirms `position = (x,y)` calls Win32 `SetCursorPos` (absolute, no acceleration curve). No new deps. | Yes |
| DPI awareness | Call `ctypes.windll.shcore.SetProcessDpiAwareness(2)` once at startup in main.py | pynput docs warn that without this, on HiDPI Windows laptops the Controller lands cursor in the wrong pixel. cv2 windows also become DPI-aware, matching scrcpy. | Yes |
| Movement model | Velocity model: each frame `delta = speed × dt`; cursor pos += delta; clamp to inner rect. Center lane → delta = 0 (cursor stops in place). Jump active → delta_y = -speed_y × dt. Slide active → delta_y = +speed_y × dt. | Spec: "continuous while detector state active", "Do not teleport", "analog joystick", "CENTER → Cursor stops". | Yes |
| MouseController threading | Called inline from main loop each frame (same pattern as existing KeyboardController.dispatch). `mouse_update_rate` throttles actual writes: skip write if `(now - last_write) < 1000/mouse_update_rate ms`. | Matches existing keyboard path (no new thread, no GIL concerns). SetCursorPos is sub-microsecond; throttling is optional. | Yes |
| MotionIntent shape | Thin frozen dataclass adapter wrapping `PlayerState.lane`, `PlayerState.posture == JUMP`, `PlayerState.posture == SLIDE`, `Ability.HOVERBOARD in abilities`. Built via `MotionIntent.from_player_state(ps)`. | Spec: "lightweight internal representation". PlayerState already exists and serves the same role for keyboard; we don't duplicate its fields, we re-expose the boolean view the mouse needs. | Yes |
| F8/F9 key codes | F8 = toggle pause/resume mouse output; F9 = reset cursor to scrcpy-window center. cv2.waitKeyEx returns stable codes for F-keys on Windows (F8=0x420000, F9=0x430000). | Spec named F8/F9 as examples for emergency toggle + reset. Existing code already uses cv2.waitKeyEx for K/Esc/Ctrl+D. | Yes |
| Esc behavior | Freeze cursor (stop movement), do NOT move cursor back to center. Existing main.py:145-149 uses Esc to disable keyboard and release held keys; mouse equivalent = stop emitting movement. | Spec: emergency stop should not surprise the user with cursor motion. | Yes |
| LOST/ERROR state behavior | Freeze cursor in place (stop movement). Do NOT snap to center; do NOT release the clamp. | Spec: "Prevent cursor escaping to the desktop". Snapping could cause unwanted game input; releasing risks taskbar interaction. Freezing is safest for expo. | Yes |
| Cursor reset target | F9 moves cursor to the geometric center of the inner scrcpy client rect (computed from GetClientRect + ClientToScreen). | Spec: "Move cursor to center of scrcpy window." | Yes |
| scrcpy launch contract | Document that scrcpy must be started as: `scrcpy --window-title "scrcpy-mouse-target" --mouse=sdk` (default mouse mode). The MouseController will look up the window by that exact title. | Research confirms: default title = device model (unstable across devices); `--window-title` makes it deterministic; `--mouse=sdk` (default) sees `SetCursorPos` movement. UHID/AOA modes capture the cursor and break absolute movement. | Yes |
| Tests | `tests/test_motion_intent.py` + `tests/test_mouse_controller.py` using `unittest` (matches existing test_action_executor.py pattern). TDD: write tests first for MotionIntent mapping and clamping math; tests-after for the ScrcpyWindow ctypes integration (mocked). | Existing repo uses unittest (see tests/test_action_executor.py). | Yes |
| Performance budget | MouseController adds < 0.5ms per frame (one SetCursorPos call + simple arithmetic). No regression to the existing RollingProfiler/FPS. Add a `mouse_latency_ms` field to DiagnosticRow for parity with `keyboard_latency_ms`. | Spec: "No noticeable FPS regression", "Cursor movement latency should feel immediate". | Yes |

## Findings (cited - path:lines)

### Internal codebase

- **main.py:32-65** — keyboard path instantiation and dispatch. `KeyboardController` + `ActionExecutor` are constructed here. `executor.execute_posture_ability(controller.last_result)` produces KeyboardEvents; `executor.execute_lane(*state_result)` produces lane-change events. `keyboard.dispatch(events)` emits them.
- **main.py:141-188** — key handling: K toggles `keyboard_enabled`, Esc disables keyboard + `keyboard.shutdown()`, Q quits, Ctrl+D toggles diagnostics, P toggles perf overlay, [ ] cycle presets, S saves, R recalibrates.
- **main.py:107-139** — diagnostic logger records `keyboard_latency_ms = timer.elapsed_ms("update", "keyboard")` and tags events with "Keyboard Sent". Need to rename/repurpose for mouse.
- **controller/keyboard_controller.py:1-73** — `KeyboardController` shape: constructor takes `AppConfig`, `dispatch(events)` consumes `KeyboardEvent` iterable, `held_labels` / `event_history` / `last_event` exposed for the visualizer. `shutdown()` releases held keys. MouseController should expose similar surface (e.g., `current_position`, `last_write_time`, `is_active`).
- **controller/keyboard_events.py:1-19** — `KeyboardEvent(timestamp, command, key, type, reason)`. The mouse path does not need an event queue — the cursor is driven by *current* state, not *transitions*. So we skip an event-queue layer entirely.
- **controller/action.py:94-122** — `PlayerState` already contains everything the mouse needs: `lane` (LEFT/CENTER/RIGHT), `posture` (JUMP/SLIDE/RUNNING), `abilities` (HOVERBOARD set). `MotionIntent.from_player_state()` is a thin projection.
- **controller/action_executor.py:1-105** — the keyboard executor is *transition-driven* (tap on lane change, hold/release for slide). The mouse is *state-driven* (continuous movement while state is active). Different paradigm — we do NOT reuse ActionExecutor for mouse.
- **controller/app_controller.py:54-125** — `AppController.update(frame)` produces `controller.last_result` (PlayerState), `controller.events_this_frame` (lane-change tuples), `controller.state` (AppState). MouseController consumes `last_result` directly each frame; the `events_this_frame` lane-change tuples become irrelevant for mouse (continuous movement subsumes them).
- **utils/config.py:42-138** — `AppConfig` dataclass. New fields go here. `save_settings()` only persists fields that differ from defaults, so adding new fields is safe.
- **utils/config.py:30-38** — `KeyMap` dataclass for keyboard bindings. Not needed for mouse; leave as-is (out of scope to delete).
- **ui/visualizer.py:355-505** — `_draw_keyboard_panel` + sidebar code references `keyboard.held_labels`, `keyboard.last_event`, `keyboard.event_history`. Must replace with mouse-panel equivalents.
- **utils/diagnostic.py:9-29** — `DiagnosticRow` has `keyboard_latency` field. Add `mouse_latency_ms` (do not remove the keyboard one — leave as 0.0 for backward CSV compatibility).
- **tests/test_action_executor.py:1-88** — unittest pattern. New tests follow the same `setUp` + `test_*` conventions.
- **presets/default.json** — existing preset JSON. Add `cursor_speed_x`, `cursor_speed_y`, `mouse_update_rate` here so they can be tuned per-preset like other params.

### External research (librarian reports — bg_1f2c0790, bg_49d5fc28)

**pynput mouse on Windows:**
- `mouse.Controller.position = (x,y)` calls Win32 `SetCursorPos` directly — NOT SendInput or mouse_event. Source: `lib/pynput/mouse/_win32.py:56-78` in moses-palmer/pynput master.
- `SetCursorPos` is absolute and bypasses the Windows mouse acceleration curve ("Enhance pointer precision" does NOT affect it). Pixel-exact placement.
- `.position = (x,y)` is preferred over `.move(dx,dy)` for per-frame control: idempotent, no drift accumulation if a frame is dropped. Sub-microsecond call, trivial at 60 FPS.
- **Critical gotcha:** on HiDPI Windows (scaling >100%), Listener receives physical pixels while Controller works in scaled pixels. Fix at startup: `ctypes.windll.shcore.SetProcessDpiAwareness(2)`.
- pynput 1.7.x is sufficient (the API is stable since 1.0). Repo pin `pynput>=1.7.0` does not need to change.
- Docs: https://pynput.readthedocs.io/en/latest/mouse.html

**scrcpy window detection on Windows:**
- Default scrcpy window title = device model (e.g., "SM-S908B"). NOT stable across devices.
- `--window-title "scrcpy-mouse-target"` sets a deterministic title (documented in `doc/window.md` and verified in `app/src/cli.c`).
- `ctypes` + `user32.FindWindowW(None, title)` is sufficient — no `pygetwindow`/`pywin32` needed.
- `GetWindowRect` returns screen coords INCLUDING title bar + borders + invisible resize borders. NOT what we want for clamping.
- `GetClientRect` + `ClientToScreen` returns the inner client rect — this IS what we want for clamping.
- scrcpy is built on SDL. In default `--mouse=sdk` mode, it consumes normal OS mouse events via SDL — `SetCursorPos`-driven movement IS seen. In `--mouse=uhid`/`--mouse=aoa` modes, scrcpy calls `SDL_SetRelativeMouseMode` and captures the cursor (cursor disappears) — `SetCursorPos` will NOT work there. **Must document: launch scrcpy with `--mouse=sdk` (which is the default).**
- Docs: https://github.com/Genymobile/scrcpy/blob/master/doc/window.md, https://github.com/Genymobile/scrcpy/blob/master/doc/mouse.md

## Decisions (with rationale)

1. **Reuse pynput, do not add new deps.** pynput is already in requirements.txt and its `mouse.Controller.position` setter uses `SetCursorPos` (absolute, no acceleration). pyautogui or pywin32 would add weight for no gain.
2. **Use ctypes (stdlib) for window detection, not pygetwindow.** `FindWindowW + GetClientRect + ClientToScreen` is a ~30-line recipe with zero new deps. pygetwindow would add a transitive dependency for a 30-line task.
3. **MotionIntent is a thin adapter, not a parallel state machine.** PlayerState already contains lane + posture + abilities. MotionIntent re-exposes these as booleans (`jump_active`, `slide_active`, `hoverboard_active`) the mouse controller reads. We do NOT recompute or duplicate detector logic.
4. **MouseController is state-driven, not transition-driven.** Unlike `ActionExecutor` (which fires on posture/lane transitions), the mouse moves continuously while a state is active. So there is no event queue — `MouseController.update(intent, dt)` is called every frame.
5. **Velocity model: `delta = speed × dt`, clamped to inner rect.** Center lane → horizontal delta = 0. LEFT → delta_x = -speed_x × dt. RIGHT → delta_x = +speed_x × dt. JUMP → delta_y = -speed_y × dt. SLIDE → delta_y = +speed_y × dt. When both lane and posture are active, both axes move (diagonal). This matches the "analog joystick" spec.
6. **DPI awareness set once at startup.** Required by pynput docs for HiDPI Windows laptops (which is the typical expo hardware).
7. **Esc = freeze (no snap).** Existing Esc semantics on keyboard = disable + release. Mouse equivalent = stop emitting movement; cursor stays where it is. F9 is the explicit "snap to center" key.
8. **LOST/ERROR = freeze cursor in place.** Do not snap, do not release the clamp. Safest for expo.
9. **Keep keyboard module files on disk, don't import them in main.py.** Reversible, low-risk, leaves main branch unaffected when expo branch merges back. (Pending user confirmation in Open Question Q2.)
10. **Add `mouse_latency_ms` to DiagnosticRow, keep `keyboard_latency_ms` field for CSV backward compatibility.**
11. **F8/F9 codes:** cv2.waitKeyEx returns stable codes on Windows for F-keys. F8 toggles `mouse_enabled`, F9 calls `mouse_controller.reset_to_center()`. Existing K/Esc/Ctrl+D/P/[/]/S/R key handlers remain unchanged.

## Scope IN

- New file `controller/motion_intent.py` — `MotionIntent` dataclass + `from_player_state()` factory.
- New file `controller/mouse_controller.py` — `MouseController` class with `update(intent, dt)`, `reset_to_center()`, `pause()`, `resume()`, `shutdown()`, properties `current_position`, `is_active`, `last_write_time`.
- New file `controller/scrcpy_window.py` — `ScrcpyWindow` class with `find()` (returns inner rect or None), `center()` (returns center point of inner rect), supports manual override bounds from config.
- Modify `utils/config.py` — add `cursor_speed_x: float`, `cursor_speed_y: float`, `scrcpy_window_bounds: tuple[int,int,int,int] | None`, `mouse_update_rate: int`, `scrcpy_window_title: str`, `mouse_enabled_default: bool`.
- Modify `presets/default.json` — add the new cursor params with sensible defaults.
- Modify `main.py` — drop KeyboardController/ActionExecutor imports; instantiate MouseController + ScrcpyWindow; build MotionIntent from `controller.last_result` each TRACKING frame; dispatch via `mouse_controller.update(intent, dt)`; add F8/F9 key handlers; add DPI awareness call at top of `main()`.
- Modify `ui/visualizer.py` — replace `_draw_keyboard_panel` with `_draw_mouse_panel` showing: Mouse Backend: ACTIVE/PAUSED, Cursor (x,y), Lane, Jump, Slide, Scrcpy bounds, Last write ms ago.
- Modify `utils/diagnostic.py` — add `mouse_latency_ms: float = 0.0` field; populate in main loop.
- New file `tests/test_motion_intent.py` — verify `from_player_state()` mapping for all 6 Action cases (LEFT, RIGHT, CENTER, JUMP, SLIDE, HOVERBOARD).
- New file `tests/test_mouse_controller.py` — verify clamping math, continuous movement, freeze-on-pause, reset-to-center, velocity model with a fake/stub clock.
- New file `tests/test_scrcpy_window.py` — verify manual-override bounds path (auto-detect path is integration-test territory; mock ctypes calls).
- Update `README.md` — add an "Expo Branch" section documenting: scrcpy launch command, F8/F9 controls, cursor params, scope (mouse-only, no clicks).

## Scope OUT (Must NOT have)

- ❌ Modify any detector logic (lane_detector.py, jump_detector.py, slide_detector.py, hoverboard_detector.py, gesture_classifier.py).
- ❌ Modify calibration (calibration.py, calibration_wizard.py) or CalibrationData.
- ❌ Modify the lane tracker, state manager, position tracker, motion event types.
- ❌ Modify the pose/hand providers, pose_frame, pose_smoother, pose_tracker, landmarks.
- ❌ Modify the camera, performance, cooldown utilities (except adding the mouse_latency field to diagnostic.py).
- ❌ Emit any keyboard events from main.py in the expo branch.
- ❌ Mouse click handling, right-click, drag, scroll.
- ❌ Cursor acceleration curves (we use raw velocity × dt).
- ❌ Android APK, accessibility service, Bluetooth, Wi-Fi, hand tracking (already exists, but no NEW hand-tracking work).
- ❌ Changes to MediaPipe model complexity, inference scheduling, or processing mode.
- ❌ Changes to detector thresholds, calibration ratios, or adaptive baseline.
- ❌ New git submodules, new pip dependencies (everything must come from stdlib + existing requirements.txt).
- ❌ Delete or rewrite the existing keyboard controller files (pending Q2 — default is "keep unused").
- ❌ Multithreading for mouse output (stay on the main loop to match the existing keyboard pattern).

## Open questions

(RESOLVED — see Decisions below.)

## Decisions (user-confirmed on Q1 + Q2)

**Q1 — scrcpy bounds detection strategy: Auto-detect + manual fallback + cached bounds with periodic refresh.**
- scrcpy window title = `"MotionRunner-Expo"` (user-chosen name, more memorable than the generic `scrcpy-mouse-target`).
- At startup: `FindWindowW(None, "MotionRunner-Expo")`. If found, get inner rect via `GetClientRect` + `ClientToScreen`, cache. If not found, print WARNING and load `mouse_fallback_bounds` from settings.json. No crash.
- During runtime: refresh window bounds every `mouse_bounds_refresh_ms` (default 200ms = 5 Hz), NOT every frame. `FindWindowW` + coord conversion are cheap but pointless at 60 FPS since users don't continuously move the scrcpy window.
- If the window disappears mid-demo: pause cursor updates, display "Mouse Backend: WAITING FOR SCRCPY" on the overlay, retry every `mouse_window_retry_ms` (default 1000ms = 1 Hz) until it returns. Resume automatically when found.
- Config fields are flat (matching the existing AppConfig style), not nested under `mouse:`. Fields: `mouse_window_title`, `mouse_auto_detect_window`, `mouse_fallback_bounds`, `mouse_bounds_refresh_ms`, `mouse_window_retry_ms`.
- BONUS deliverable: `start_expo.bat` at repo root — launches `scrcpy --window-title MotionRunner-Expo --max-size 1080`, waits 2s, then `python main.py`. Expo booth setup becomes: connect phone via USB → double-click `start_expo.bat` → stand in front of camera.

**Q2 — Keyboard module disposition: Keep all keyboard files untouched, isolate by not importing.**
- `controller/keyboard_controller.py`, `controller/action_executor.py`, `controller/keyboard_events.py`, `KeyMap` in `utils/config.py`, `tests/test_action_executor.py` — all remain on disk exactly as they are. Do NOT modify, delete, or refactor them.
- main.py simply stops importing/instantiating `KeyboardController` and `ActionExecutor`.
- The existing `tests/test_action_executor.py` continues to pass (it tests ActionExecutor in isolation).
- No `output_backend` config flag — keep main.py simple for the expo.
- The user's hard constraint (verbatim): "This is not a refactor. Do not modify the pose pipeline, calibration, detectors, smoothing, adaptive thresholds, or performance code. Do not rewrite the application architecture. Treat the existing pipeline as a black box that produces motion events. The only task is to replace the final output sink from KeyboardController to MouseController while leaving the rest of the system functionally identical."

## Approval gate
status: approved
<!-- User answered both forks in detail on 2025-07-19. Treated as approval to write the plan file. Proceeding to scaffold + Metis + todos. -->
approach: Auto-detect scrcpy window via ctypes FindWindowW (title "MotionRunner-Expo"), refresh every 200ms, manual fallback bounds from config, WAITING-FOR-SCRCPY state on disappearance. Keep all keyboard files untouched; main.py stops importing them. MotionIntent = thin adapter from PlayerState. MouseController = inline in main loop, pynput mouse.position each frame throttled by mouse_update_rate. Velocity model with clamp to inner client rect. DPI awareness at startup. F8 pause, F9 reset, Esc freeze. Add start_expo.bat launcher.

## Metis gap analysis result
- Reviewer: Metis (bg_e58a606d, ses_08744883effe5k42gki9NVbvmp), completed 2025-07-19.
- Findings: 2 BLOCKERS (config field name inconsistency across draft sections — resolved in plan T1 which uses the canonical Q1 list; scrcpy title inconsistency — resolved to "MotionRunner-Expo" in plan T1/T5/T9). 14 MAJORS folded into the plan: F8/F9 code verification note added to T8; FindWindowW exact-match risk noted in T3 references; SetProcessDpiAwareness side-effect verification added to T8; HOVERBOARD no-op behavior specified in T6; F8+F9 interaction (F9 works while paused, does not unpause) specified in T6; TRACKING→LOST→TRACKING resume-from-frozen specified in T6; cv2 focus constraint documented in T8 + T9; integration test (mock pynput, assert position setter called) added as T6 test case (o); "no keyboard events" grep guard added to T8 acceptance criteria; viz.draw() signature + _draw_sidebar call site explicitly in T7; LOST/ERROR branch wiring (mouse.pause()) explicitly in T8 step (6); start_expo.bat + README noted as user-requested (Q1 answer); misleading-success-output guard added as T6 test case (o); diagnostic field name corrected to `keyboard_latency` (not `keyboard_latency_ms`) in T8 references. 5 MINORs + 2 NITs fixed inline.
- Verdict: all BLOCKERS and MAJORS resolved in the plan; plan is decision-complete.
- Independent Oracle review: NOT run (review_required: false per CLEAR intent without explicit high-accuracy modifier).

## User simplification pass (2025-07-19, post-Metis)
The user reviewed the 9-todo plan and rated it 8.8/10 — architecture solid but over-engineered for an expo demo. Requested 9 changes, all applied to the plan (now 7 todos):

1. **DROP MotionIntent entirely.** MouseController consumes `PlayerState` directly. No adapter layer, no `controller/motion_intent.py`, no `tests/test_motion_intent.py`. Rationale: "You already have PlayerState. Why create PlayerState → MotionIntent → MouseController? It buys almost nothing. Unless you're planning Mouse/Keyboard/Gamepad/UDP/OSC as interchangeable backends later, I'd skip MotionIntent."
2. **Reduce config from 8 fields to 3.** Only `cursor_speed` (single value, not separate x/y), `mouse_window_title`, `mouse_bounds_refresh_ms`. Dropped: `cursor_speed_x`, `cursor_speed_y`, `mouse_update_rate`, `mouse_window_retry_ms`, `mouse_auto_detect_window`, `mouse_fallback_bounds`, `mouse_emergency_keys`, `mouse_enabled_default`. Rationale: "For an expo, you probably need cursor_speed, window_title, refresh_ms. That's enough. Keep the config small."
3. **Collapse WAITING into PAUSED.** Only 2 states: ACTIVE and PAUSED. If scrcpy disappears → PAUSED (derived from `is_active = not user_paused and window.is_available`). When scrcpy returns → ACTIVE (auto-resume, no explicit resume() needed). No WAITING state, no retry logic. Rationale: "If scrcpy disappears, PAUSED is sufficient. No need for another state."
4. **Remove mouse update throttling.** Write every frame. SetCursorPos is sub-microsecond; the main loop is already 45-60 FPS. Dropped `mouse_update_rate` config field and throttle logic. Rationale: "Why throttle again? Just every frame → SetCursorPos(). It's extremely cheap."
5. **Don't touch DiagnosticRow/CSV/Logger/Summary.** Dropped T4 (diagnostic field addition). `utils/diagnostic.py` stays byte-identical. In main.py, the existing `keyboard_latency` field is populated with the mouse timer value (field name stays, value changes). Rationale: "Those are stable. Changing diagnostics creates unnecessary risk."
6. **Visualizer: rename, don't replace.** Renamed `_draw_keyboard_panel` → `_draw_output_panel` (minimal change, same panel structure, updated fields). Rationale: "I'd just rename it. Output Backend / ACTIVE / Cursor / Lane / Jump / Slide. Small change. Less code."
7. **DPI awareness: NOT called by default.** Added as a commented-out line in main.py: `# import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Uncomment if cursor alignment is off on HiDPI displays`. Rationale: "I wouldn't do it initially. Changing DPI awareness can affect OpenCV windows, coordinate calculations, screen scaling. Test on the actual expo laptop first. Only add DPI awareness if cursor alignment is actually wrong."
8. **ADD: Auto-center cursor after calibration.** When AppState transitions CALIBRATING → TRACKING, call `mouse.reset_to_center()`. Rationale: "After body calibration finishes, automatically do cursor → center(scrcpy). Now every participant starts from center instead of last participant's cursor position. Makes demos much smoother."
9. **ADD: Controls legend overlay.** Small semi-transparent box on cv2 preview showing "MOUSE MODE / ← LEFT / ↑ JUMP / ↓ SLIDE / → RIGHT". Rationale: "People at an expo won't know 'lean left → cursor moves left' unless you show them. Visitors understand it instantly."

**Net effect:** Plan went from 9 todos to 7 todos. Removed 2 files (motion_intent.py + test), removed 1 file modification (diagnostic.py), removed 5 config fields, removed WAITING state machine, removed throttling logic, removed DPI awareness call. Added auto-center-on-calibration and controls legend overlay. Plan is now focused on the expo demo question: "Can a person stand in front of a webcam and control the cursor inside scrcpy using the existing MotionRunner detectors?"
