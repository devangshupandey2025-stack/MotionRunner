import cv2

from utils.config import AppConfig
from camera.webcam import Webcam
from controller.action_executor import ActionExecutor
from controller.app_controller import AppController, AppState
from controller.keyboard_controller import KeyboardController
from ui.visualizer import Visualizer


def main():
    toggle_keys = (ord("k"), ord("K"))
    config = AppConfig()
    cam = Webcam(config)
    controller = AppController(config)
    keyboard = KeyboardController(config)
    executor = ActionExecutor(config.keymap)
    viz = Visualizer(config)
    keyboard_enabled = False

    print("MotionRunner — Milestone 2")
    print("Stand in view of the camera to calibrate.")
    print("Press K to toggle keyboard control, Esc for emergency stop, Q to quit.\n")

    try:
        while True:
            frame = cam.read()
            controller.update(frame)

            if keyboard_enabled and controller.state == AppState.TRACKING:
                events = executor.execute(controller.last_result)
                keyboard.dispatch(events)
            elif controller.state in (AppState.LOST, AppState.ERROR):
                keyboard.shutdown()
                executor.reset()

            display = viz.draw(
                frame,
                controller.pose,
                controller.last_result,
                controller.state,
                controller.calibrator,
                keyboard=keyboard,
                keyboard_enabled=keyboard_enabled,
                control_mode=config.control_mode,
            )

            cv2.imshow("MotionRunner", display)

            key = cv2.waitKeyEx(1)
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

            if controller.state == AppState.ERROR:
                print(f"Error: {controller.error_msg}")
                break
    finally:
        keyboard.shutdown()
        executor.reset()
        cam.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
