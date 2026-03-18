#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ml_controller.py
# ------------------
"""Contrôleur propulsé par un modèle de Machine Learning (MLP).

Implémente ControllerBase. Utilise le VisionAdapter pour transformer
le SensorState en vecteur, passe ce vecteur à un modèle d'inférence (TFLite),
et convertit la sortie en MotorCommand.
"""

import numpy as np
from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


class MLController(ControllerBase):
    """Contrôleur basé sur un réseau de neurones MLP.

    Charge un modèle TensorFlow Lite et effectue l'inférence en temps réel
    pour produire les commandes moteur à partir de l'état des capteurs.
    """

    # Vitesse maximale des moteurs (correspond à la normalisation du VisionAdapter)
    MOTOR_SPEED_MAX = 100.0

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

        # Debug info
        self._last_input = None
        self._last_output = None
        self._inference_count = 0

        if self.model_path:
            self._load_model()

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
                Path(__file__).parent.parent.parent.parent / "MLP_model_trainer" / "environment_config.json",
                Path.home() / "robot" / "environment_config.json",  # Pour le Pi
                Path("/home/pi/robot/environment_config.json"),       # Chemin Pi absolu
            ]

            for config_path in config_paths:
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    if "tflite" in config:
                        tflite_cfg = config["tflite"]
                        print(f"[MLController] Configuration TFLite chargée: {config_path}")
                        return {
                            "num_threads": tflite_cfg.get("num_threads_recommended", 4),
                            "allow_fp16": config.get("device_type") == "raspberry_pi"
                        }
        except Exception as e:
            # Silencieux si pas de config - utiliser les valeurs par défaut
            pass

        # Retourner les valeurs par défaut
        return {"num_threads": 4, "allow_fp16": False}

    def _build_state_vector(self, state) -> np.ndarray:
        """Construit le vecteur d'état à partir du SensorState.

        Args:
            state: SensorState contenant les données des capteurs.

        Returns:
            np.ndarray: Vecteur d'état normalisé prêt pour l'inférence.
        """
        # Construire le dict vision_result à partir des détections
        vision_result = {"detections": state.detections or []}

        # Construire le dict IMU à partir de gyro_angles
        # gyro_angles = [x, y, z, acc_x, acc_y, comp_x, comp_y, rot_x, rot_y, rot_z, ...]
        imu_data = {}
        if state.gyro_angles and len(state.gyro_angles) >= 6:
            # Les données d'accélération sont aux indices 3, 4 (acc_x, acc_y)
            # Les rotations aux indices 7, 8, 9 (rot_x, rot_y, rot_z)
            imu_data = {
                "ax": state.gyro_angles[3] if len(state.gyro_angles) > 3 else 0.0,
                "ay": state.gyro_angles[4] if len(state.gyro_angles) > 4 else 0.0,
                "az": 9.81,  # Approximation pour az (gravité)
                "gx": state.gyro_angles[7] if len(state.gyro_angles) > 7 else 0.0,
                "gy": state.gyro_angles[8] if len(state.gyro_angles) > 8 else 0.0,
                "gz": state.gyro_angles[9] if len(state.gyro_angles) > 9 else 0.0,
            }

        # IR sensors
        ir_data = state.ir_sensors if state.ir_sensors else [0] * 6

        # Utiliser le VisionAdapter pour construire le vecteur normalisé
        return self.vision_adapter.get_state_vector(vision_result, imu_data, ir_data)

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