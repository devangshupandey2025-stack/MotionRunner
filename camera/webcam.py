import cv2
from utils.config import AppConfig


class Webcam:
    def __init__(self, config: AppConfig):
        self.config = config
        self._cap = cv2.VideoCapture(config.camera_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera at index {config.camera_index}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)
        self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)

        ret, test_frame = self._cap.read()
        if not ret or test_frame is None:
            self._cap.release()
            raise RuntimeError(f"Camera at index {config.camera_index} opened but returns no frames")

        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def read(self):
        ret, frame = self._cap.read()
        if not ret:
            raise RuntimeError("Failed to read frame from camera")
        if self.config.mirror_camera:
            frame = cv2.flip(frame, 1)
        return frame

    def release(self):
        self._cap.release()
