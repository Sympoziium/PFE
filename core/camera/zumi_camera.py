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
import threading


class ZumiCamera(CameraBase):
    """
    Wrapper pour la caméra Zumi qui assure la conversion RGB→BGR.

    La bibliothèque Zumi retourne des images en format RGB, mais OpenCV
    s'attend à du BGR. Cette classe effectue la conversion automatiquement.
    
    La résolution par défaut (160×128) est utilisée pour le flux vidéo en
    direct (Pi Zero V1). Utiliser change_camera_resolution() pour changer de résolution.
    """

    # Résolution par défaut pour le flux vidéo (Pi Zero V1)
    DEFAULT_W = 160
    DEFAULT_H = 128

    def __init__(self, image_w=None, image_h=None):
        """
        Initialise le wrapper de la caméra Zumi.
        
        :param image_w: Largeur par défaut (None = défaut Zumi 160px)
        :param image_h: Hauteur par défaut (None = défaut Zumi 128px)
        """
        self._default_w = image_w or self.DEFAULT_W
        self._default_h = image_h or self.DEFAULT_H
        try:
            self.camera = Camera(image_w=self._default_w, image_h=self._default_h)
            print("[ZumiCamera] Initialized ({}x{}) - RGB to BGR conversion active".format(
                self._default_w, self._default_h))
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
        """Ferme la caméra Zumi (tolérant aux erreurs de generator)."""
        try:
            self.camera.close()
            print("[ZumiCamera] Camera closed")
        except ValueError as e:
            # "generator already executing" — le flux vidéo était en cours de capture.
            # La caméra sera libérée quand le générateur se terminera.
            print("[ZumiCamera] Camera close (generator busy, will release): {}".format(e))
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

    # SUPPRIMÉ: capture_hires() - utiliser change_camera_resolution() à la place
