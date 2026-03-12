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

    # ------------------------------------------------------------------ #
    #  Sélection du mode capteur plein-FOV                                #
    # ------------------------------------------------------------------ #
    def _find_full_fov_mode(self):
        """
        Parcourt les modes capteur et retourne le plus petit mode dont le
        crop_limits couvre >= 90 % du capteur (= plein champ de vision).

        Sur IMX219 cela sélectionne le mode 2×2 binned 1640×1232 plutôt que
        le mode crop 1920×1080 qui perd ~40 % du FOV horizontal.

        Retourne None si aucun mode plein-FOV n'est trouvé.
        """
        try:
            modes = self.picam2.sensor_modes
            full_w, full_h = self.picam2.sensor_resolution
        except Exception:
            return None
        if not modes or full_w == 0:
            return None

        full_fov = []
        for m in modes:
            crop = m.get('crop_limits', (0, 0, 0, 0))
            if crop[2] >= full_w * 0.9 and crop[3] >= full_h * 0.9:
                full_fov.append(m)
        if not full_fov:
            return None

        # Trier par nombre de pixels croissant
        full_fov.sort(key=lambda m: m['size'][0] * m['size'][1])

        # Prendre le plus petit mode plein-FOV >= sortie demandée
        for m in full_fov:
            if m['size'][0] >= self._width and m['size'][1] >= self._height:
                return m
        # Sinon le plus grand mode plein-FOV disponible
        return full_fov[-1]

    # ------------------------------------------------------------------ #
    #  Construction de la configuration Picamera2                         #
    # ------------------------------------------------------------------ #
    def _build_configuration(self):
        kwargs = {
            "main": {"format": "BGR888", "size": (self._width, self._height)},
            "buffer_count": 2,  # minimum stable : libère ~100 MB vs défaut 4 buffers en HD
        }

        # Rotation matérielle 180° quand disponible (plus efficace que post-traitement).
        if self._rotate_180 and Transform is not None:
            kwargs["transform"] = Transform(hflip=True, vflip=True)

        # Pour les résolutions HD, forcer un mode capteur plein-FOV afin
        # que l'ISP recadre/redimensionne depuis le plein capteur plutôt que
        # de sélectionner le mode crop 1920×1080 (perte massive de FOV).
        # On passe uniquement 'sensor' (pas de stream raw) → pas de buffer
        # Bayer supplémentaire, donc impact mémoire nul.
        if self._width >= 1280 or self._height >= 720:
            mode = self._find_full_fov_mode()
            if mode is not None:
                kwargs["sensor"] = {
                    "output_size": mode["size"],
                    "bit_depth": mode.get("bit_depth", 10),
                }
                print("[PiCam2] Mode capteur plein-FOV sélectionné: {}".format(mode["size"]))

        # Toujours utiliser preview_configuration : video_configuration
        # sélectionne souvent le mode crop 1080p du capteur.
        return self.picam2.create_preview_configuration(**kwargs)
        
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