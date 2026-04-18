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
        
        # Multi-zones (circuit_fsm)
        center_dash_count:     Nombre de pointillés dans la zone centre (indicateur de confiance).
        front_dash_count:      Nombre de pointillés dans la zone avant (lookahead).
        front_line_detected:   True si la zone avant voit des pointillés.
        front_line_confirmed:  True si la zone avant a >= front_min_dashes pointillés.
        front_offset:          Offset dans la zone avant (pixels).
        corner_left_detected:  True si la zone coin gauche voit des pointillés.
        corner_right_detected: True si la zone coin droit voit des pointillés.
        corner_left_count:     Nombre de pointillés dans la zone coin gauche.
        corner_right_count:    Nombre de pointillés dans la zone coin droit.
        zones_result:          Résultat complet de process_zones() (dict).
    """

    __slots__ = (
        'timestamp', 'frame', 'line_offset', 'line_detected', 'detections',
        'gyro_angles', 'orientation', 'ir_sensors', 'battery_voltage',
        'center_dash_count', 'front_dash_count',
        'front_line_detected', 'front_line_confirmed', 'front_offset',
        'corner_left_detected', 'corner_right_detected',
        'corner_left_count', 'corner_right_count',
        'corner_left_area', 'corner_right_area',
        'zones_result',
    )

    def __init__(
        self,
        timestamp=None,
        frame=None,
        line_offset=None,
        line_detected=False,
        detections=None,
        gyro_angles=None,
        # orientation=-1,
        ir_sensors=None,
        # battery_voltage=0.0,
        center_dash_count=0,
        front_dash_count=0,
        front_line_detected=False,
        front_line_confirmed=False,
        front_offset=None,
        corner_left_detected=False,
        corner_right_detected=False,
        corner_left_count=0,
        corner_right_count=0,
        corner_left_area=0,
        corner_right_area=0,
        zones_result=None,
    ):
        self.timestamp = timestamp if timestamp is not None else time.time()
        self.frame = frame
        self.line_offset = line_offset
        self.line_detected = line_detected
        self.detections = detections
        self.gyro_angles = gyro_angles
        # self.orientation = orientation
        self.ir_sensors = ir_sensors
        # self.battery_voltage = battery_voltage
        self.center_dash_count = center_dash_count
        self.front_dash_count = front_dash_count
        self.front_line_detected = front_line_detected
        self.front_line_confirmed = front_line_confirmed
        self.front_offset = front_offset
        self.corner_left_detected = corner_left_detected
        self.corner_right_detected = corner_right_detected
        self.corner_left_count = corner_left_count
        self.corner_right_count = corner_right_count
        self.corner_left_area = corner_left_area
        self.corner_right_area = corner_right_area
        self.zones_result = zones_result

    def __repr__(self):
        parts = ["SensorState("]
        parts.append("  line={}, offset={}".format(self.line_detected, self.line_offset))
        if self.gyro_angles:
            parts.append("  gyro=[{:.1f}, {:.1f}, {:.1f}]".format(*self.gyro_angles[:3]))
        if self.ir_sensors:
            parts.append("  ir={}".format(self.ir_sensors))
        # if self.battery_voltage is not None:
        #     parts.append("  batt={:.2f}V".format(self.battery_voltage))
        parts.append(")")
        return "\n".join(parts)
