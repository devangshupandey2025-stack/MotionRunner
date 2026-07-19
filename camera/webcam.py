import cv2
import os
from utils.config import AppConfig


class Webcam:
    def __init__(self, config: AppConfig):
        import time
        self.config = config
        # DirectShow avoids the multi-frame Media Foundation queue on Windows,
        # which otherwise makes a live control loop feel sluggish even when its
        # measured processing FPS is acceptable.
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        self._cap = cv2.VideoCapture(config.camera_index, backend)
        if not self._cap.isOpened() and backend != cv2.CAP_ANY:
            self._cap.release()
            self._cap = cv2.VideoCapture(config.camera_index)
        self.last_capture_ms = 0.0
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera at index {config.camera_index}")

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera_height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        ret, test_frame = self._cap.read()
        if not ret or test_frame is None:
            self._cap.release()
            raise RuntimeError(f"Camera at index {config.camera_index} opened but returns no frames")

        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def read(self):
        import time
        t0 = time.perf_counter()
        ret, frame = self._cap.read()
        self.last_capture_ms = (time.perf_counter() - t0) * 1000.0
        
        if not ret:
            raise RuntimeError("Failed to read frame from camera")
        if self.config.mirror_camera:
            frame = cv2.flip(frame, 1)
        return frame

    def release(self):
        self._cap.release()
