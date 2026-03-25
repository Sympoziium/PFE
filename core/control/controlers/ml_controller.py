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

    # Indices des features pour le calcul des deltas temporels
    # Doit correspondre à DELTA_FEATURE_INDICES dans dataset.py
    # Note: indices 27-28 sont line_position et line_confidence (ajoutees dynamiquement)
    DELTA_FEATURE_INDICES = [1, 3, 6, 7, 18, 27, 28]
    DELTA_STEPS = 3
    DELTA_WEIGHTS = [1.0, 0.5, 0.25]

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

        # Normalisation z-score et masque (chargés depuis normalization_stats.json)
        self._feature_mean = None
        self._feature_std = None
        self._feature_mask = None

        # Buffer circulaire pour calcul des deltas temporels multi-pas
        self._prev_vectors = collections.deque(maxlen=self.DELTA_STEPS)

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

            # Masque de features (indices des features actives a conserver)
            if stats.get('feature_mask') is not None:
                self._feature_mask = np.array(stats['feature_mask'], dtype=np.int64)
                print(f"[MLController] Masque chargé: {len(self._feature_mask)} features actives")
            else:
                print("[MLController] PAS DE MASQUE (toutes les features utilisées)")

            print(f"[MLController] Z-score chargé: {len(self._feature_mean)} features")

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

    def _build_state_vector(self, state) -> np.ndarray:
        """Construit le vecteur d'état à partir du SensorState.

        Pipeline: VisionAdapter (27-dim) → deltas (32-dim) → masque (N-dim) → z-score

        Args:
            state: SensorState contenant les données des capteurs.

        Returns:
            np.ndarray: Vecteur d'état normalisé prêt pour l'inférence.
        """
        vision_result = {"detections": state.detections or []}

        # Construire le dict IMU complet à partir de gyro_angles (11 valeurs)
        # zumi.update_angles() → [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y,
        #                          Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
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

        raw_vector = self.vision_adapter.get_state_vector(vision_result, imu_data, ir_data)

        # Features engineered: line_position et line_confidence
        ir_bot_r = raw_vector[1]  # IR_bottom_right
        ir_bot_l = raw_vector[3]  # IR_bottom_left
        line_pos = (ir_bot_l - ir_bot_r) / (ir_bot_l + ir_bot_r + 1e-6)
        line_conf = abs(ir_bot_l - ir_bot_r) / ((ir_bot_l + ir_bot_r) / 2 + 1e-6)
        raw_vector = np.concatenate([raw_vector, np.array([line_pos, line_conf], dtype=np.float32)])
        # raw_vector est maintenant 29-dim

        # Calculer les deltas temporels multi-pas
        all_deltas = []
        for step, weight in enumerate(self.DELTA_WEIGHTS):
            d = np.zeros(len(self.DELTA_FEATURE_INDICES), dtype=np.float32)
            if step < len(self._prev_vectors):
                prev = self._prev_vectors[-(step + 1)]
                d = (raw_vector[self.DELTA_FEATURE_INDICES] - prev[self.DELTA_FEATURE_INDICES]) * weight
            all_deltas.append(d)
        self._prev_vectors.append(raw_vector.copy())

        # Concaténer: 29-dim + 7*3 deltas = 50-dim
        full_vector = np.concatenate([raw_vector] + all_deltas)

        # Appliquer le masque (retirer les features mortes)
        if self._feature_mask is not None:
            full_vector = full_vector[self._feature_mask]

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
        if self._interpreter is None and self.model_path:
            self._load_model()
            self._load_normalization_stats()

        if self._interpreter:
            print(f"[MLController] Démarré avec modèle: {self.model_path}")
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