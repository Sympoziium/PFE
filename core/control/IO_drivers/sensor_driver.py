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

        if self.vision_pipeline is not None:
            frame = self.vision_pipeline.get_last_frame()

            # Détection de ligne
            if Line_detection and frame is not None and self._line_detector_index is not None:
                try:
                    result = self.vision_pipeline.process_frame(
                        frame.copy(), self._line_detector_index
                    )
                    if result:
                        line_offset = result.get('line_offset')
                        line_detected = line_offset is not None
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

        # ── Orientation ─────────────────────────────
        # orientation = -1
        # if hasattr(self.robot, 'get_orientation'):
        #     try:
        #         orientation = self.robot.get_orientation()
        #     except Exception:
        #         pass

        # ── Capteurs IR ─────────────────────────────
        ir_sensors = None
        if hasattr(self.robot, 'get_ir_data'):
            try:
                ir_sensors = self.robot.get_ir_data()
            except Exception:
                pass

        # ── Batterie ────────────────────────────────
        # battery_voltage = 0.0
        # if hasattr(self.robot, 'get_battery_voltage'):
        #     try:
        #         battery_voltage = self.robot.get_battery_voltage()
        #     except Exception:
        #         pass

        return SensorState(
            timestamp=now,
            frame=frame,
            line_offset=line_offset,
            line_detected=line_detected,
            detections=detections,
            gyro_angles=gyro_angles,
            # orientation=orientation,
            ir_sensors=ir_sensors,
            # battery_voltage=battery_voltage,
        )
