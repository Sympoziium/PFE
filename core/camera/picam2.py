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
    def __init__(self, image_w=640, image_h=480):
        self._width = image_w
        self._height = image_h
        try: 
            self.picam2 = Picamera2()
            self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'BGR888', "size": (self._width, self._height)}))
        except Exception as e:
            print("Erreur lors de l'initialisation de PiCam2: {}".format(e))
            raise e
        
    def start_camera(self):
        try:
            self.picam2.start()
        except Exception as e:
            print("Erreur lors du demarrage de PiCam2: {}".format(e))
            raise e

    def close(self):
        try: 
            self.picam2.stop()
        except Exception as e:
            print("Erreur lors de l'arret de PiCam2: {}".format(e))
            raise e

    def capture(self) -> np.ndarray:
        try:
            frame = self.picam2.capture_array()
        except Exception as e:
            print("Erreur lors de la capture d'une image avec PiCam2: {}".format(e))
            raise e
        return frame

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
            self.picam2.configure(self.picam2.create_preview_configuration(main={"format": 'BGR888', "size": (self._width, self._height)}))
            print("[PiCam2] Reconfigurée: {}x{}".format(self._width, self._height))
        except Exception as e:
            print("Erreur lors de la reconfiguration de PiCam2: {}".format(e))
            raise e