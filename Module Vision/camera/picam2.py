from picamera2 import Picamera2, Preview
from Module.Vision.camera.camera_base import CameraBase
import numpy as np
import time


class PiCam2(CameraBase):
    def __init__(self):
        self.picam2 = Picamera2()
        self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)}))

    def start(self):
        self.picam2.start()

    def stop(self):
        self.picam2.stop()

    def get_frame(self) -> np.ndarray:
        frame = self.picam2.capture_array()
        return frame