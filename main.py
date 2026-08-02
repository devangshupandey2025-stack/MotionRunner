import cv2

from utils.config import AppConfig, InputMode
from utils.performance import LoopTimer, RollingProfiler, StageSample
from camera.webcam import Webcam
from controller.android_swipe_controller import AndroidSwipeController
from controller.app_controller import AppController, AppState
from ui.visualizer import Visualizer
from utils.diagnostic import DiagnosticLogger, DiagnosticRow
from controller.calibration_wizard import WizardState

def main():
    config = AppConfig()
    config.load_settings()
    
    inject_cal = None
    saved_cal = config.load_calibration()
    print("MotionRunner - Phase 3")
    if saved_cal:
        choice = input("Found saved calibration. Press [Enter] to continue or [R] to recalibrate: ")
        if choice.strip().lower() != 'r':
            inject_cal = saved_cal
            
    cam = Webcam(config)
    controller = AppController(config)
    if inject_cal:
        controller.inject_calibration(inject_cal)
        
    android = AndroidSwipeController()
    viz = Visualizer(config)
    android_enabled = False
    perf_overlay_enabled = False
    loop_profiler = RollingProfiler()
    diag_logger = DiagnosticLogger()
    print(f"Input mode: {controller.input_mode.name}")
    if controller.input_mode == InputMode.HAND:
        print("Hold one open palm in frame to calibrate hand movement.")
        print("Move palm left/right to steer and pinch-hold to trigger hoverboard.")
    else:
        print("Stand in view of the camera to calibrate pose tracking.")
    print("Press M to toggle Android swipe control, Esc for emergency stop, Q to quit.")
    print("Press Ctrl+D to toggle Diagnostic Mode.\n")

    try:
        while True:
            timer = LoopTimer()
            frame = cam.read()
            timer.mark("capture")
            controller.update(frame)
            timer.mark("update")

            if android_enabled and controller.state == AppState.TRACKING:
                android.update(controller.last_result)
                for previous_lane, desired_lane in controller.events_this_frame:
                    android.dispatch_lane_change(previous_lane, desired_lane)
            elif controller.state in (AppState.LOST, AppState.ERROR):
                android.clear_pending()
            timer.mark("android")

            display = viz.draw(
                frame,
                controller.pose,
                controller.last_result,
                controller.state,
                controller.calibrator,
                wizard=controller.wizard,
                mouse=android,
                mouse_enabled=android_enabled,
                perf_overlay_enabled=perf_overlay_enabled,
                control_mode=config.control_mode,
                input_state=controller.last_input,
                input_mode=controller.input_mode,
                hand_landmarks=controller.hand_landmarks,
                perf_stats=controller.perf_stats,
                tracking_result=controller.latest_tracking_result,
                state_manager=controller.state_manager,
            )
            timer.mark("visualize")
            cv2.imshow("MotionRunner", display)

            key = cv2.waitKeyEx(1)
            timer.mark("end")
            sample = StageSample(
                capture_ms=timer.elapsed_ms("start", "capture"),
                preprocess_ms=controller.perf_stats.preprocess_ms,
                inference_ms=controller.perf_stats.inference_ms,
                classify_ms=controller.perf_stats.classify_ms,
                visualize_ms=timer.elapsed_ms("android", "visualize"),
                display_ms=timer.elapsed_ms("visualize", "end"),
                total_ms=timer.total_ms(),
            )
            loop_profiler.add(sample)
            snapshot = loop_profiler.snapshot()
            snapshot.processed_frame = controller.perf_stats.processed_frame
            snapshot.processing_mode = controller.perf_stats.processing_mode
            snapshot.auto_switches = controller.perf_stats.auto_switches
            controller.perf_stats = snapshot

            if diag_logger.active:
                row = DiagnosticRow(
                    frame_index=controller.last_input.frame_index if controller.last_input else 0,
                    fps=snapshot.fps,
                    frame_source="REAL" if snapshot.processed_frame else "REUSED",
                    capture_latency=cam.last_capture_ms,
                    inference_latency=snapshot.inference_ms,
                    detector_latency=snapshot.classify_ms,
                    render_latency=snapshot.visualize_ms,
                    keyboard_latency=timer.elapsed_ms("update", "android"),
                    loop_latency=snapshot.total_ms,
                )
                if controller.last_result and controller.last_result.jump_result:
                    jr = controller.last_result.jump_result
                    row.hip_raw_y = jr.raw_tracking_y
                    row.hip_smoothed_y = jr.smoothed_tracking_y
                    row.velocity_instant = jr.instant_velocity
                    row.velocity_averaged = jr.velocity
                    row.above_threshold = jr.above_effective_line
                    row.moving_upward = jr.moving_upward
                    row.confirmation_ms = jr.elapsed_ms
                    if jr.event:
                        row.event = jr.event
                        jr.event = ""  # consume it
                
                diag_logger.record(row)

            if key in (ord("q"), ord("Q")):
                break
            if key == 4: # Ctrl+D
                diag_logger.toggle()
            elif key == 27:
                android_enabled = False
                android.pause()
                print("Emergency stop: Android swipe control disabled.")
            elif key in (ord("m"), ord("M")):
                android_enabled = not android_enabled
                if android_enabled:
                    if not android.resume():
                        android_enabled = False
                        print(f"Android swipe control unavailable: {android.device_label}")
                        continue
                else:
                    android.pause()
                status = "enabled" if android_enabled else "disabled"
                print(f"Android swipe control {status}.")
                
            elif key in (ord("p"), ord("P")):
                perf_overlay_enabled = not perf_overlay_enabled
                
            elif key in (ord("["), ord("]")):
                forward = (key == ord("]"))
                config.cycle_preset(forward)
                if controller.calibrator and controller.calibrator.result:
                    controller.calibrator.result.recompute_lines(config)
                    if hasattr(controller.provider, 'classifier'):
                        controller.provider.classifier.set_calibration(controller.calibrator.result)
                print(f"Preset changed to: {config.active_preset}")
                
            elif key in (ord("s"), ord("S")):
                config.save_settings()
                if controller.calibrator and controller.calibrator.result:
                    config.save_calibration(controller.calibrator.result)
                print("Settings and calibration manually saved.")

            if controller.state == AppState.ERROR:
                print(f"Error: {controller.error_msg}")
                break
                
            if key in (ord("r"), ord("R")):
                if controller.wizard and controller.wizard.state == WizardState.QUALITY_CHECK:
                    controller.wizard.retry()
                elif controller.state == AppState.TRACKING:
                    controller._preloaded_cal = None
                    controller.state = AppState.INITIALIZING
                    print("Recalibrating...")
            elif key != -1 and controller.wizard:
                controller.wizard.advance_from_preview()
    finally:
        if diag_logger.active or len(diag_logger.rows) > 0:
            diag_logger.flush()
        config.save_settings()
        if controller.calibrator and controller.calibrator.result:
            config.save_calibration(controller.calibrator.result)
        android.shutdown()
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
