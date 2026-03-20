#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vision_adapter.py
# ------------------
"""
Convertit les résultats de détection de la vision et les données capteurs
en un vecteur d'état homogène consommable par le MLController.

Vecteur d'état (22 + N classes):
  [0-5]      : IR sensors (6)             - normalisé / 255
  [6]        : detection flag (1)         - 0 ou 1
  [7..7+N]   : class one-hot (N)          - 0 ou 1
  [7+N..11+N]: bbox cx,cy,w,h (4)        - normalisé [0,1]
  [11+N..22+N]: IMU (11 valeurs)          - normalisé [-1,1]
     11+N: gyro_x   (angle gyroscope X, degrés)
     12+N: gyro_y   (angle gyroscope Y)
     13+N: gyro_z   (angle gyroscope Z)
     14+N: acc_x    (inclinaison accéléromètre X, degrés)
     15+N: acc_y    (inclinaison accéléromètre Y)
     16+N: comp_x   (angle filtré complémentaire X)
     17+N: comp_y   (angle filtré complémentaire Y)
     18+N: rot_x    (rotation accéléromètre X)
     19+N: rot_y    (rotation accéléromètre Y)
     20+N: rot_z    (rotation accéléromètre Z / heading)
     21+N: tilt_state (état d'inclinaison, -1 à 7)

Source des données IMU: zumi.update_angles() retourne 11 valeurs
  [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
"""
from typing import Optional
import numpy as np

# Nombre de valeurs IMU dans le vecteur d'état
IMU_DIM = 11


class VisionAdapter:
    """
    Normalise les sorties du VisionPipeline et les données capteurs
    en un vecteur d'état homogène consommable par le MLController.
    """

    IR_MAX_VALUE    = 255    # Valeur maximale des capteurs IR (8 bits)
    MOTOR_SPEED_MAX = 100.0  # Vitesse maximale théorique (-100 à 100)

    # Normalisation IMU: toutes les valeurs de update_angles() sont des angles en degrés.
    ANGLE_MAX_DEG   = 180.0  # Normalisation des angles: [-180, 180] → [-1, 1]
    TILT_STATE_MAX  = 7.0    # tilt_state va de -1 à 7; on normalise par 7

    def __init__(self, image_width: int, image_height: int, classes: list[str]):
        self.image_width  = image_width
        self.image_height = image_height
        self.classes      = classes

    # --- Getter des dimensions de vecteurs ---
    @property
    def state_dim(self) -> int:
        """Dimension du vecteur d'état (entrée) : 22 + N classes."""
        return 6 + 1 + len(self.classes) + 4 + IMU_DIM  # IR(6)+detect(1)+classes(N)+bbox(4)+IMU(11) = 22+N

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

        # --- Détection (indices 6 à 10+N) ---
        detection = self._get_largest_detection(vision_result)
        if detection:
            state[6] = 1.0
            state[7 : 7 + len(self.classes)] = self._encode_class(detection["object"])
            state[7 + len(self.classes) : 11 + len(self.classes)] = \
                self._normalize_bbox(detection["detection_box"])

        # --- IMU complet (indices 11+N à 21+N) ---
        imu_start = 11 + len(self.classes)
        # Angles gyroscope (3 valeurs)
        state[imu_start]     = imu_data.get("gyro_x", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 1] = imu_data.get("gyro_y", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 2] = imu_data.get("gyro_z", 0.0) / self.ANGLE_MAX_DEG
        # Angles accéléromètre (2 valeurs)
        state[imu_start + 3] = imu_data.get("acc_x", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 4] = imu_data.get("acc_y", 0.0) / self.ANGLE_MAX_DEG
        # Angles filtrés complémentaires (2 valeurs)
        state[imu_start + 5] = imu_data.get("comp_x", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 6] = imu_data.get("comp_y", 0.0) / self.ANGLE_MAX_DEG
        # Angles de rotation (3 valeurs)
        state[imu_start + 7] = imu_data.get("rot_x", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 8] = imu_data.get("rot_y", 0.0) / self.ANGLE_MAX_DEG
        state[imu_start + 9] = imu_data.get("rot_z", 0.0) / self.ANGLE_MAX_DEG
        # État d'inclinaison (1 valeur)
        state[imu_start + 10] = imu_data.get("tilt_state", 0.0) / self.TILT_STATE_MAX

        return np.clip(state, -1.0, 1.0)

    def encode_label(self, left: float, right: float) -> np.ndarray:
        """Normalise les commandes moteur brutes en label [-1, 1]."""
        left_norm = np.clip(left / self.MOTOR_SPEED_MAX, -1.0, 1.0)
        right_norm = np.clip(right / self.MOTOR_SPEED_MAX, -1.0, 1.0)
        return np.array([left_norm, right_norm], dtype=np.float32)

    # --- Méthodes privées ---

    def _get_largest_detection(self, vision_result: dict) -> Optional[dict]:
        detections = vision_result.get("detections", [])
        if not detections:
            return None
        return max(detections, key=lambda d: d["detection_box"][2] * d["detection_box"][3])

    def _encode_class(self, class_name: str) -> np.ndarray:
        vec = np.zeros(len(self.classes), dtype=np.float32)
        if class_name in self.classes:
            vec[self.classes.index(class_name)] = 1.0
        return vec

    def _normalize_bbox(self, bbox: tuple) -> np.ndarray:
        x, y, w, h = bbox
        cx = (x + w / 2.0) / self.image_width
        cy = (y + h / 2.0) / self.image_height
        return np.array([cx, cy, w / self.image_width, h / self.image_height],
                        dtype=np.float32)

    # --- Méthodes de Validation du vecteur ---
    def validate_state_vector(self, vector: np.ndarray) -> bool:
        ir_valid = self.validate_IR(vector)
        imu_valid = self.validate_imu(vector)
        detect_valid = self.validate_detection(vector)
        return ir_valid and imu_valid and detect_valid

    def validate_label_vector(self, label: np.ndarray) -> bool:
        if len(label) != self.label_dim:
            print("[VisionAdapter] Label invalide : taille incorrecte ({} != {})".format(len(label), self.label_dim))
            return False
        if np.any(label < -1.0) or np.any(label > 1.0):
            print("[VisionAdapter] Label hors de la plage normalisée [-1, 1] : {}".format(label))
            return False
        return True

    def debug_print_state(self, state: np.ndarray, label: Optional[np.ndarray] = None):
        """Print le vecteur d'état de manière lisible (dénormalisée)."""
        print("\n=== État courant dénormalisé (Debug) ===")

        # --- IR ---
        ir_values = state[0:6] * self.IR_MAX_VALUE
        print("  [IR] {}".format(ir_values.astype(int)))

        # --- Détection ---
        detection_present = state[6]
        if detection_present > 0.5:
            class_vector = state[7 : 7 + len(self.classes)]
            detected_classes = [self.classes[i] for i in range(len(self.classes)) if class_vector[i] > 0.5]
            bbox_norm = state[7 + len(self.classes) : 11 + len(self.classes)]
            bbox_denorm = bbox_norm.copy()
            bbox_denorm[0] *= self.image_width
            bbox_denorm[1] *= self.image_height
            bbox_denorm[2] *= self.image_width
            bbox_denorm[3] *= self.image_height
            print("  [Vision] Détection: {}, BBox (cx,cy,w,h): {}".format(detected_classes, bbox_denorm.round(1)))
        else:
            print("  [Vision] Aucune détection")

        # --- IMU complet ---
        imu_start = 11 + len(self.classes)
        gyro_vals  = state[imu_start:imu_start+3] * self.ANGLE_MAX_DEG
        acc_vals   = state[imu_start+3:imu_start+5] * self.ANGLE_MAX_DEG
        comp_vals  = state[imu_start+5:imu_start+7] * self.ANGLE_MAX_DEG
        rot_vals   = state[imu_start+7:imu_start+10] * self.ANGLE_MAX_DEG
        tilt_val   = state[imu_start+10] * self.TILT_STATE_MAX
        print("  [IMU] Gyro (deg): {}".format(gyro_vals.round(1)))
        print("  [IMU] Acc  (deg): {}".format(acc_vals.round(1)))
        print("  [IMU] Comp (deg): {}".format(comp_vals.round(1)))
        print("  [IMU] Rot  (deg): {}, Tilt: {:.0f}".format(rot_vals.round(1), tilt_val))

        # --- Label ---
        if label is not None:
            denorm_label = label * self.MOTOR_SPEED_MAX
            print("  [Label] Moteur: Gauche={:.1f}, Droite={:.1f}".format(denorm_label[0], denorm_label[1]))

        print("========================================\n")

    def validate_IR(self, state: np.ndarray) -> bool:
        ir_values_norm = state[0:6]
        if np.any(ir_values_norm < 0.0) or np.any(ir_values_norm > 1.0):
            print("[VisionAdapter] Valeurs IR invalides : {}".format(ir_values_norm))
            return False
        return True

    def validate_imu(self, state: np.ndarray) -> bool:
        imu_start = 11 + len(self.classes)
        imu_values_norm = state[imu_start : imu_start + IMU_DIM]
        if np.any(imu_values_norm < -1.0) or np.any(imu_values_norm > 1.0):
            print("[VisionAdapter] Valeurs IMU invalides : {}".format(imu_values_norm))
            return False
        return True

    def validate_detection(self, state: np.ndarray) -> bool:
        detection_present = state[6]
        if detection_present < 0.0 or detection_present > 1.0:
            print("[VisionAdapter] Flag de détection invalide : {}".format(detection_present))
            return False

        class_vector = state[7 : 7 + len(self.classes)].copy()
        if np.any(class_vector < 0.0) or np.any(class_vector > 1.0):
            print("[VisionAdapter] Valeurs de classe invalides : {}".format(class_vector))
            return False

        if np.sum(class_vector) > 1.0:
            detected_classes = [self.classes[i] for i in range(len(self.classes)) if class_vector[i] > 0.5]
            print("[VisionAdapter] Plusieurs classes détectées simultanément : {}".format(detected_classes))

        bbox_values = state[7 + len(self.classes) : 11 + len(self.classes)]
        if np.any(bbox_values < 0.0) or np.any(bbox_values > 1.0):
            print("[VisionAdapter] Valeurs de boîte invalides : {}".format(bbox_values))
            return False

        return True
