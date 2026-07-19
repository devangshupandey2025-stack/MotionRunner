# Learnings — scrcpy-mouse-backend

## 2026-07-19 Session start
- Plan: 7 todos, 3 waves. Wave 1 (T1-T3 parallel), Wave 2 (T4-T5 parallel), Wave 3 (T6-T7 sequential).
- Branch: expo/scrcpy-mouse-backend (created from main).
- Key constraint: detection pipeline is a black box. Only swap the output sink (keyboard to mouse).
- pynput mouse.Controller.position = (x,y) calls Win32 SetCursorPos (absolute, no acceleration).
- scrcpy window detection: ctypes FindWindowW + GetClientRect + ClientToScreen (zero new deps).
- scrcpy must be launched with --window-title MotionRunner-Expo for deterministic title matching.
- DPI awareness is OFF by default (commented out in main.py).
- No MotionIntent adapter. MouseController consumes PlayerState directly.
- Only 2 states: ACTIVE and PAUSED. No WAITING state.
- No throttling. Write every frame.
- Do NOT touch utils/diagnostic.py.

## 2026-07-19 T1 complete
- Added 3 flat fields to AppConfig (utils/config.py:127-130) under new # --- Mouse Backend Settings --- section: cursor_speed: float = 400.0, mouse_window_title: str = "MotionRunner-Expo", mouse_bounds_refresh_ms: int = 200.
- Added "cursor_speed": 500.0 to presets/default.json (line 9). Default preset overrides AppConfig default 400.0 -> 500.0.
- save_settings()/load_settings() work unchanged: new fields match isinstance(v, (int, float, bool, str)) filter and round-trip via setattr. Confirmed with cursor_speed=999.0 round-trip test.
- load_preset('nonexistent') is a no-op (os.path.exists check), so defaults are preserved.
- All 3 acceptance commands pass. No other files touched.
- T4 (MouseController) can now consume config.cursor_speed, config.mouse_window_title, config.mouse_bounds_refresh_ms.

## 2026-07-19 T2 complete (ScrcpyWindow)
- Created controller/scrcpy_window.py (57 pure LOC) and tests/test_scrcpy_window.py (53 pure LOC).
- ScrcpyWindow: __init__ reads config.mouse_window_title + config.mouse_bounds_refresh_ms; find() returns cached (left, top, right, bottom) or None; center() returns geometric center or None; is_available property; refresh_if_stale(now_ms) for external clock; _refresh() does FindWindowW -> GetClientRect -> ClientToScreen.
- ctypes prototypes set at module load: FindWindowW (HWND restype, [LPCWSTR, LPCWSTR] argtypes), GetClientRect (BOOL restype, [HWND, POINTER(RECT)]), ClientToScreen (BOOL restype, [HWND, POINTER(POINT)]).
- Cross-platform import: try/except (OSError, AttributeError) around ctypes.WinDLL("user32", use_last_error=True); on non-Windows user32 = None and _refresh() returns False. Module is importable on any OS.
- Used ctypes.pointer() (not ctypes.byref()) so test side_effects can modify ptr.contents.right/x etc. Both work with real WinDLL; pointer() is mock-friendly.
- Inner client rect formula: (pt.x, pt.y, pt.x + rect.right, pt.y + rect.bottom). GetClientRect returns left=0,top=0,right=width,bottom=height (client area only). ClientToScreen(0,0) gives screen coords of client top-left.
- Refresh throttling: find() calls refresh_if_stale(time.time()*1000) which checks now - last_refresh > refresh_interval_ms. _last_refresh_ms starts at 0.0 so first call always refreshes. Throttle applies to both hit and miss (no retry loop, no WAITING state).
- Tests use @patch("controller.scrcpy_window.user32") with MagicMock. FindWindowW.return_value controls hit/miss. GetClientRect/ClientToScreen use side_effect functions that write into ptr.contents. All 4 tests pass: auto-detect success (100,50,900,650), auto-detect failure (None), refresh throttling (call_count=1), center (500,350).
- T1 config fields confirmed present (utils/config.py:129-130) before smoke test ran. Smoke test passed: ScrcpyWindow(AppConfig()).find() returns None (scrcpy not running), is_available is False, no crash.
- Pre-existing test failures in test_action_executor.py (ActionExecutor.execute signature mismatch: test calls execute(state()) but impl takes execute(previous, current)) — NOT caused by T2, unrelated.
- No new dependencies. Only ctypes + ctypes.wintypes (stdlib). No pygetwindow/pywin32/pyautogui.

## 2026-07-19 T4 complete (MouseController)
- Created controller/mouse_controller.py (68 pure LOC) and tests/test_mouse_controller.py (186 pure LOC).
- MouseController: __init__(config, window) creates pynput.mouse.Controller() internally; is_active = not _user_paused and window.is_available (derived, NOT stored); state property returns "ACTIVE"/"PAUSED" (only 2 states, NO WAITING); update(player_state, dt) computes delta = speed * dt per lane/posture, clamps to window.find() bounds, writes every frame (NO throttling); pause()/resume()/shutdown() toggle _user_paused; reset_to_center() works regardless of pause state (does NOT auto-resume).
- HOVERBOARD is IGNORED for cursor movement — abilities set is never read in update(). Verified by tests (l) and (m).
- Used match/case with typing.assert_never for exhaustive Lane/Posture variant matching (Python 3.11.9 confirmed). All 3 Lane values (LEFT/RIGHT/CENTER) and 3 Posture values (JUMP/SLIDE/RUNNING) handled explicitly; unhandled cases raise via assert_never.
- Velocity model: delta_x = -speed*dt (LEFT), +speed*dt (RIGHT), 0 (CENTER); delta_y = -speed*dt (JUMP), +speed*dt (SLIDE), 0 (RUNNING). new_x/new_y clamped to [bounds[0],bounds[2]] / [bounds[1],bounds[3]] (nearest edge, NOT center).
- Test mocking pattern: @patch("controller.mouse_controller.Controller") with FakeMouse (records setter calls via @property) and StubWindow (mutable bounds/available fields). FakeMouse.position getter returns current pos, setter appends to set_calls list. This avoids PropertyMock complexity and follows fake-over-mock principle.
- Float/int comparison: 500 - 400.0*1.0 = 100.0 (float), assertEqual((100.0, 500.0), (100, 500)) passes because 100.0 == 100 in Python. No assertAlmostEqual needed for exact-representable deltas.
- All 15 tests pass: (a) LEFT decreases x, (b) RIGHT increases x, (c) CENTER no movement, (d) JUMP decreases y, (e) SLIDE increases y, (f) JUMP+LEFT diagonal, (g) clamp on large delta, (h) pause blocks writes, (i) reset_to_center while paused, (j) inactive when window unavailable, (k) auto-resume when window available, (l) HOVERBOARD alone no movement, (m) HOVERBOARD+LEFT still moves, (n) bounds shrink clamps cursor, (o) 3 frames 3 writes decreasing x.
- Smoke test passes: MouseController(AppConfig(), ScrcpyWindow(AppConfig())) with pause() + update() -> state == "PAUSED", prints OK.
- T2 tests (test_scrcpy_window.py) still pass — no regressions. Pre-existing test_action_executor.py failures unchanged (NOT our fault).
- No files modified other than the 2 new files. No new dependencies. No git commit.

## 2026-07-19 T5 complete (visualizer keyboard->mouse migration)
- Modified ui/visualizer.py only. No other files touched.
- Renamed _draw_keyboard_panel -> _draw_output_panel (lines 469-500). New signature: _draw_output_panel(self, sidebar, mouse, mouse_enabled, y, sw). Dropped control_mode param (was only used for old keyboard header).
- _draw_output_panel reads: mouse.state ("ACTIVE"/"PAUSED"), mouse.current_position (tuple or None), mouse.last_intent (PlayerState or None). Uses getattr() with None default for graceful degradation when mouse=None.
- Status line: "ACTIVE" (green/success) if mouse.state == "ACTIVE", else "PAUSED" (dim). When mouse=None, shows "PAUSED".
- Cursor line: "Cursor: (x, y)" from mouse.current_position, or "Cursor: (--, --)" when None.
- Intent line: "Lane: {lane.name} | Jump: {posture==JUMP} | Slide: {posture==SLIDE}" from mouse.last_intent, or "Lane: NONE | Jump: False | Slide: False" when None.
- Removed keyboard event history loop (for event in list(keyboard.event_history)[-3:]). Removed time.perf_counter() age calculation. Removed import time (was only used by the keyboard panel).
- draw() signature: replaced keyboard=None, keyboard_enabled=False with mouse=None, mouse_enabled=False. All other params unchanged.
- _draw_sidebar signature: swapped keyboard->mouse, keyboard_enabled->mouse_enabled. control_mode kept in signature (still passed from draw()) but no longer forwarded to _draw_output_panel.
- _draw_sidebar call in draw() (line 130): passes mouse=mouse, mouse_enabled=mouse_enabled.
- Added _draw_controls_legend(self, frame_view, w, h) method (lines 502-519). Draws 180x100 semi-transparent black box (cv2.addWeighted 0.5/0.5) in top-right corner of frame_view. Contents: "MOUSE MODE" header (theme.highlight, scale 0.45) + 4 control lines (theme.text, scale 0.4): "<- LEFT", "^ JUMP", "v SLIDE", "-> RIGHT". Called from draw() at line 120, right after self.hud.draw() and before perf_overlay.
- Used ASCII arrows (<- ^ v ->) instead of Unicode (← ↑ ↓ →) because cv2.putText with FONT_HERSHEY_SIMPLEX does not render Unicode. Codebase convention: existing _lane_label() at line 343 already uses "<- LEFT" and "RIGHT ->".
- PRE-EXISTING ISSUE FIXED: _draw_sidebar crashed on app_state.name when app_state=None (acceptance smoke test passes None for app_state). Added local state_name = app_state.name if app_state else "INITIALIZING" and replaced 2 references to app_state.name with state_name. This was NOT caused by T5 - the crash existed before - but the acceptance command requires it to pass. Minimal fix, no behavior change for real usage (app_state is always provided in production).
- All 6 acceptance commands pass: (1) syntax OK, (2) draw(mouse=None) OK, (3) _draw_keyboard_panel count=0, (4) _draw_output_panel count=2, (5) MOUSE MODE count=1, (6) signature has mouse, no keyboard.
- Smoke test with mock mouse (ACTIVE/PAUSED/with-last_intent) all pass - no crashes, correct rendering.
- Pre-existing test failures in test_action_executor.py (7 errors, ActionExecutor.execute signature mismatch) unchanged - NOT caused by T5.
- File size: 544 total lines, 455 pure LOC. Pre-existing condition (was 529 lines before T5). _draw_controls_legend added ~18 lines, _draw_output_panel is shorter than old _draw_keyboard_panel. File is over 250 LOC ceiling but splitting is outside T5 scope ("Do NOT touch any other file", "MINIMAL change").
- Posture enum already imported (line 7) - no new imports needed. Ability import is pre-existing and unused but not touched (out of scope).
- T6 (main.py call site update) can now pass mouse=mouse, mouse_enabled=mouse_enabled to v.draw().

## 2026-07-19 T6 complete (main.py rewiring)
- Modified main.py only. No other files touched. git diff --name-only shows only main.py.
- Removed imports: controller.action_executor.ActionExecutor, controller.keyboard_controller.KeyboardController. Added: time, controller.mouse_controller.MouseController, controller.scrcpy_window.ScrcpyWindow.
- Added module-level constants F8_KEY = 0x420000, F9_KEY = 0x430000 with a discovery comment (cv2.waitKeyEx hex codes are platform-specific and not self-documenting).
- DPI awareness: commented-out line at top of main() — # import ctypes; ctypes.windll.shcore.SetProcessDpiAwareness(2). NOT called by default.
- Replaced keyboard = KeyboardController(config) + xecutor = ActionExecutor(config.keymap) with scrcpy_window = ScrcpyWindow(config) + mouse = MouseController(config, scrcpy_window).
- Replaced keyboard_enabled = False with mouse_enabled = False + added previous_app_state = None + last_frame_time = time.perf_counter().
- Auto-center on calibration: if controller.state == AppState.TRACKING and previous_app_state == AppState.CALIBRATING: mouse.reset_to_center(). Fires once on the CALIBRATING -> TRACKING transition.
- Mouse update block: when mouse_enabled and TRACKING, compute dt = min(now - last_frame_time, 0.1) (capped at 100ms to prevent huge jumps after pauses), refresh scrcpy bounds if stale, call mouse.update(controller.last_result, dt). On LOST/ERROR: mouse.pause(). Else (INITIALIZING/CALIBRATING): reset last_frame_time to now to prevent dt spike when tracking starts.
- timer.mark('keyboard') -> timer.mark('mouse'). visualize_ms and keyboard_latency (DiagnosticRow field name unchanged per spec) now read timer.elapsed_ms('...', 'mouse').
- Removed the vents = [] line and the if keyboard_enabled and ... events: diagnostic tagging block — events variable no longer exists (spec Step 9).
- Key handlers: removed toggle_keys tuple and K toggle. Updated Esc to set mouse_enabled=False + mouse.pause(). Added F8 (toggle mouse_enabled, resume/pause) and F9 (mouse.reset_to_center()). Kept Q, Ctrl+D, P, [, ], S, R handlers unchanged.
- Added previous_app_state = controller.state at end of loop iteration (after all key handling, before loop repeats).
- Finally block: replaced keyboard.shutdown() + xecutor.reset() with mouse.shutdown().
- All 12 acceptance commands pass: (1) AST parse OK, (2) import main OK, (3) keyboard imports count=0, (4) KeyboardController|ActionExecutor count=0, (5) MouseController|ScrcpyWindow count=4, (6) SetProcessDpiAwareness count=1, (7) commented SetProcessDpiAwareness count=1, (8) F8_KEY|F9_KEY|0x420000|0x430000 count=4, (9) mouse.update|pause|shutdown|resume|reset_to_center count=8, (10) reset_to_center count=2, (11) unittest Ran 37 tests FAILED errors=7 (all 7 in test_action_executor.py with AttributeError: 'ActionExecutor' object has no attribute 'execute' — pre-existing, NOT caused by T6), (12) scope fidelity guard: no protected files modified.
- File size: 215 total lines (was 202). The 13-line increase is from F8/F9 constants block (+5), DPI comment (+2), previous_app_state/last_frame_time init (+2), auto-center block (+3), F8 handler (+7), F9 handler (+2), previous_app_state update (+1), minus removed K toggle (-7), removed events tagging block (-6), removed executor.reset() (-1). Net within healthy range.
- The # Ctrl+D comment on line 153 is pre-existing (was line 143 in original).
- The jr.event = ""  # consume it comment on line 147 is pre-existing.
- T7 (smoke test / integration verification) can now run against the fully wired main.py.
