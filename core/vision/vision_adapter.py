#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vision_adapter.py
# ------------------
"""
Convertit les résultats de détection de la vision et les données capteurs
en un vecteur d'état homogène consommable par le MLController.

Le VisionAdapter effectue uniquement la vectorisation structurelle (assemblage,
encodage one-hot, bbox relative). Les valeurs numériques (IR, IMU) sont stockées
en valeurs brutes (raw). La normalisation statistique (z-score) est appliquée
séparément au moment de l'entraînement et de l'inférence.

Vecteur d'état (38 + N classes):
  [0-5]      : IR sensors (6)             - valeurs brutes 0-255 (8 bits)
  [6]        : IR_diff (1)               - (bottom_left - bottom_right), raw
  [7]        : IR_sum  (1)               - (bottom_left + bottom_right)/2, raw
  [8]        : detection flag (1)         - 0 ou 1
  [9..9+N]   : class one-hot (N)          - 0 ou 1
  [9+N..13+N]: bbox cx,cy,w,h (4)        - normalisé [0,1] (relatif à l'image)
  [13+N..24+N]: IMU (11 valeurs)          - valeurs brutes (degrés)
     13+N: gyro_x   (angle gyroscope X, degrés)
     14+N: gyro_y   (angle gyroscope Y)
     15+N: gyro_z   (angle gyroscope Z)
     16+N: acc_x    (inclinaison accéléromètre X, degrés)
     17+N: acc_y    (inclinaison accéléromètre Y)
     18+N: comp_x   (angle filtré complémentaire X)
     19+N: comp_y   (angle filtré complémentaire Y)
     20+N: rot_x    (rotation accéléromètre X)
     21+N: rot_y    (rotation accéléromètre Y)
     22+N: rot_z    (rotation accéléromètre Z / heading)
     23+N: tilt_state (état d'inclinaison, -1 à 7)
  [24+N..32+N]: Zone features (9)         - détection multi-zones caméra
     24+N: front_line_detected            - 0 ou 1
     25+N: front_line_confirmed           - 0 ou 1
     26+N: front_offset_norm              - [-1, 1]
     27+N: front_dash_count_norm          - [0, 1] (count / MAX_DASH_COUNT)
     28+N: corner_left_detected           - 0 ou 1
     29+N: corner_right_detected          - 0 ou 1
     30+N: corner_left_area_norm          - [0, 1]
     31+N: corner_right_area_norm         - [0, 1]
     32+N: center_dash_count_norm         - [0, 1] (count / MAX_DASH_COUNT)
  [33+N]     : line_camera_offset (1)    - position de la ligne blanche [-1, 1]
  [34+N]     : line_camera_detected (1)  - 0 ou 1 (ligne visible par caméra)

  IR_diff et IR_sum sont des features engineered à partir des capteurs IR bottom:
    ir_data = [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
    IR_diff = bottom_left(idx 3) - bottom_right(idx 1)  → position latérale de la ligne
    IR_sum  = (bottom_left + bottom_right) / 2           → confiance (sur la ligne ou pas)

  Seules les bbox sont normalisées par les dimensions image (transform structurel,
  résolution-indépendant). Le z-score appliqué en aval gère toute la normalisation
  statistique.

  Note: les anciennes données (29-dim, sans zone features) et intermédiaires
  (36-dim, sans dash counts) sont zero-paddées vers 38-dim par
  dataset.py:pad_to_new_format() lors de l'entraînement.

Source des données IMU: zumi.update_angles() retourne 11 valeurs
  [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
"""
from typing import Optional
import numpy as np

# Nombre de valeurs IMU dans le vecteur d'état
IMU_DIM = 11


class VisionAdapter:
    """
    Vectorise les sorties du VisionPipeline et les données capteurs
    en un vecteur d'état homogène consommable par le MLController.

    Effectue uniquement les transformations structurelles (assemblage, encodage,
    bbox relative). Les valeurs IR et IMU sont conservées brutes (raw).
    La normalisation statistique (z-score) est appliquée séparément.
    """

    MOTOR_SPEED_MAX = 50.0  # Plage utile des moteurs (-50 à 50), plafond ML

    def __init__(self, image_width: int, image_height: int, classes: list[str]):
        self.image_width  = image_width
        self.image_height = image_height
        self.classes      = classes

    # Aire maximale d'une zone coin pour normalisation (25% x 25% de l'image)
    CORNER_ZONE_RATIO = 0.25 * 0.25  # fraction de l'aire totale de l'image

    # Nombre maximal de dashes attendus dans une zone (pour normalisation [0,1])
    MAX_DASH_COUNT = 10.0

    # Nombre de features de zone ajoutees au vecteur d'etat
    ZONE_FEATURES_DIM = 9

    # --- Getter des dimensions de vecteurs ---
    @property
    def state_dim(self) -> int:
        """Dimension du vecteur d'état (entrée) : 38 + N classes."""
        return 6 + 2 + 1 + len(self.classes) + 4 + IMU_DIM + self.ZONE_FEATURES_DIM + 2

    @property
    def label_dim(self) -> int:
        """Dimension du vecteur cible : 2 (vitesse gauche, droite)."""
        return 2

    def get_state_vector(
        self,
        vision_result: dict,
        imu_data: dict,
        ir_data: list,         # [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
        line_offset: float = None,  # Position de la ligne blanche en pixels (caméra)
        front_line_detected: bool = False,
        front_line_confirmed: bool = False,
        front_offset: float = None,
        front_dash_count: int = 0,
        corner_left_detected: bool = False,
        corner_right_detected: bool = False,
        corner_left_area: float = 0,
        corner_right_area: float = 0,
        center_dash_count: int = 0,
    ) -> np.ndarray:

        state = np.zeros(self.state_dim, dtype=np.float32)

        # --- IR sensors (indices 0-5) — valeurs brutes 0-255 ---
        if ir_data is not None and len(ir_data) == 6:
            ir_raw = np.array(ir_data, dtype=np.float32)
            state[0:6] = ir_raw
            # IR engineered features (indices 6-7) — calculées depuis les valeurs brutes
            # ir_data = [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
            state[6] = ir_raw[3] - ir_raw[1]        # IR_diff: position laterale de la ligne
            state[7] = (ir_raw[3] + ir_raw[1]) / 2.0  # IR_sum: confiance (sur la ligne)

        # --- Détection (indices 8 à 12+N) — encodage structurel ---
        detection = self._get_largest_detection(vision_result)
        if detection:
            state[8] = 1.0
            state[9 : 9 + len(self.classes)] = self._encode_class(detection["object"])
            state[9 + len(self.classes) : 13 + len(self.classes)] = \
                self._normalize_bbox(detection["detection_box"])

        # --- IMU complet (indices 13+N à 23+N) — valeurs brutes en degrés ---
        imu_start = 13 + len(self.classes)
        # Angles gyroscope (3 valeurs, degrés)
        state[imu_start]     = imu_data.get("gyro_x", 0.0)
        state[imu_start + 1] = imu_data.get("gyro_y", 0.0)
        state[imu_start + 2] = imu_data.get("gyro_z", 0.0)
        # Angles accéléromètre (2 valeurs, degrés)
        state[imu_start + 3] = imu_data.get("acc_x", 0.0)
        state[imu_start + 4] = imu_data.get("acc_y", 0.0)
        # Angles filtrés complémentaires (2 valeurs, degrés)
        state[imu_start + 5] = imu_data.get("comp_x", 0.0)
        state[imu_start + 6] = imu_data.get("comp_y", 0.0)
        # Angles de rotation (3 valeurs, degrés)
        state[imu_start + 7] = imu_data.get("rot_x", 0.0)
        state[imu_start + 8] = imu_data.get("rot_y", 0.0)
        state[imu_start + 9] = imu_data.get("rot_z", 0.0)
        # État d'inclinaison (1 valeur, -1 à 7)
        state[imu_start + 10] = imu_data.get("tilt_state", 0.0)

        # --- Zone features (indices 24+N à 32+N) — détection multi-zones caméra ---
        zone_start = imu_start + IMU_DIM
        max_corner_area = self.image_width * self.image_height * self.CORNER_ZONE_RATIO
        state[zone_start]     = 1.0 if front_line_detected else 0.0
        state[zone_start + 1] = 1.0 if front_line_confirmed else 0.0
        state[zone_start + 2] = np.clip(
            float(front_offset or 0) / (self.image_width / 2.0), -1.0, 1.0
        ) if front_offset is not None else 0.0
        state[zone_start + 3] = min(float(front_dash_count) / self.MAX_DASH_COUNT, 1.0)
        state[zone_start + 4] = 1.0 if corner_left_detected else 0.0
        state[zone_start + 5] = 1.0 if corner_right_detected else 0.0
        state[zone_start + 6] = min(float(corner_left_area) / max_corner_area, 1.0)
        state[zone_start + 7] = min(float(corner_right_area) / max_corner_area, 1.0)
        state[zone_start + 8] = min(float(center_dash_count) / self.MAX_DASH_COUNT, 1.0)

        # --- Détection de ligne par caméra (indices 33+N, 34+N) ---
        # IMPORTANT: toujours les 2 derniers indices du vecteur.
        # dataset.py utilise raw_dim - 2 pour acceder a line_camera_offset.
        line_start = zone_start + self.ZONE_FEATURES_DIM
        if line_offset is not None:
            # Normaliser en [-1, 1] relatif à la demi-largeur de l'image
            state[line_start] = np.clip(line_offset / (self.image_width / 2.0), -1.0, 1.0)
            state[line_start + 1] = 1.0  # ligne détectée
        # Sinon : 0.0 par défaut (pas de ligne visible)

        return state

    def encode_label(self, left: float, right: float) -> np.ndarray:
        """Normalise les commandes moteur brutes en label [-1, 1].

        Divise par MOTOR_SPEED_MAX (50). Les vitesses au-dela de 50 sont clippees.
        """
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
        """Print le vecteur d'état de manière lisible (valeurs brutes)."""
        print("\n=== État courant (Debug) ===")

        # --- IR (valeurs brutes 0-255) ---
        ir_values = state[0:6]
        print("  [IR] {}".format(ir_values.astype(int)))
        print("  [IR eng] diff={:.1f}, sum={:.1f}".format(state[6], state[7]))

        # --- Détection ---
        detection_present = state[8]
        if detection_present > 0.5:
            class_vector = state[9 : 9 + len(self.classes)]
            detected_classes = [self.classes[i] for i in range(len(self.classes)) if class_vector[i] > 0.5]
            bbox_norm = state[9 + len(self.classes) : 13 + len(self.classes)]
            bbox_denorm = bbox_norm.copy()
            bbox_denorm[0] *= self.image_width
            bbox_denorm[1] *= self.image_height
            bbox_denorm[2] *= self.image_width
            bbox_denorm[3] *= self.image_height
            print("  [Vision] Détection: {}, BBox (cx,cy,w,h): {}".format(detected_classes, bbox_denorm.round(1)))
        else:
            print("  [Vision] Aucune détection")

        # --- IMU complet (valeurs brutes en degrés) ---
        imu_start = 13 + len(self.classes)
        gyro_vals  = state[imu_start:imu_start+3]
        acc_vals   = state[imu_start+3:imu_start+5]
        comp_vals  = state[imu_start+5:imu_start+7]
        rot_vals   = state[imu_start+7:imu_start+10]
        tilt_val   = state[imu_start+10]
        print("  [IMU] Gyro (deg): {}".format(np.round(gyro_vals, 1)))
        print("  [IMU] Acc  (deg): {}".format(np.round(acc_vals, 1)))
        print("  [IMU] Comp (deg): {}".format(np.round(comp_vals, 1)))
        print("  [IMU] Rot  (deg): {}, Tilt: {:.0f}".format(np.round(rot_vals, 1), tilt_val))

        # --- Zone features (9 features) ---
        zone_start = imu_start + IMU_DIM
        print("  [Zones] front_det={:.0f}, front_conf={:.0f}, front_off={:.2f}, front_dash={:.2f}".format(
            state[zone_start], state[zone_start + 1], state[zone_start + 2], state[zone_start + 3]))
        print("  [Zones] corner_L={:.0f} (area={:.3f}), corner_R={:.0f} (area={:.3f})".format(
            state[zone_start + 4], state[zone_start + 6],
            state[zone_start + 5], state[zone_start + 7]))
        print("  [Zones] center_dash={:.2f}".format(state[zone_start + 8]))

        # --- Camera line ---
        line_start = zone_start + self.ZONE_FEATURES_DIM
        print("  [Camera] offset={:.3f}, detected={:.0f}".format(
            state[line_start], state[line_start + 1]))

        # --- Label ---
        if label is not None:
            denorm_label = label * self.MOTOR_SPEED_MAX
            print("  [Label] Moteur: Gauche={:.1f}, Droite={:.1f}".format(denorm_label[0], denorm_label[1]))

        print("========================================\n")

    def validate_IR(self, state: np.ndarray) -> bool:
        ir_values = state[0:6]
        if np.any(ir_values < 0.0) or np.any(ir_values > 255.0):
            print("[VisionAdapter] Valeurs IR invalides (attendu 0-255) : {}".format(ir_values))
            return False
        return True

    def validate_imu(self, state: np.ndarray) -> bool:
        imu_start = 13 + len(self.classes)
        imu_values = state[imu_start : imu_start + IMU_DIM]
        # Indices non-cumulatifs: acc_x(3), acc_y(4), comp_x(5), comp_y(6)
        # Les angles cumulatifs (gyro_x/y/z, rot_x/y/z) peuvent depasser 360 deg
        non_cumulative = [3, 4, 5, 6]
        if np.any(np.abs(imu_values[non_cumulative]) > 360.0):
            print("[VisionAdapter] Valeurs IMU hors plage (>360 deg) : {}".format(
                imu_values[non_cumulative]))
            return False
        # tilt_state: -1 à 7
        if imu_values[10] < -2.0 or imu_values[10] > 8.0:
            print("[VisionAdapter] Tilt state invalide : {}".format(imu_values[10]))
            return False
        return True

    def validate_detection(self, state: np.ndarray) -> bool:
        detection_present = state[8]
        if detection_present < 0.0 or detection_present > 1.0:
            print("[VisionAdapter] Flag de détection invalide : {}".format(detection_present))
            return False

        class_vector = state[9 : 9 + len(self.classes)].copy()
        if np.any(class_vector < 0.0) or np.any(class_vector > 1.0):
            print("[VisionAdapter] Valeurs de classe invalides : {}".format(class_vector))
            return False

        if np.sum(class_vector) > 1.0:
            detected_classes = [self.classes[i] for i in range(len(self.classes)) if class_vector[i] > 0.5]
            print("[VisionAdapter] Plusieurs classes détectées simultanément : {}".format(detected_classes))

        bbox_values = state[9 + len(self.classes) : 13 + len(self.classes)]
        if np.any(bbox_values < 0.0) or np.any(bbox_values > 1.0):
            print("[VisionAdapter] Valeurs de boîte invalides : {}".format(bbox_values))
            return False

        return True
