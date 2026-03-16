#!/usr/bin/env python
# -*- coding: utf-8 -*-
# picam2.py
# ------------------
# Module de gestion de la caméra Raspberry Pi utilisant la bibliothèque Picamera2
from picamera2 import Picamera2, Preview
from .camera_base import CameraBase
import numpy as np
import time
import cv2

try:
    from libcamera import Transform
except Exception:
    Transform = None


class PiCam2(CameraBase):
    def __init__(self, image_w=640, image_h=480, rotate_180=False):
        self._width = image_w
        self._height = image_h
        self._rotate_180 = rotate_180
        try: 
            self.picam2 = Picamera2()
            self.picam2.configure(self._build_configuration())
        except Exception as e:
            print("Erreur lors de l'initialisation de PiCam2: {}".format(e))
            raise e

    def _build_configuration(self):
        kwargs = {
            "main": {"format": "BGR888", "size": (self._width, self._height)},
            "buffer_count": 2,  # minimum stable : libère ~100 MB vs défaut 4 buffers en HD
        }

        # Rotation matérielle 180° quand disponible (plus efficace que post-traitement).
        if self._rotate_180 and Transform is not None:
            kwargs["transform"] = Transform(hflip=True, vflip=True)

        return self.picam2.create_preview_configuration(**kwargs)
        
    def start_camera(self):
        try:
            if hasattr(self.picam2, "started") and self.picam2.started:
                return
            self.picam2.start()
        except Exception as e:
            print("Erreur lors du demarrage de PiCam2: {}".format(e))
            raise e

    def close(self):
        try: 
            if hasattr(self.picam2, "started") and not self.picam2.started:
                return
            self.picam2.stop()
        except Exception as e:
            print("Erreur lors de l'arret de PiCam2: {}".format(e))
            raise e

    def capture(self) -> np.ndarray:
        try:
            frame = self.picam2.capture_array()

            # Fallback logiciel si libcamera.Transform n'est pas disponible.
            if self._rotate_180 and Transform is None:
                frame = cv2.rotate(frame, cv2.ROTATE_180)

            # Vérifier que c'est bien une image couleur 3 canaux
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                # Conversion RGB→BGR pour OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                return frame_bgr
            return frame
        except Exception as e:
            print("Erreur lors de la capture d'une image avec PiCam2: {}".format(e))
            raise e
       

    def reconfigure(self, width: int, height: int):
        """
        Reconfigure PiCam2 à la résolution demandée.
        Ferme et recrée l'instance Picamera2 avec la nouvelle configuration.
        """
        self._width = width
        self._height = height
        try:
            self.picam2.close()
        except Exception as e:
            print("[PiCam2] Avertissement fermeture avant reconfiguration: {}".format(e))
        try:
            self.picam2 = Picamera2()
            self.picam2.configure(self._build_configuration())
            print("[PiCam2] Reconfigurée: {}x{}".format(self._width, self._height))
        except Exception as e:
            print("Erreur lors de la reconfiguration de PiCam2: {}".format(e))
            raise e