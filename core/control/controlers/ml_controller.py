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
    IR_OFFSET_BOTTOM = 8.8       # Mesuré via Sensor Profiler (zumi_1, 2026-03-28)
    GAP_THRESHOLD = 210.8        # Seuil IR pour ligne visible (idem)

    # Fenetre glissante (defauts, ecrases par normalization_stats.json)
    WINDOW_SIZE = 25           # Nombre de pas dans la fenetre (1.25s a 20Hz)
    WINDOW_FEATURE_DIM = 41    # 30 raw + 11 engineered par pas (detection exclue)
    TEMPORAL_DECAY = 0.85      # Decay exponentiel (1.0 = pas de decay)
    INTEGRAL_WINDOW = 5        # Fenetre pour ir_error_integral

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
        # Buffer circulaire pour la fenetre glissante
        self._window_buffer = collections.deque(maxlen=self.WINDOW_SIZE)
        self._prev_gyro_z = None  # Pour le calcul du gyro_z_rate
        self._prev_calibrated_error = None  # Pour ir_error_derivative
        self._prev_gyro_z_rate = None  # Pour gyro_z_accel

        # DSP features
        self._prev_ir_sum = None         # Pour ir_sum_accel (1ere derivee)
        self._prev_ir_sum_delta = None   # Pour ir_sum_accel (2eme derivee)
        self._line_lost_counter = 0      # Pour line_lost_duration

        # Debug logging (activé via UI ou set_debug())
        self._debug_enabled = False
        self._debug_log = []
        self._debug_interval = 1  # log every tick (changer a 5-10 si le log est trop gros)
        self._prev_output = None
        self._last_step_debug = {}

        # Exclusion des features Detection (indices 8-15 dans le vecteur brut 38-dim)
        self._exclude_detection = False
        self._detection_indices = list(range(8, 16))
        self._decay_weights = None  # Precalcule apres chargement des stats

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
            self.IR_OFFSET_BOTTOM = stats.get('ir_offset_bottom', self.IR_OFFSET_BOTTOM)
            self.GAP_THRESHOLD = stats.get('gap_threshold', self.GAP_THRESHOLD)

            # Charger les parametres de la fenetre glissante
            self.WINDOW_SIZE = stats.get('window_size', self.WINDOW_SIZE)
            self.WINDOW_FEATURE_DIM = stats.get('window_feature_dim', self.WINDOW_FEATURE_DIM)
            self.TEMPORAL_DECAY = stats.get('temporal_decay', self.TEMPORAL_DECAY)
            # Reinitialiser le buffer avec la bonne taille
            self._window_buffer = collections.deque(maxlen=self.WINDOW_SIZE)

            # Charger les parametres d'exclusion Detection
            self._exclude_detection = stats.get('exclude_detection', False)
            self._detection_indices = stats.get('detection_indices', list(range(8, 16)))

            # Precalculer les poids de decay temporel
            if self.TEMPORAL_DECAY < 1.0:
                self._decay_weights = np.array([
                    self.TEMPORAL_DECAY ** (self.WINDOW_SIZE - 1 - w)
                    for w in range(self.WINDOW_SIZE)
                ], dtype=np.float32)
            else:
                self._decay_weights = None

            print(f"[MLController] Z-score chargé: {len(self._feature_mean)} features "
                  f"(fenetre={self.WINDOW_SIZE}x{self.WINDOW_FEATURE_DIM}, "
                  f"decay={self.TEMPORAL_DECAY}, "
                  f"ir_offset={self.IR_OFFSET_BOTTOM:.1f}, "
                  f"exclude_det={self._exclude_detection})")

        except Exception as e:
            print(f"[MLController] Erreur chargement normalization_stats: {e}")
            self._feature_mean = None
            self._feature_std = None

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
        """Construit le vecteur d'etat pour un seul pas temporel.

        Pipeline: VisionAdapter (38-dim) -> exclusion Detection (30-dim)
                  -> engineered features (41-dim)

        Args:
            state: SensorState contenant les donnees des capteurs.

        Returns:
            np.ndarray: Vecteur 26-dim (21 raw + 5 engineered) ou 34-dim si detection incluse.
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
        raw_vector = self.vision_adapter.get_state_vector(
            vision_result, imu_data, ir_data,
            line_offset=line_off,
            front_line_detected=getattr(state, 'front_line_detected', False),
            front_line_confirmed=getattr(state, 'front_line_confirmed', False),
            front_offset=getattr(state, 'front_offset', None),
            front_dash_count=getattr(state, 'front_dash_count', 0),
            corner_left_detected=getattr(state, 'corner_left_detected', False),
            corner_right_detected=getattr(state, 'corner_right_detected', False),
            corner_left_area=getattr(state, 'corner_left_area', 0),
            corner_right_area=getattr(state, 'corner_right_area', 0),
            center_dash_count=getattr(state, 'center_dash_count', 0),
        )

        # Extraire les valeurs avant l'exclusion (indices stables dans le vecteur 38-dim)
        ir_bot_r = raw_vector[1]   # IR_bottom_right
        ir_bot_l = raw_vector[3]   # IR_bottom_left
        ir_sum = (ir_bot_l + ir_bot_r) / 2.0
        gyro_z = raw_vector[18]    # gyro_z cumulatif (toujours index 18 dans le 38-dim)

        # Appliquer le masque d'exclusion Detection
        if self._exclude_detection:
            keep_mask = [i for i in range(len(raw_vector)) if i not in self._detection_indices]
            raw_vector = raw_vector[keep_mask]

        # Features engineered PID-inspired (9 features)
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

        # ir_error_derivative: delta calibrated_error
        ir_error_derivative = 0.0
        if self._prev_calibrated_error is not None:
            ir_error_derivative = calibrated_error - self._prev_calibrated_error
        self._prev_calibrated_error = calibrated_error

        # ir_error_integral: moyenne glissante sur INTEGRAL_WINDOW pas
        raw_dim = len(raw_vector)
        recent_errors = []
        for vec in list(self._window_buffer)[-(self.INTEGRAL_WINDOW - 1):]:
            recent_errors.append(vec[raw_dim + 0])  # calibrated_error index
        recent_errors.append(calibrated_error)
        ir_error_integral = sum(recent_errors) / len(recent_errors)

        # gyro_z_accel: delta gyro_z_rate
        gyro_z_accel = 0.0
        if self._prev_gyro_z_rate is not None:
            gyro_z_accel = gyro_z_rate - self._prev_gyro_z_rate
        self._prev_gyro_z_rate = gyro_z_rate

        # lookahead_delta: discordance camera (ligne devant) vs IR (ligne dessous)
        line_camera_offset = raw_vector[raw_dim - 2] if raw_dim >= 2 else 0.0
        lookahead_delta = (line_camera_offset - cal_error_norm) * line_visible

        # --- Features DSP ---

        # ir_sum_accel: 2eme derivee de ir_sum
        ir_sum_delta = 0.0
        ir_sum_accel = 0.0
        if self._prev_ir_sum is not None:
            ir_sum_delta = ir_sum - self._prev_ir_sum
            if self._prev_ir_sum_delta is not None:
                ir_sum_accel = ir_sum_delta - self._prev_ir_sum_delta
        self._prev_ir_sum = ir_sum
        self._prev_ir_sum_delta = ir_sum_delta

        # line_lost_duration: compteur de ticks sans ligne visible, normalise
        if line_visible > 0.5:
            self._line_lost_counter = 0
        else:
            self._line_lost_counter += 1
        line_lost_duration = self._line_lost_counter / self.WINDOW_SIZE

        engineered = np.array([
            calibrated_error, line_visible, cal_error_norm,
            gyro_z_rate, heading_drift,
            ir_error_derivative, ir_error_integral, gyro_z_accel, lookahead_delta,
            ir_sum_accel, line_lost_duration
        ], dtype=np.float32)

        # Exposer les features clés pour le debug logging
        self._last_step_debug = {
            'cal_error': float(calibrated_error),
            'line_visible': float(line_visible),
            'gyro_z_rate': float(gyro_z_rate),
            'lookahead_delta': float(lookahead_delta),
            'ir_error_deriv': float(ir_error_derivative),
        }

        return np.concatenate([raw_vector, engineered])

    def _build_state_vector(self, state) -> np.ndarray:
        """Construit le vecteur d'etat complet via fenetre glissante.

        Pipeline: step vector -> window buffer -> decay temporel
                  -> concatenation -> z-score

        Args:
            state: SensorState contenant les donnees des capteurs.

        Returns:
            np.ndarray: Vecteur normalise pret pour l'inference.
        """
        # 1. Construire le vecteur du pas actuel
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
            slot = offset + i  # position dans la fenetre (0=plus ancien)
            start = slot * feature_dim
            end = start + feature_dim

            # Appliquer le decay temporel
            if self._decay_weights is not None:
                full_vector[start:end] = vec * self._decay_weights[slot]
            else:
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
        import time as _time
        t0 = _time.perf_counter()

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

                # Debug logging périodique
                if self._debug_enabled and self._inference_count % self._debug_interval == 0:
                    step_ms = (_time.perf_counter() - t0) * 1000
                    output_delta = float(np.abs(output - self._prev_output).sum()) if self._prev_output is not None else 0.0
                    self._debug_log.append({
                        'tick': self._inference_count,
                        'override': False,
                        'step_ms': round(step_ms, 1),
                        'ir': [round(float(x), 1) for x in state.ir_sensors] if state.ir_sensors else None,
                        'line_offset': round(float(state.line_offset), 3) if getattr(state, 'line_offset', None) is not None else None,
                        **{k: round(v, 4) for k, v in self._last_step_debug.items()},
                        'output': [round(float(output[0]), 4), round(float(output[1]), 4)],
                        'output_delta': round(output_delta, 4),
                        'input_range': [round(float(input_vector.min()), 2), round(float(input_vector.max()), 2)],
                    })
                self._prev_output = output.copy()

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
        self._prev_calibrated_error = None
        self._prev_gyro_z_rate = None
        self._prev_ir_sum = None
        self._prev_ir_sum_delta = None
        self._line_lost_counter = 0
        if self._interpreter is None and self.model_path:
            self._load_model()
            self._load_normalization_stats()

        if self._interpreter:
            expected_dim = self._input_details[0]['shape'][1]
            print(f"[MLController] Demarré: {self.model_path}")
            print(f"[MLController] TFLite input: {expected_dim}-dim, "
                  f"fenetre={self.WINDOW_SIZE}x{self.WINDOW_FEATURE_DIM}, "
                  f"decay={self.TEMPORAL_DECAY}, "
                  f"ir_offset={self.IR_OFFSET_BOTTOM:.1f}")
        else:
            print("[MLController] Démarré SANS modèle (commandes = 0)")

    def stop(self):
        """Arrête le contrôleur ML."""
        print(f"[MLController] Arrêté. Inférences effectuées: {self._inference_count}")

        # Sauvegarder et résumer le debug log
        if self._debug_log:
            ml_entries = [e for e in self._debug_log if not e.get('override', False)]
            override_entries = [e for e in self._debug_log if e.get('override', False)]

            if ml_entries:
                timings = [e['step_ms'] for e in ml_entries]
                deltas = [e['output_delta'] for e in ml_entries]
                print(f"  [DEBUG] {len(ml_entries)} entries ML, {len(override_entries)} overrides")
                print(f"  [DEBUG] Timing: mean={np.mean(timings):.1f}ms, max={np.max(timings):.1f}ms")
                print(f"  [DEBUG] Output delta: mean={np.mean(deltas):.4f}, max={np.max(deltas):.4f}")
                if np.mean(deltas) < 0.001:
                    print(f"  [DEBUG] ALERTE: Le modele donne des sorties quasi-identiques!")

            import json
            from pathlib import Path
            log_path = Path(self.model_path).parent / 'debug_log.json'
            with open(log_path, 'w') as f:
                json.dump(self._debug_log, f, indent=2)
            print(f"  [DEBUG] Log sauvegardé: {log_path}")

    def set_debug(self, enabled):
        """Active ou désactive le debug logging."""
        self._debug_enabled = enabled
        if enabled:
            self._debug_log = []
            self._prev_output = None
        print(f"[MLController] Debug {'activé' if enabled else 'désactivé'}")

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