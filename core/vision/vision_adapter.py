#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vision_adapter.py
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
    MOTOR_SPEED_MAX = 100.0 # Vitesse maximale théorique (-100 à 100)

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
        left_norm = np.clip(left / self.MOTOR_SPEED_MAX, -1.0, 1.0)
        right_norm = np.clip(right / self.MOTOR_SPEED_MAX, -1.0, 1.0)
        return np.array([left_norm, right_norm], dtype=np.float32)

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
    

    # --- Méthodes de Validation du vecteur ---
    def validate_state_vector(self, vector: np.ndarray) -> bool:
        ir_valid = self.validate_IR(vector)
        imu_valid = self.validate_imu(vector)
        detect_valid = self.validate_detection(vector)
        return ir_valid and imu_valid and detect_valid

    def validate_label_vector(self, label: np.ndarray) -> bool:
        """Valide que les labels de commandes moteur sont bien dans la plage normalisée [-1, 1]."""
        if len(label) != self.label_dim:
            print(f"[VisionAdapter] Label invalide : taille incorrecte ({len(label)} != {self.label_dim})")
            return False
            
        if np.any(label < -1.0) or np.any(label > 1.0):
            print(f"[VisionAdapter] Label hors de la plage normalisée [-1, 1] : {label}")
            return False
            
        return True

    def debug_print_state(self, state: np.ndarray, label: Optional[np.ndarray] = None):
        """Print le vecteur d'état de manière lisible (dénormalisée)."""
        print("\n=== État courant dénormalisé (Debug) ===")
        
        # --- IR ---
        ir_values = state[0:6] * self.IR_MAX_VALUE
        print(f"  [IR] {ir_values.astype(int)}")
        
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
            print(f"  [Vision] Détection: {detected_classes}, BBox (cx,cy,w,h): {bbox_denorm.round(1)}")
        else:
            print("  [Vision] Aucune détection")
            
        # --- IMU ---
        imu_start = 11 + len(self.classes)
        accel_values = state[imu_start:imu_start+3] * self.ACCEL_MAX_G * 9.81
        gyro_values = state[imu_start+3:imu_start+6] * self.GYRO_MAX_DPS
        print(f"  [IMU] Accel (m/s²): {accel_values.round(2)}, Gyro (dps): {gyro_values.round(2)}")
        
        # --- Label ---
        if label is not None:
            denorm_label = label * self.MOTOR_SPEED_MAX
            print(f"  [Label] Commandes Moteur (dénormalisées): Gauche={denorm_label[0]:.1f}, Droite={denorm_label[1]:.1f}")
            
        print("========================================\n")

    def validate_IR(self, state: np.ndarray) -> bool:
        ir_values_norm = state[0:6]
        if np.any(ir_values_norm < 0.0) or np.any(ir_values_norm > 1.0):
            print(f"[VisionAdapter] Valeurs IR invalides détectées : {ir_values_norm}")
            return False
        
        ir_values = ir_values_norm * self.IR_MAX_VALUE
        if np.any(ir_values < 0) or np.any(ir_values > self.IR_MAX_VALUE):
            print(f"[VisionAdapter] Valeurs IR hors plage après dénormalisation : {ir_values}")
            return False
        
        return True
    
    def validate_imu(self, state: np.ndarray) -> bool:
        imu_values_norm = state[11 + len(self.classes) : 16 + len(self.classes)]
        if np.any(imu_values_norm < -1.0) or np.any(imu_values_norm > 1.0):
            print(f"[VisionAdapter] Valeurs IMU invalides détectées : {imu_values_norm}")
            return False
        
        # Dénormalisation pour validation physique
        accel_values = imu_values_norm[0:3] * self.ACCEL_MAX_G * 9.81
        gyro_values = imu_values_norm[3:6] * self.GYRO_MAX_DPS # voir si l'indice 6 est pas plus tôt 5 (on a 3 classes de détection visuel)
        
        if np.any(np.abs(accel_values) > self.ACCEL_MAX_G * 9.81):
            print(f"[VisionAdapter] Valeurs d'accélération hors plage : {accel_values}")
            return False
        if np.any(np.abs(gyro_values) > self.GYRO_MAX_DPS):
            print(f"[VisionAdapter] Valeurs de gyroscope hors plage : {gyro_values}")
            return False
        
        return True
    
    def validate_detection(self, state: np.ndarray) -> bool:
        detection_present = state[6]
        if detection_present < 0.0 or detection_present > 1.0:
            print(f"[VisionAdapter] Flag de détection invalide : {detection_present}")
            return False
        
        class_vector = state[7 : 7 + len(self.classes)].copy()
        if np.any(class_vector < 0.0) or np.any(class_vector > 1.0):
            print(f"[VisionAdapter] Valeurs de classe invalides : {class_vector}")
            return False
        
        # nombre de classes détectées simultanément (doit être entre 0 et 3)
        if np.sum(class_vector) > 1.0:

            print(f"[VisionAdapter] Plusieurs classes détectées simultanément : {class_vector}")
            #identifier les classes détectées pour le debug
            detected_classes = [self.classes[i] for i in range(len(self.classes)) if class_vector[i] > 0.5]
            print(f"[VisionAdapter] Classes détectées : {detected_classes}")
            
        
        bbox_values = state[7 + len(self.classes) : 11 + len(self.classes)]
        if np.any(bbox_values < 0.0) or np.any(bbox_values > 1.0):
            print(f"[VisionAdapter] Valeurs de boîte de détection invalides : {bbox_values}")
            return False
        
        bbox_values_denorm = bbox_values.copy() 
        bbox_values_denorm[1] *= self.image_height
        bbox_values_denorm[2] *= self.image_width
        bbox_values_denorm[3] *= self.image_height
        
        return True
        