import cv2

from utils.config import AppConfig, InputMode
from utils.performance import LoopTimer, RollingProfiler, StageSample
from camera.webcam import Webcam
from controller.action_executor import ActionExecutor
from controller.app_controller import AppController, AppState
from controller.keyboard_controller import KeyboardController
from ui.visualizer import Visualizer


def main():
    toggle_keys = (ord("k"), ord("K"))
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
        
    keyboard = KeyboardController(config)
    executor = ActionExecutor(config.keymap)
    viz = Visualizer(config)
    keyboard_enabled = False
    perf_overlay_enabled = False
    loop_profiler = RollingProfiler()
    print(f"Input mode: {controller.input_mode.name}")
    if controller.input_mode == InputMode.HAND:
        print("Hold one open palm in frame to calibrate hand movement.")
        print("Move palm left/right to steer and pinch-hold to trigger hoverboard.")
    else:
        print("Stand in view of the camera to calibrate pose tracking.")
    print("Press K to toggle keyboard control, Esc for emergency stop, Q to quit.\n")

    try:
        while True:
            timer = LoopTimer()
            frame = cam.read()
            timer.mark("capture")
            controller.update(frame)
            timer.mark("update")

            if keyboard_enabled and controller.state == AppState.TRACKING:
                events = executor.execute(controller.last_result)
                keyboard.dispatch(events)
            elif controller.state in (AppState.LOST, AppState.ERROR):
                keyboard.shutdown()
                executor.reset()
            timer.mark("keyboard")

            display = viz.draw(
                frame,
                controller.pose,
                controller.last_result,
                controller.state,
                controller.calibrator,
                wizard=controller.wizard,
                keyboard=keyboard,
                keyboard_enabled=keyboard_enabled,
                perf_overlay_enabled=perf_overlay_enabled,
                control_mode=config.control_mode,
                input_state=controller.last_input,
                input_mode=controller.input_mode,
                hand_landmarks=controller.hand_landmarks,
                perf_stats=controller.perf_stats,
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
                visualize_ms=timer.elapsed_ms("keyboard", "visualize"),
                display_ms=timer.elapsed_ms("visualize", "end"),
                total_ms=timer.total_ms(),
            )
            loop_profiler.add(sample)
            snapshot = loop_profiler.snapshot()
            snapshot.processed_frame = controller.perf_stats.processed_frame
            snapshot.processing_mode = controller.perf_stats.processing_mode
            snapshot.auto_switches = controller.perf_stats.auto_switches
            controller.perf_stats = snapshot

            if key in (ord("q"), ord("Q")):
                break
            if key == 27:
                keyboard_enabled = False
                keyboard.shutdown()
                executor.reset()
                print("Emergency stop: keyboard control disabled and held keys released.")
            elif key in toggle_keys:
                keyboard_enabled = not keyboard_enabled
                if not keyboard_enabled:
                    keyboard.shutdown()
                    executor.reset()
                status = "enabled" if keyboard_enabled else "disabled"
                print(f"Keyboard control {status}.")
                
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
        config.save_settings()
        if controller.calibrator and controller.calibrator.result:
            config.save_calibration(controller.calibrator.result)
        keyboard.shutdown()
        executor.reset()
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
