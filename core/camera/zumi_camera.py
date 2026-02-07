#!/usr/bin/env python
# -*- coding: utf-8 -*-
# zumi_camera.py
# ------------------
# Wrapper pour la caméra Zumi qui convertit RGB en BGR pour compatibilité OpenCV

import sys
sys.path.append("/usr/local/lib/python3.5/dist-packages")
from zumi.util.camera import Camera

from .camera_base import CameraBase
import numpy as np
import cv2


class ZumiCamera(CameraBase):
    """
    Wrapper pour la caméra Zumi qui assure la conversion RGB→BGR.

    La bibliothèque Zumi retourne des images en format RGB, mais OpenCV
    s'attend à du BGR. Cette classe effectue la conversion automatiquement.
    """

    def __init__(self):
        """Initialise le wrapper de la caméra Zumi."""
        try:
            self.camera = Camera()
            print("[ZumiCamera] Initialized - will convert RGB to BGR for OpenCV compatibility")
        except Exception as e:
            print("Erreur lors de l'initialisation de ZumiCamera: {}".format(e))
            raise e

    def start_camera(self):
        """Démarre la caméra Zumi."""
        try:
            self.camera.start_camera()
            print("[ZumiCamera] Camera started")
        except Exception as e:
            print("Erreur lors du démarrage de ZumiCamera: {}".format(e))
            raise e

    def close(self):
        """Ferme la caméra Zumi."""
        try:
            self.camera.close()
            print("[ZumiCamera] Camera closed")
        except Exception as e:
            print("Erreur lors de la fermeture de ZumiCamera: {}".format(e))
            raise e

    def capture(self) -> np.ndarray:
        """
        Capture une image et la retourne en format BGR (OpenCV standard).

        IMPORTANT: La caméra Zumi retourne RGB, cette méthode convertit en BGR.

        Returns:
            np.ndarray: Image en format BGR (H, W, 3)
        """
        try:
            # Capture depuis la caméra Zumi (retourne RGB)
            frame_rgb = self.camera.capture()

            if frame_rgb is None:
                print("[ZumiCamera] Warning: captured frame is None")
                return None

            # Vérifier que c'est bien une image couleur 3 canaux
            if len(frame_rgb.shape) == 3 and frame_rgb.shape[2] == 3:
                # Conversion RGB→BGR pour OpenCV
                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                return frame_bgr
            else:
                # Si grayscale ou autre format, retourner tel quel
                print("[ZumiCamera] Warning: unexpected frame shape: {}".format(frame_rgb.shape))
                return frame_rgb

        except Exception as e:
            print("Erreur lors de la capture d'une image avec ZumiCamera: {}".format(e))
            raise e
