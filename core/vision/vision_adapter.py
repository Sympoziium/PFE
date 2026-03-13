#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vision_pipeline.py
# ------------------
"""
ce module sert a convertir les résultats de détection de la vision en vecteur
"""
from typing import Optional
import numpy as np

class VisionAdapter:
    """
    Normalise les sorties du VisionPipeline et les données capteurs
    en un vecteur d'état homogène consommable par le MLController.
    """

    # Plages physiques MPU-6050 (configuration Zumi par défaut)
    ACCEL_MAX_G   = 2.0
    GYRO_MAX_DPS  = 250.0
    IR_MAX_VALUE  = 255 # Valeur maximale des capteurs IR (8 bits)

    def __init__(self, image_width: int, image_height: int, classes: list[str]):
        self.image_width  = image_width      # nécessaire pour normaliser les boites de détection
        self.image_height = image_height
        self.classes      = classes          # ordre détermine l'encodage one-hot

    # --- Getter des dimensions de vecteurs ---
    @property
    def state_dim(self) -> int:
        """Dimension du vecteur d'état (entrée) : 17 + N classes."""
        return 17 + len(self.classes)
    
    @property
    def label_dim(self) -> int:
        """Dimension du vecteur cible : 2 (vitesse gauche, droite)."""
        return 2

    def get_state_vector(
        self,
        vision_result: dict,
        imu_data: dict,
        ir_data: list          # [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
    ) -> np.ndarray:

        state = np.zeros(self.state_dim, dtype=np.float32)

        # --- IR sensors (indices 0-5) ---
        if ir_data is not None and len(ir_data) == 6:
            state[0:6] = np.array(ir_data, dtype=np.float32) / self.IR_MAX_VALUE
        # sinon : zeros (valeur par défaut documentée = capteur hors ligne)

        # --- Détection (indices 6 à 10+N) ---
        detection = self._get_largest_detection(vision_result)
        if detection:
            state[6] = 1.0 # flag de détection présente
            state[7 : 7 + len(self.classes)] = self._encode_class(detection["object"]) 
            state[7 + len(self.classes) : 11 + len(self.classes)] = \
                self._normalize_bbox(detection["detection_box"])
        # sinon : zeros par défaut (detection_present=0, one-hot=0, detection_box=0)

        # --- IMU (indices 11+N à 16+N) ---
        imu_start = 11 + len(self.classes)
        state[imu_start]     = imu_data.get("ax", 0.0) / (self.ACCEL_MAX_G * 9.81)
        state[imu_start + 1] = imu_data.get("ay", 0.0) / (self.ACCEL_MAX_G * 9.81)
        state[imu_start + 2] = imu_data.get("az", 0.0) / (self.ACCEL_MAX_G * 9.81)
        state[imu_start + 3] = imu_data.get("gx", 0.0) / self.GYRO_MAX_DPS
        state[imu_start + 4] = imu_data.get("gy", 0.0) / self.GYRO_MAX_DPS
        state[imu_start + 5] = imu_data.get("gz", 0.0) / self.GYRO_MAX_DPS

        return np.clip(state, -1.0, 1.0)

    def encode_label(self, left: float, right: float) -> np.ndarray:
        """Normalise les commandes moteur brutes en label [-1, 1]."""
        # À adapter selon la plage réelle des commandes Zumi
        return np.array([left, right], dtype=np.float32)

    # --- Méthodes privées ---

    def _get_largest_detection(self, vision_result: dict) -> Optional[dict]:
        detections = vision_result.get("detections", [])
        if not detections:
            return None
        # Sélectionne la détection avec la plus grande aire de boîte englobante
        return max(detections, key=lambda d: d["detection_box"][2] * d["detection_box"][3])

    def _encode_class(self, class_name: str) -> np.ndarray:
        vec = np.zeros(len(self.classes), dtype=np.float32)
        if class_name in self.classes:
            vec[self.classes.index(class_name)] = 1.0
        return vec  # vecteur zero si classe inconnue — à logger pour diagnostic

    def _normalize_bbox(self, bbox: tuple) -> np.ndarray:
        x, y, w, h = bbox
        cx = (x + w / 2.0) / self.image_width
        cy = (y + h / 2.0) / self.image_height
        return np.array([cx, cy, w / self.image_width, h / self.image_height],
                        dtype=np.float32)