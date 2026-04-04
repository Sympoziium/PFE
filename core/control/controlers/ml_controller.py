#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ml_controller.py
# ------------------
"""Contrôleur propulsé par un modèle de Machine Learning (MLP).

Implémente ControllerBase. Utilise le VisionAdapter pour transformer
le SensorState en vecteur, passe ce vecteur à un modèle d'inférence (TFLite),
et convertit la sortie en MotorCommand.
"""

import collections
import numpy as np
from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


class MLController(ControllerBase):
    """Contrôleur basé sur un réseau de neurones MLP.

    Charge un modèle TensorFlow Lite et effectue l'inférence en temps réel
    pour produire les commandes moteur à partir de l'état des capteurs.
    """

    # Plage utile des moteurs (correspond au VisionAdapter, plafond ML)
    MOTOR_SPEED_MAX = 50.0

    # Constantes de feature engineering (defauts, ecrasees par normalization_stats.json)
    IR_OFFSET_BOTTOM = -17.0
    GAP_THRESHOLD = 195.0

    # Fenetre glissante (defauts, ecrases par normalization_stats.json)
    WINDOW_SIZE = 20           # Nombre de pas dans la fenetre (1s a 20Hz)
    WINDOW_FEATURE_DIM = 34    # 29 raw + 5 engineered par pas

    def __init__(self, vision_adapter, model_path=None):
        """
        Args:
            vision_adapter (VisionAdapter): Instance de l'adaptateur pour vectoriser l'état.
            model_path (str): Chemin vers le modèle TFLite (.tflite).
        """
        self.vision_adapter = vision_adapter
        self.model_path = model_path

        # Interpreter TFLite
        self._interpreter = None
        self._input_details = None
        self._output_details = None

        # Normalisation z-score (chargees depuis normalization_stats.json)
        self._feature_mean = None
        self._feature_std = None
        self._feature_version = 1  # 1=ancien (2 features), 2=PID-inspired (5 features)

        # Buffer circulaire pour la fenetre glissante
        # Stocke les vecteurs 34-dim (29 raw + 5 engineered) des WINDOW_SIZE derniers pas
        self._window_buffer = collections.deque(maxlen=self.WINDOW_SIZE)
        self._prev_gyro_z = None  # Pour le calcul du gyro_z_rate

        # Debug info
        self._last_input = None
        self._last_output = None
        self._inference_count = 0

        if self.model_path:
            self._load_model()
            self._load_normalization_stats()

    def _load_model(self):
        """Charge le modèle TensorFlow Lite avec configuration optimale."""
        try:
            # Charger la config d'environnement si disponible
            tflite_config = self._load_tflite_config()

            # Essayer d'abord tflite_runtime (plus léger pour Pi)
            try:
                import tflite_runtime.interpreter as tflite
                self._interpreter = tflite.Interpreter(
                    model_path=self.model_path,
                    num_threads=tflite_config.get("num_threads", 4)
                )
            except ImportError:
                # Fallback sur tensorflow complet
                import tensorflow as tf
                self._interpreter = tf.lite.Interpreter(
                    model_path=self.model_path
                )
                # Appliquer num_threads pour TensorFlow
                try:
                    self._interpreter._load_delegate(None)
                except Exception:
                    pass

            self._interpreter.allocate_tensors()
            self._input_details = self._interpreter.get_input_details()
            self._output_details = self._interpreter.get_output_details()

            input_shape = self._input_details[0]['shape']
            output_shape = self._output_details[0]['shape']

            print(f"[MLController] Modèle chargé: {self.model_path}")
            print(f"[MLController] Input shape: {input_shape}, Output shape: {output_shape}")
            print(f"[MLController] TFLite config: threads={tflite_config.get('num_threads', 4)}")

        except Exception as e:
            print(f"[MLController] Erreur de chargement du modèle: {e}")
            self._interpreter = None

    def _load_tflite_config(self) -> dict:
        """Charge la configuration TFLite depuis le fichier de config d'environnement."""
        try:
            from pathlib import Path
            import json

            # Chercher le fichier config dans le répertoire MLP_model_trainer
            config_paths = [
                Path.home() / "PFE" / "core" / "control" / "controlers" / "models" / "environment_config.json",  # Pour le Pi
                Path("/home/pi/PFE/core/control/controlers/models/environment_config.json"),       # Chemin Pi absolu
            ]

            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    if "tflite" in config:
                        tflite_cfg = config["tflite"]
                        print(f"[MLController] Configuration TFLite chargée: {config_path}")
                        return {
                            "num_threads": tflite_cfg.get("num_threads_recommended", 3),
                            "allow_fp16": config.get("device_type") == "raspberry_pi"
                        }
                else:
                    print(f"[MLController] Config TFLite non trouvée à: {config_path}")
        except Exception as e:
            print(f"[MLController] Aucune config présente : {e}")
            pass

        # Retourner les valeurs par défaut
        return {"num_threads": 3, "allow_fp16": True}

    def _load_normalization_stats(self):
        """Charge les stats de normalisation z-score depuis normalization_stats.json.

        Cherche le fichier dans le même répertoire que le modèle .tflite.
        Si absent, l'inférence fonctionne sans normalisation (rétrocompatible).
        """
        try:
            from pathlib import Path
            import json

            model_dir = Path(self.model_path).parent
            stats_path = model_dir / "normalization_stats.json"

            if not stats_path.exists():
                print("[MLController] Pas de normalization_stats.json (ancien modèle, pas de z-score)")
                return

            with open(stats_path, 'r') as f:
                stats = json.load(f)

            self._feature_mean = np.array(stats['feature_mean'], dtype=np.float32)
            self._feature_std = np.array(stats['feature_std'], dtype=np.float32)
            # Protéger contre division par zéro (features mortes)
            self._feature_std[self._feature_std < 1e-6] = 1.0

            # Charger les constantes de feature engineering
            self._feature_version = stats.get('feature_version', 1)
            if self._feature_version >= 2:
                self.IR_OFFSET_BOTTOM = stats.get('ir_offset_bottom', -17.0)
                self.GAP_THRESHOLD = stats.get('gap_threshold', 195.0)
                print(f"[MLController] Feature v2: ir_offset={self.IR_OFFSET_BOTTOM:.1f}, "
                      f"gap={self.GAP_THRESHOLD}")

            # Charger les parametres de la fenetre glissante
            self.WINDOW_SIZE = stats.get('window_size', 20)
            self.WINDOW_FEATURE_DIM = stats.get('window_feature_dim', 34)
            # Reinitialiser le buffer avec la bonne taille
            self._window_buffer = collections.deque(maxlen=self.WINDOW_SIZE)

            print(f"[MLController] Z-score chargé: {len(self._feature_mean)} features "
                  f"(version={self._feature_version}, "
                  f"fenetre={self.WINDOW_SIZE}x{self.WINDOW_FEATURE_DIM})")

        except Exception as e:
            print(f"[MLController] Erreur chargement normalization_stats: {e}")
            self._feature_mean = None
            self._feature_std = None
            self._feature_mask = None

    def _apply_zscore(self, vector: np.ndarray) -> np.ndarray:
        """Applique la normalisation z-score au vecteur d'état.

        Args:
            vector: Vecteur brut du VisionAdapter

        Returns:
            Vecteur normalisé (même shape)
        """
        if self._feature_mean is None or self._feature_std is None:
            return vector
        return (vector - self._feature_mean) / self._feature_std

    def _build_step_vector(self, state) -> np.ndarray:
        """Construit le vecteur d'etat 34-dim pour un seul pas temporel.

        Pipeline: VisionAdapter (29-dim) -> engineered features (34-dim)

        Args:
            state: SensorState contenant les donnees des capteurs.

        Returns:
            np.ndarray: Vecteur 34-dim (29 raw + 5 engineered).
        """
        vision_result = {"detections": state.detections or []}

        imu_data = {}
        if state.gyro_angles and len(state.gyro_angles) >= 11:
            a = state.gyro_angles
            imu_data = {
                "gyro_x": float(a[0]),
                "gyro_y": float(a[1]),
                "gyro_z": float(a[2]),
                "acc_x":  float(a[3]),
                "acc_y":  float(a[4]),
                "comp_x": float(a[5]),
                "comp_y": float(a[6]),
                "rot_x":  float(a[7]),
                "rot_y":  float(a[8]),
                "rot_z":  float(a[9]),
                "tilt_state": float(a[10]),
            }

        ir_data = state.ir_sensors if state.ir_sensors else [0] * 6
        line_off = state.line_offset if hasattr(state, 'line_offset') else None
        raw_vector = self.vision_adapter.get_state_vector(vision_result, imu_data, ir_data, line_offset=line_off)

        # Features engineered PID-inspired (5 features)
        ir_bot_r = raw_vector[1]   # IR_bottom_right
        ir_bot_l = raw_vector[3]   # IR_bottom_left
        ir_sum = (ir_bot_l + ir_bot_r) / 2.0
        gyro_z = raw_vector[18]    # gyro_z cumulatif

        calibrated_error = (ir_bot_r - ir_bot_l) - (-self.IR_OFFSET_BOTTOM)
        line_visible = 1.0 if ir_sum < self.GAP_THRESHOLD else 0.0
        cal_error_norm = calibrated_error / (ir_sum + 1e-6)

        # gyro_z_rate (delta gyro_z cumulatif)
        gyro_z_rate = 0.0
        if self._prev_gyro_z is not None:
            rate = gyro_z - self._prev_gyro_z
            if abs(rate) < 150.0:  # pas une frontiere de sequence
                gyro_z_rate = rate
        self._prev_gyro_z = gyro_z

        heading_drift = gyro_z_rate * (1.0 - line_visible)

        engineered = np.array([
            calibrated_error, line_visible, cal_error_norm,
            gyro_z_rate, heading_drift
        ], dtype=np.float32)

        return np.concatenate([raw_vector, engineered])

    def _build_state_vector(self, state) -> np.ndarray:
        """Construit le vecteur d'etat complet via fenetre glissante.

        Pipeline: step vector (34-dim) -> window buffer -> concatenation
                  (34 x 20 = 680-dim) -> z-score

        Args:
            state: SensorState contenant les donnees des capteurs.

        Returns:
            np.ndarray: Vecteur 680-dim normalise pret pour l'inference.
        """
        # 1. Construire le vecteur du pas actuel (34-dim)
        step_vector = self._build_step_vector(state)

        # 2. Ajouter au buffer de fenetre
        self._window_buffer.append(step_vector)

        # 3. Construire la fenetre complete (oldest first, newest last)
        #    Si le buffer n'est pas encore plein, zero-padder a gauche
        window_size = self.WINDOW_SIZE
        feature_dim = len(step_vector)
        full_vector = np.zeros(window_size * feature_dim, dtype=np.float32)

        n_available = len(self._window_buffer)
        offset = window_size - n_available  # nombre de pas zero-paddes

        for i, vec in enumerate(self._window_buffer):
            start = (offset + i) * feature_dim
            end = start + feature_dim
            full_vector[start:end] = vec

        # 4. Appliquer la normalisation z-score
        return self._apply_zscore(full_vector)

    def _inference(self, input_vector: np.ndarray) -> np.ndarray:
        """Effectue l'inférence avec le modèle TFLite.

        Args:
            input_vector: Vecteur d'état normalisé (shape: [state_dim])

        Returns:
            np.ndarray: Commandes moteur normalisées [left, right] dans [-1, 1]
        """
        # Reshape pour batch de 1
        input_data = input_vector.reshape(1, -1).astype(np.float32)

        # Set input tensor
        self._interpreter.set_tensor(self._input_details[0]['index'], input_data)

        # Run inference
        self._interpreter.invoke()

        # Get output
        output = self._interpreter.get_tensor(self._output_details[0]['index'])

        return output[0]  # Retirer la dimension batch

    @property
    def name(self):
        return "ml_controller"

    def step(self, state):
        """Calcule la commande moteur via le modèle MLP.

        Args:
            state (SensorState): État courant des capteurs.

        Returns:
            MotorCommand: Commande moteur calculée.
        """
        # 1. Vectoriser l'état
        input_vector = self._build_state_vector(state)
        self._last_input = input_vector

        # 2. Inférence dans le modèle
        if self._interpreter is not None:
            try:
                output = self._inference(input_vector)
                self._last_output = output
                self._inference_count += 1

                # Diagnostic aux premiers ticks
                if self._inference_count <= 3:
                    print(f"[MLController] Tick {self._inference_count}: "
                          f"input_shape={input_vector.shape}, "
                          f"input_range=[{input_vector.min():.2f}, {input_vector.max():.2f}], "
                          f"output=[{output[0]:.4f}, {output[1]:.4f}]")
                    if state.ir_sensors:
                        ir = state.ir_sensors
                        print(f"  IR raw: fr={ir[0]}, br={ir[1]}, bkr={ir[2]}, "
                              f"bl={ir[3]}, bkl={ir[4]}, fl={ir[5]}")

                # Dénormaliser: [-1, 1] -> [-MOTOR_SPEED_MAX, MOTOR_SPEED_MAX]
                left_speed = float(output[0]) * self.MOTOR_SPEED_MAX
                right_speed = float(output[1]) * self.MOTOR_SPEED_MAX

            except Exception as e:
                print(f"[MLController] Erreur d'inférence: {e}")
                left_speed, right_speed = 0, 0
        else:
            # Fallback: arrêt si pas de modèle
            left_speed, right_speed = 0, 0

        # 3. Retourner la commande
        return MotorCommand.make_speed(left_speed, right_speed)

    def start(self):
        """Démarre le contrôleur ML."""
        self._inference_count = 0
        self._window_buffer.clear()  # Reset la fenetre glissante
        self._prev_gyro_z = None
        if self._interpreter is None and self.model_path:
            self._load_model()
            self._load_normalization_stats()

        if self._interpreter:
            expected_dim = self._input_details[0]['shape'][1]
            print(f"[MLController] Demarré: {self.model_path}")
            print(f"[MLController] TFLite input: {expected_dim}-dim, "
                  f"feature_version={self._feature_version}, "
                  f"fenetre={self.WINDOW_SIZE}x{self.WINDOW_FEATURE_DIM}, "
                  f"ir_offset={self.IR_OFFSET_BOTTOM:.1f}")
        else:
            print("[MLController] Démarré SANS modèle (commandes = 0)")

    def stop(self):
        """Arrête le contrôleur ML."""
        print(f"[MLController] Arrêté. Inférences effectuées: {self._inference_count}")

    def get_debug_info(self) -> dict:
        """Retourne les informations de debug pour l'interface."""
        return {
            "model_loaded": self._interpreter is not None,
            "model_path": self.model_path,
            "zscore_loaded": self._feature_mean is not None,
            "inference_count": self._inference_count,
            "last_input_shape": self._last_input.shape if self._last_input is not None else None,
            "last_output": self._last_output.tolist() if self._last_output is not None else None,
        }

    def get_params(self) -> dict:
        """Retourne les paramètres du contrôleur."""
        return {
            "motor_speed_max": self.MOTOR_SPEED_MAX,
            "state_dim": self.vision_adapter.state_dim,
        }