#!/usr/bin/env python
# -*- coding: utf-8 -*-
# picam2.py
# ------------------
# Module de gestion de la caméra Raspberry Pi utilisant la bibliothèque Picamera2
from picamera2 import Picamera2, Preview
from .camera_base import CameraBase
import numpy as np
import time


class PiCam2(CameraBase):
    def __init__(self):
        try: 
            self.picam2 = Picamera2()
            self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'BGR888', "size": (640, 480)}))
        except Exception as e:
            print(f"Erreur lors de l'initialisation de PiCam2: {e}")
            raise e
        
    def start_camera(self):
        try:
            self.picam2.start()
        except Exception as e:
            print(f"Erreur lors du démarrage de PiCam2: {e}")
            raise e

    def close(self):
        try: 
            self.picam2.stop()
        except Exception as e:
            print(f"Erreur lors de l'arrêt de PiCam2: {e}")
            raise e

    def capture(self) -> np.ndarray:
        try:
            frame = self.picam2.capture_array()
        except Exception as e:
            print(f"Erreur lors de la capture d'une image avec PiCam2: {e}")
            raise e
        
        return frame