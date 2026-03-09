#!/usr/bin/env python
# -*- coding: utf-8 -*-
# sensor_state.py
# ------------------
"""DTO standardisé encapsulant toutes les données capteur à un instant t.

Chaque contrôleur reçoit un SensorState en entrée de sa méthode step().
Cela découple complètement les contrôleurs de la source des données
(VisionPipeline, MPU Zumi, capteurs IR, etc.).
"""

import time
import numpy as np
from typing import Optional, List


class SensorState:
    """État complet des capteurs du robot à un instant donné.

    Attributes:
        timestamp:        Horodatage UNIX de la lecture.
        frame:            Frame brute de la caméra (np.ndarray BGR) ou None.
        line_offset:      Offset de la ligne en pixels (négatif=gauche, positif=droite) ou None.
        line_detected:    True si la ligne est visible dans la frame.
        detections:       Liste de détections passives (Haar, etc.) — liste de dicts.
        gyro_angles:      Angles gyroscope/accéléromètre [x, y, z, acc_x, acc_y, comp_x, comp_y,
                          rot_x, rot_y, rot_z, tilt_state] — 11 valeurs ou None.
        orientation:      État d'orientation Zumi (-1 à 7, 5 = roues au sol).
        ir_sensors:       6 lectures IR [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
                          valeurs 0-255 ou None.
        battery_voltage:  Tension batterie en volts (max 4.2V).
    """

    __slots__ = (
        'timestamp', 'frame', 'line_offset', 'line_detected', 'detections',
        'gyro_angles', 'orientation', 'ir_sensors', 'battery_voltage',
    )

    def __init__(
        self,
        timestamp=None,
        frame=None,
        line_offset=None,
        line_detected=False,
        detections=None,
        gyro_angles=None,
        orientation=-1,
        ir_sensors=None,
        battery_voltage=0.0,
    ):
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.frame = frame
        self.line_offset = line_offset
        self.line_detected = line_detected
        self.detections = detections
        self.gyro_angles = gyro_angles
        self.orientation = orientation
        self.ir_sensors = ir_sensors
        self.battery_voltage = battery_voltage

    # ------------------------------------------------------------------
    #  Conversion en vecteur numérique pour les modèles ML
    # ------------------------------------------------------------------

    def to_vector(self, image_width=320):
        """Convertit l'état en vecteur numpy normalisé pour un modèle ML.

        Le vecteur contient (dans l'ordre) :
          [0]     line_offset normalisé [-1, 1]  (0 si non détectée)
          [1]     line_detected flag              (0.0 ou 1.0)
          [2-4]   gyro x, y, z normalisés /180
          [5-10]  IR capteurs normalisés /255
          [11]    orientation normalisé /7
          [12]    batterie normalisée /4.2

        Returns:
            np.ndarray de shape (13,) et dtype float32.
        """
        vec = np.zeros(13, dtype=np.float32)

        # Ligne
        if self.line_offset is not None:
            half_w = image_width / 2.0
            vec[0] = np.clip(self.line_offset / half_w, -1.0, 1.0)
        vec[1] = 1.0 if self.line_detected else 0.0

        # Gyroscope (3 premiers angles : x, y, z)
        if self.gyro_angles and len(self.gyro_angles) >= 3:
            for i in range(3):
                vec[2 + i] = np.clip(self.gyro_angles[i] / 180.0, -1.0, 1.0)

        # IR capteurs
        if self.ir_sensors and len(self.ir_sensors) >= 6:
            for i in range(6):
                vec[5 + i] = self.ir_sensors[i] / 255.0

        # Orientation
        if self.orientation >= 0:
            vec[11] = self.orientation / 7.0

        # Batterie
        vec[12] = np.clip(self.battery_voltage / 4.2, 0.0, 1.0)

        return vec

    def __repr__(self):
        parts = ["SensorState("]
        parts.append("  line={}, offset={}".format(self.line_detected, self.line_offset))
        if self.gyro_angles:
            parts.append("  gyro=[{:.1f}, {:.1f}, {:.1f}]".format(*self.gyro_angles[:3]))
        if self.ir_sensors:
            parts.append("  ir={}".format(self.ir_sensors))
        parts.append("  batt={:.2f}V".format(self.battery_voltage))
        parts.append(")")
        return "\n".join(parts)
