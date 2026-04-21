#!/usr/bin/env python
# -*- coding: utf-8 -*-
# sensor_driver.py
# ------------------
"""Driver de lecture et normalisation des capteurs.

Lit les données du VisionPipeline et du robot (MPU, IR, batterie)
et les empaquette dans un SensorState standardisé.

Fonctions Zumi SDK utilisées :
    - zumi.update_angles()       → 11 valeurs [Gyro x,y,z, Acc x,y, Comp x,y, Rot x,y,z, tilt]
    - zumi.get_all_IR_data()     → 6 valeurs IR [0-255]
    - zumi.get_orientation()     → int (-1 à 7)
    - zumi.get_battery_voltage() → float (volts)
"""

import time
from core.control.IO_drivers.sensor_state import SensorState


class SensorDriver:
    """Construit un SensorState à partir des capteurs du robot et du VisionPipeline.

    Args:
        vision_pipeline: Instance de VisionPipeline (caméra + détecteurs).
        robot:           Instance de RobotBase (ex. RobotZumi).
    """

    def __init__(self, vision_pipeline, robot):
        self.vision_pipeline = vision_pipeline
        self.robot = robot
        self._line_detector_index = self._find_line_detector_index()

    def _find_line_detector_index(self):
        """Trouve l'index du détecteur de ligne dans le pipeline."""
        if self.vision_pipeline is None:
            return None
        for i, det in enumerate(self.vision_pipeline.detectors):
            if getattr(det, 'name', '') == 'line':
                return i
        return None

    def read(self, Line_detection = True):
        """Lit tous les capteurs et retourne un SensorState.

        Returns:
            SensorState: État complet des capteurs à cet instant.
        """
        now = time.time()

        # ── Vision ──────────────────────────────────
        frame = None
        line_offset = None
        line_detected = False
        detections = None
        
        # Multi-zones
        center_dash_count = 0
        front_dash_count = 0
        front_line_detected = False
        front_line_confirmed = False
        front_offset = None
        corner_left_detected = False
        corner_right_detected = False
        corner_left_count = 0
        corner_right_count = 0
        corner_left_area = 0
        corner_right_area = 0
        zones_result = None

        if self.vision_pipeline is not None:
            frame = self.vision_pipeline.get_last_frame()

            # Détection de ligne (multi-zones)
            if Line_detection and frame is not None and self._line_detector_index is not None:
                try:
                    # Utiliser process_zones() pour la détection multi-zones
                    line_det = self.vision_pipeline.detectors[self._line_detector_index]
                    zones_result = line_det.process_zones(frame.copy())

                    if zones_result:
                        line_offset = zones_result.get('line_offset')
                        line_detected = line_offset is not None
                        # Dash counts depuis les zones centre et avant
                        center_dash_count = zones_result.get('center', {}).get('count', 0)
                        front_dash_count = zones_result.get('front', {}).get('count', 0)
                        front_line_detected = zones_result.get('front_line_detected', False)
                        front_line_confirmed = zones_result.get('front_line_confirmed', False)
                        front_offset = zones_result.get('front_offset')
                        corner_left_detected = zones_result.get('corner_left_detected', False)
                        corner_right_detected = zones_result.get('corner_right_detected', False)
                        corner_left_count = zones_result.get('corner_left_count', 0)
                        corner_right_count = zones_result.get('corner_right_count', 0)
                        corner_left_area = zones_result.get('corner_left_area', 0)
                        corner_right_area = zones_result.get('corner_right_area', 0)
                except Exception:
                    pass

            # Détections passives (Haar, etc.)
            if hasattr(self.vision_pipeline, 'get_last_detection_result'):
                try:
                    passive_result = self.vision_pipeline.get_last_detection_result()
                    if passive_result and 'detections' in passive_result:
                        detections = passive_result['detections']
                except Exception:
                    pass

        # ── IMU / Gyroscope ─────────────────────────
        gyro_angles = None
        if hasattr(self.robot, 'get_angles'):
            try:
                gyro_angles = self.robot.get_angles()
            except Exception:
                pass

        # ── Capteurs IR ─────────────────────────────
        ir_sensors = None
        if hasattr(self.robot, 'get_ir_data'):
            try:
                ir_sensors = self.robot.get_ir_data()
            except Exception:
                pass

        return SensorState(
            timestamp=now,
            frame=frame,
            line_offset=line_offset,
            line_detected=line_detected,
            detections=detections,
            gyro_angles=gyro_angles,
            ir_sensors=ir_sensors,
            center_dash_count=center_dash_count,
            front_dash_count=front_dash_count,
            front_line_detected=front_line_detected,
            front_line_confirmed=front_line_confirmed,
            front_offset=front_offset,
            corner_left_detected=corner_left_detected,
            corner_right_detected=corner_right_detected,
            corner_left_count=corner_left_count,
            corner_right_count=corner_right_count,
            corner_left_area=corner_left_area,
            corner_right_area=corner_right_area,
            zones_result=zones_result,
        )

