#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Sensor Profiler — Séquence interactive de caractérisation robot.

Machine à états qui guide l'utilisateur à travers 18 phases (statiques
et automatiques) pour mapper les réponses des capteurs sous conditions
contrôlées. Produit un profil JSON par robot.

Voir SENSOR_PROFILER_PLAN.md pour le plan complet.
"""

import json
import time
import threading
import numpy as np
from pathlib import Path
from datetime import datetime

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


# ============================================================
# Définition des phases
# ============================================================

PHASES = [
    # Groupe A: Mapping statique des surfaces
    {
        "id": "A1_road_baseline",
        "group": "A",
        "type": "static",
        "instruction": "Placez le robot sur la ROUTE NOIRE (sans ligne, espace dégagé)",
        "description": "Baseline IR de la route, référence IMU au repos",
        "params": {"n_samples": 100},
    },
    {
        "id": "A2_line_centered",
        "group": "A",
        "type": "static",
        "instruction": "Placez le robot CENTRÉ sur un tiret de LIGNE BLANCHE",
        "description": "IR quand les 2 capteurs sont sur/près de la ligne",
        "params": {"n_samples": 100},
    },
    {
        "id": "A3_offset_left",
        "group": "A",
        "type": "static",
        "instruction": "Décalez le robot à GAUCHE de la ligne (capteur DROIT sur la ligne)",
        "description": "IR profil offset gauche",
        "params": {"n_samples": 100},
    },
    {
        "id": "A4_offset_right",
        "group": "A",
        "type": "static",
        "instruction": "Décalez le robot à DROITE de la ligne (capteur GAUCHE sur la ligne)",
        "description": "IR profil offset droit",
        "params": {"n_samples": 100},
    },
    {
        "id": "A5_grass",
        "group": "A",
        "type": "static",
        "instruction": "Placez le robot sur le GAZON (hors de la route)",
        "description": "Baseline IR du gazon",
        "params": {"n_samples": 100},
    },
    {
        "id": "A6_off_mat",
        "group": "A",
        "type": "static",
        "instruction": "Placez le robot HORS DU TAPIS (table ou sol)",
        "description": "Baseline IR hors-tapis",
        "params": {"n_samples": 100},
    },

    # Groupe B: Caractérisation moteur
    {
        "id": "B1a_fwd_10_raw",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Positionnez le robot avec espace devant (~30cm). Avancer vitesse 10 RAW",
        "description": "Dérive gyro_z naturelle à basse vitesse",
        "params": {"speed": 10, "duration": 3.0, "pid": False},
    },
    {
        "id": "B1b_fwd_10_pid",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Replacez le robot. Avancer vitesse 10 avec PID de cap",
        "description": "Correction PID appliquée à basse vitesse",
        "params": {"speed": 10, "duration": 3.0, "pid": True},
    },
    {
        "id": "B2a_fwd_20_raw",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Replacez le robot. Avancer vitesse 20 RAW",
        "description": "Dérive naturelle à vitesse moyenne",
        "params": {"speed": 20, "duration": 3.0, "pid": False},
    },
    {
        "id": "B2b_fwd_20_pid",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Replacez le robot. Avancer vitesse 20 PID cap",
        "description": "Correction PID à vitesse moyenne",
        "params": {"speed": 20, "duration": 3.0, "pid": True},
    },
    {
        "id": "B3a_fwd_30_raw",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Replacez le robot. Avancer vitesse 30 RAW",
        "description": "Dérive naturelle à haute vitesse",
        "params": {"speed": 30, "duration": 3.0, "pid": False},
    },
    {
        "id": "B3b_fwd_30_pid",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Replacez le robot. Avancer vitesse 30 PID cap",
        "description": "Correction PID à haute vitesse",
        "params": {"speed": 30, "duration": 3.0, "pid": True},
    },
    {
        "id": "B4_rev_15_raw",
        "group": "B",
        "type": "auto_drive",
        "instruction": "Espace derrière (~30cm). Reculer vitesse 15 RAW",
        "description": "Dérive en marche arrière",
        "params": {"speed": -15, "duration": 3.0, "pid": False},
    },

    # Groupe C: Caractérisation gyroscope
    {
        "id": "C1_rot_left",
        "group": "C",
        "type": "auto_rotate",
        "instruction": "Confirmez: espace pour tourner sur place. Rotation gauche 2s",
        "description": "Angle parcouru, vitesse angulaire, IR pendant rotation",
        "params": {"direction": 1, "speed": 1, "duration": 2.0},
    },
    {
        "id": "C2_rot_right",
        "group": "C",
        "type": "auto_rotate",
        "instruction": "Robot prêt. Rotation droite 2s",
        "description": "Idem direction opposée, détecte asymétrie",
        "params": {"direction": -1, "speed": 1, "duration": 2.0},
    },
    {
        "id": "C3_rot_90x4",
        "group": "C",
        "type": "auto_rotate_repeat",
        "instruction": "Robot prêt. 4x rotation gauche 0.5s",
        "description": "Répétabilité (erreur cumulée)",
        "params": {"direction": 1, "speed": 1, "duration": 0.5, "repeats": 4},
    },

    # Groupe D: Profil IR croisement de ligne (manoeuvres manuelles)
    {
        "id": "D1_cross_right",
        "group": "D",
        "type": "manual_sampling",
        "instruction": "Placez au bord GAUCHE de la route. Pilotez manuellement en dérivant vers la DROITE. Appuyez sur Enregistrer avant de commencer, Stop quand terminé.",
        "description": "Profil IR: bord gauche → ligne → bord droit",
        "params": {"min_valid_runs": 3, "expected_direction": "left_to_right"},
    },
    {
        "id": "D2_cross_left",
        "group": "D",
        "type": "manual_sampling",
        "instruction": "Placez au bord DROIT de la route. Pilotez en dérivant vers la GAUCHE. Appuyez sur Enregistrer avant de commencer, Stop quand terminé.",
        "description": "Profil IR: bord droit → ligne → bord gauche",
        "params": {"min_valid_runs": 3, "expected_direction": "right_to_left"},
    },
]


# ============================================================
# CalibrationController
# ============================================================

class CalibrationController(ControllerBase):
    """Contrôleur qui exécute des manoeuvres planifiées pour le profiling.

    Activé par le SensorProfiler pour les phases automatiques (B, C).
    step() retourne la commande moteur et enregistre les capteurs.
    """

    def __init__(self):
        self._maneuver = None
        self._start_time = None
        self._samples = []
        self._done = False
        self._timeout = 10.0

    @property
    def name(self):
        return "calibration_controller"

    def set_maneuver(self, maneuver_type, params):
        """Configure la prochaine manoeuvre.

        Peut être appelé avant ou après start(). La manoeuvre persiste
        à travers les appels start()/stop() du ControlManager.

        Args:
            maneuver_type: "drive_raw", "rotate", "static_record"
            params: dict avec les paramètres de la manoeuvre
        """
        self._maneuver = (maneuver_type, params)

    def clear_maneuver(self):
        """Efface la manoeuvre configurée. Appelé manuellement quand on veut reset."""
        self._maneuver = None

    def step(self, state):
        """Retourne la commande moteur et enregistre les capteurs."""
        if self._maneuver is None or self._done:
            return MotorCommand.stop()

        if self._start_time is None:
            self._start_time = time.time()

        elapsed = time.time() - self._start_time
        mtype, params = self._maneuver

        # Enregistrer les données capteurs
        sample = {
            "t": round(elapsed, 4),
            "ir": list(state.ir_sensors) if state.ir_sensors else None,
            "imu": list(state.gyro_angles) if state.gyro_angles else None,
        }
        self._samples.append(sample)

        # Timeout sécurité
        if elapsed > self._timeout:
            self._done = True
            return MotorCommand.stop()

        # --- Manoeuvres ---

        if mtype == "static_record":
            # Phase statique: juste enregistrer, pas de mouvement
            n_target = params.get("n_samples", 100)
            if len(self._samples) >= n_target:
                self._done = True
            return MotorCommand.stop()

        elif mtype == "drive_raw":
            if elapsed >= params["duration"]:
                self._done = True
                return MotorCommand.stop()
            speed = params["speed"]
            return MotorCommand.make_speed(speed, speed)

        elif mtype == "drive_pid":
            # Avance avec correction de cap proportionnelle (comme ManualController)
            if elapsed >= params["duration"]:
                self._done = True
                return MotorCommand.stop()
            speed = params["speed"]
            # Correction de cap via gyro_z
            heading = 0.0
            if state.gyro_angles and len(state.gyro_angles) > 2:
                heading = float(state.gyro_angles[2])
            # Premier tick: capturer le cap de référence
            if self._desired_heading is None:
                self._desired_heading = heading
            error = heading - self._desired_heading
            kp = 1.9
            correction = max(-15, min(9, error * kp))
            left = speed + correction
            right = speed - correction
            # Enregistrer la correction dans le sample
            self._samples[-1]["correction"] = round(correction, 2)
            self._samples[-1]["heading"] = round(heading, 2)
            return MotorCommand.make_speed(left, right)

        elif mtype == "rotate":
            if elapsed >= params["duration"]:
                self._done = True
                return MotorCommand.stop()
            d = params.get("direction", 1)
            s = params.get("speed", 1)
            return MotorCommand.make_speed(-d * s, d * s)

        elif mtype == "rotate_repeat":
            # N rotations avec pause de 0.5s entre chaque
            repeats = params.get("repeats", 4)
            rot_duration = params.get("duration", 0.5)
            pause = 0.3
            cycle = rot_duration + pause
            total_duration = cycle * repeats

            if elapsed >= total_duration:
                self._done = True
                return MotorCommand.stop()

            # Dans quel cycle sommes-nous?
            cycle_pos = elapsed % cycle
            if cycle_pos < rot_duration:
                # Phase rotation
                d = params.get("direction", 1)
                s = params.get("speed", 1)
                return MotorCommand.make_speed(-d * s, d * s)
            else:
                # Phase pause
                return MotorCommand.stop()

        return MotorCommand.stop()

    def get_samples(self):
        """Retourne les samples collectés."""
        return list(self._samples)

    @property
    def is_done(self):
        return self._done

    def start(self):
        """Appelé par ControlManager à l'activation. Reset l'état d'exécution
        mais conserve la manoeuvre configurée par set_maneuver()."""
        self._start_time = None
        self._samples = []
        self._done = False
        self._desired_heading = None  # pour drive_pid

    def stop(self):
        """Appelé par ControlManager à la désactivation."""
        self._done = True


# ============================================================
# SensorProfiler
# ============================================================

class SensorProfiler:
    """Orchestrateur de la séquence de profiling.

    Gère la progression des phases, délègue les manoeuvres au
    CalibrationController, et calcule les dérivés à la fin.
    """

    def __init__(self, robot):
        self.robot = robot
        self.phases = list(PHASES)
        self.current_phase_idx = -1
        self.profile_data = {}
        self.robot_id = "zumi_1"
        self.is_active = False
        self._controller = CalibrationController()
        self._recording = False
        self._manual_runs = []  # Pour les phases D

    def start(self, robot_id="zumi_1"):
        """Démarre la séquence de profiling."""
        self.robot_id = robot_id
        self.profile_data = {
            "robot_id": robot_id,
            "timestamp": datetime.now().isoformat(),
            "phases": {},
        }
        self.current_phase_idx = 0
        self.is_active = True
        self._manual_runs = []
        print("[SensorProfiler] Démarré pour {}. {} phases.".format(
            robot_id, len(self.phases)))

    def get_status(self):
        """Retourne l'état actuel pour le UI."""
        if not self.is_active:
            return {"active": False}

        if self.current_phase_idx >= len(self.phases):
            return {
                "active": True,
                "completed": True,
                "total_phases": len(self.phases),
                "completed_phases": len(self.profile_data.get("phases", {})),
            }

        phase = self.phases[self.current_phase_idx]
        completed_ids = list(self.profile_data.get("phases", {}).keys())

        status = {
            "active": True,
            "completed": False,
            "current_phase": self.current_phase_idx + 1,
            "total_phases": len(self.phases),
            "phase_id": phase["id"],
            "phase_group": phase["group"],
            "phase_type": phase["type"],
            "instruction": phase["instruction"],
            "description": phase["description"],
            "completed_phases": completed_ids,
            "robot_id": self.robot_id,
        }

        # Info additionnelle pour phases manuelles (D)
        if phase["type"] == "manual_sampling":
            min_runs = phase["params"].get("min_valid_runs", 3)
            valid = sum(1 for r in self._manual_runs if r.get("quality") == "valid")
            status["manual_valid_runs"] = valid
            status["manual_min_runs"] = min_runs
            status["manual_total_runs"] = len(self._manual_runs)
            status["recording"] = self._recording

        # Info pour phases auto en cours
        if self._controller._maneuver is not None and not self._controller.is_done:
            status["auto_running"] = True
            status["auto_samples"] = len(self._controller.get_samples())
        else:
            status["auto_running"] = False

        return status

    def record_static(self):
        """Enregistre N samples pour la phase statique courante.

        Le CalibrationController est utilisé en mode static_record.
        Retourne les résultats de la phase.
        """
        if not self.is_active or self.current_phase_idx >= len(self.phases):
            return {"error": "Profiler pas actif ou terminé"}

        phase = self.phases[self.current_phase_idx]
        if phase["type"] != "static":
            return {"error": "Phase courante n'est pas statique: {}".format(phase["type"])}

        n_samples = phase["params"].get("n_samples", 100)
        print("[SensorProfiler] Enregistrement statique: {} ({} samples)".format(
            phase["id"], n_samples))

        # Lire les capteurs directement (pas besoin du control loop)
        samples = []
        for i in range(n_samples):
            ir = self.robot.get_ir_data()
            imu = self.robot.get_angles()
            samples.append({
                "ir": list(ir) if ir else None,
                "imu": list(imu) if imu else None,
            })
            time.sleep(0.02)  # ~50Hz

        # Calculer les statistiques
        ir_arr = np.array([s["ir"] for s in samples if s["ir"] is not None], dtype=np.float64)
        imu_arr = np.array([s["imu"] for s in samples if s["imu"] is not None], dtype=np.float64)

        result = {
            "description": phase["description"],
            "n_samples": len(samples),
            "ir_mean": ir_arr.mean(axis=0).tolist() if len(ir_arr) > 0 else None,
            "ir_std": ir_arr.std(axis=0).tolist() if len(ir_arr) > 0 else None,
            "ir_min": ir_arr.min(axis=0).tolist() if len(ir_arr) > 0 else None,
            "ir_max": ir_arr.max(axis=0).tolist() if len(ir_arr) > 0 else None,
            "imu_mean": imu_arr.mean(axis=0).tolist() if len(imu_arr) > 0 else None,
            "imu_std": imu_arr.std(axis=0).tolist() if len(imu_arr) > 0 else None,
            "raw_samples": samples,
        }

        self.profile_data["phases"][phase["id"]] = result
        print("[SensorProfiler] Phase {} complétée: {} samples, IR_mean={}".format(
            phase["id"], len(samples),
            [round(v, 1) for v in result["ir_mean"]] if result["ir_mean"] else "N/A"))

        return result

    def get_controller(self):
        """Retourne le CalibrationController pour activation via ControlManager."""
        return self._controller

    def run_auto_phase(self):
        """Configure et lance la manoeuvre auto de la phase courante.

        Retourne la config pour que le serveur active le controller.
        """
        if not self.is_active or self.current_phase_idx >= len(self.phases):
            return {"error": "Profiler pas actif ou terminé"}

        phase = self.phases[self.current_phase_idx]

        if phase["type"] == "auto_drive":
            params = phase["params"]
            maneuver_type = "drive_pid" if params.get("pid") else "drive_raw"
            self._controller.set_maneuver(maneuver_type, {
                "speed": params["speed"],
                "duration": params["duration"],
            })
            return {"action": "activate_calibration_controller",
                    "phase_id": phase["id"], "duration": params["duration"]}

        elif phase["type"] == "auto_rotate":
            self._controller.set_maneuver("rotate", phase["params"])
            return {"action": "activate_calibration_controller",
                    "phase_id": phase["id"], "duration": phase["params"]["duration"]}

        elif phase["type"] == "auto_rotate_repeat":
            p = phase["params"]
            total = (p["duration"] + 0.3) * p.get("repeats", 4)
            self._controller.set_maneuver("rotate_repeat", {
                "direction": p["direction"],
                "speed": p["speed"],
                "duration": p["duration"],
                "repeats": p.get("repeats", 4),
            })
            return {"action": "activate_calibration_controller",
                    "phase_id": phase["id"], "duration": total}

        return {"error": "Type de phase non supporté: {}".format(phase["type"])}

    # ------------------------------------------------------------------
    #  Enregistrement manuel (phases D)
    # ------------------------------------------------------------------

    def start_manual_recording(self):
        """Démarre l'enregistrement des capteurs en arrière-plan.

        L'utilisateur pilote le robot avec WASD pendant que ce thread
        enregistre IR + IMU à 20Hz. Appeler stop_manual_recording()
        pour arrêter et récupérer les samples.
        """
        if self._recording:
            return {"error": "Enregistrement déjà en cours"}

        self._recording = True
        self._manual_samples = []

        def _record_loop():
            while self._recording:
                ir = self.robot.get_ir_data()
                imu = self.robot.get_angles()
                self._manual_samples.append({
                    "ir": list(ir) if ir else None,
                    "imu": list(imu) if imu else None,
                    "t": len(self._manual_samples) * 0.05,
                })
                time.sleep(0.05)

        self._record_thread = threading.Thread(target=_record_loop, daemon=True)
        self._record_thread.start()
        print("[SensorProfiler] Enregistrement manuel démarré")
        return {"status": "recording"}

    def stop_manual_recording(self):
        """Arrête l'enregistrement et valide le run.

        Retourne le résultat avec la qualité du run.
        """
        if not self._recording:
            return {"error": "Pas d'enregistrement en cours"}

        self._recording = False
        self._record_thread.join(timeout=2.0)
        samples = self._manual_samples

        n = len(samples)
        if n < 5:
            result = {"quality": "rejected", "reason": "Trop peu de samples ({})".format(n),
                      "n_samples": n}
            self._manual_runs.append(result)
            return result

        # Validation: détecter une traversée de ligne
        # La traversée se manifeste par une chute significative de ir_sum
        ir_data = [s["ir"] for s in samples if s.get("ir")]
        if not ir_data:
            result = {"quality": "rejected", "reason": "Pas de données IR", "n_samples": 0}
            self._manual_runs.append(result)
            return result

        ir_arr = np.array(ir_data)
        ir_sum = (ir_arr[:, 1] + ir_arr[:, 3]) / 2.0  # (bot_r + bot_l) / 2
        ir_sum_min = ir_sum.min()
        ir_sum_max = ir_sum.max()
        ir_range = ir_sum_max - ir_sum_min

        # Une traversée de ligne cause une chute de ir_sum > 30
        if ir_range < 30:
            result = {"quality": "rejected",
                      "reason": "Pas de traversée de ligne détectée (variation IR: {:.0f})".format(ir_range),
                      "n_samples": n, "ir_range": round(float(ir_range), 1)}
            self._manual_runs.append(result)
            return result

        result = {"quality": "valid", "n_samples": n,
                  "ir_range": round(float(ir_range), 1),
                  "ir_timeseries": samples}
        self._manual_runs.append(result)

        # Vérifier si on a assez de runs valides
        phase = self.phases[self.current_phase_idx]
        min_valid = phase["params"].get("min_valid_runs", 3)
        valid_count = sum(1 for r in self._manual_runs if r.get("quality") == "valid")

        print("[SensorProfiler] Run manuel: {} ({} samples, IR range={:.0f}). "
              "Valides: {}/{}".format(
                  result["quality"], n, ir_range, valid_count, min_valid))

        return {**result, "valid_count": valid_count, "min_valid": min_valid,
                "phase_complete": valid_count >= min_valid}

    def finalize_manual_phase(self):
        """Finalise la phase manuelle et sauvegarde les runs valides."""
        phase = self.phases[self.current_phase_idx]
        valid_runs = [r for r in self._manual_runs if r.get("quality") == "valid"]
        rejected_runs = [r for r in self._manual_runs if r.get("quality") == "rejected"]

        result = {
            "description": phase["description"],
            "expected_direction": phase["params"].get("expected_direction", "unknown"),
            "valid_runs": len(valid_runs),
            "rejected_runs": len(rejected_runs),
            "runs": self._manual_runs,
        }
        self.profile_data["phases"][phase["id"]] = result
        self._manual_runs = []
        print("[SensorProfiler] Phase {} finalisée: {} runs valides".format(
            phase["id"], len(valid_runs)))
        return result

    def collect_auto_results(self):
        """Collecte les résultats d'une manoeuvre auto terminée."""
        if not self._controller.is_done:
            return None

        phase = self.phases[self.current_phase_idx]
        samples = self._controller.get_samples()

        # Extraire les statistiques des timeseries
        ir_data = [s["ir"] for s in samples if s.get("ir")]
        imu_data = [s["imu"] for s in samples if s.get("imu")]

        result = {
            "description": phase["description"],
            "n_samples": len(samples),
            "timeseries": samples,
        }

        # Stats spécifiques aux phases B (drive)
        if phase["type"] == "auto_drive" and imu_data:
            imu_arr = np.array(imu_data)
            gyro_z_start = imu_arr[0, 2] if len(imu_arr) > 0 else 0
            gyro_z_end = imu_arr[-1, 2] if len(imu_arr) > 0 else 0
            duration = samples[-1]["t"] if samples else 0
            result["gyro_z_start"] = round(float(gyro_z_start), 2)
            result["gyro_z_end"] = round(float(gyro_z_end), 2)
            result["gyro_z_drift_rate"] = round(
                float(gyro_z_end - gyro_z_start) / duration if duration > 0 else 0, 2)
            result["commanded_speed"] = phase["params"].get("speed", 0)

        # Stats spécifiques aux phases C (rotation)
        if phase["type"] in ("auto_rotate", "auto_rotate_repeat") and imu_data:
            imu_arr = np.array(imu_data)
            gyro_z_start = imu_arr[0, 2] if len(imu_arr) > 0 else 0
            gyro_z_end = imu_arr[-1, 2] if len(imu_arr) > 0 else 0
            duration = samples[-1]["t"] if samples else 0
            result["angle_covered"] = round(float(gyro_z_end - gyro_z_start), 2)
            result["duration_actual"] = round(duration, 2)
            if duration > 0:
                result["angular_velocity_mean"] = round(
                    float(gyro_z_end - gyro_z_start) / duration, 2)

        self.profile_data["phases"][phase["id"]] = result
        print("[SensorProfiler] Phase {} complétée: {} samples".format(
            phase["id"], len(samples)))

        return result

    def next_phase(self):
        """Passe à la phase suivante."""
        if not self.is_active:
            return {"error": "Profiler pas actif"}

        self.current_phase_idx += 1
        self._manual_runs = []

        if self.current_phase_idx >= len(self.phases):
            self.is_active = False
            self.compute_derived()
            print("[SensorProfiler] Toutes les phases complétées!")
            return {"completed": True}

        phase = self.phases[self.current_phase_idx]
        print("[SensorProfiler] Phase {}/{}: {} — {}".format(
            self.current_phase_idx + 1, len(self.phases),
            phase["id"], phase["instruction"]))

        return {"phase_idx": self.current_phase_idx, "phase_id": phase["id"]}

    def stop_and_save(self):
        """Arrête le profiling et sauvegarde le profil (même partiel)."""
        self.is_active = False
        self.compute_derived()
        path = self.save_profile()
        return {"saved": str(path), "n_phases_completed": len(self.profile_data.get("phases", {}))}

    def compute_derived(self):
        """Calcule les valeurs dérivées depuis les données collectées."""
        phases = self.profile_data.get("phases", {})
        derived = {}

        # IR offsets depuis A1 (route baseline)
        a1 = phases.get("A1_road_baseline")
        if a1 and a1.get("ir_mean"):
            ir = a1["ir_mean"]
            # Indices: 0=front_r, 1=bottom_r, 2=back_r, 3=bottom_l, 4=back_l, 5=front_l
            derived["ir_offsets"] = {
                "bottom": round(ir[3] - ir[1], 1),
                "front": round(ir[5] - ir[0], 1),
                "back": round(ir[4] - ir[2], 1),
            }
            derived["ir_baselines"] = [round(v, 1) for v in ir]

        # Seuils de surface depuis A1-A6
        thresholds = {}
        if a1 and a1.get("ir_mean"):
            road_sum = (a1["ir_mean"][1] + a1["ir_mean"][3]) / 2
            thresholds["road_ir_sum_mean"] = round(road_sum, 1)

        a2 = phases.get("A2_line_centered")
        if a2 and a2.get("ir_mean"):
            line_sum = (a2["ir_mean"][1] + a2["ir_mean"][3]) / 2
            thresholds["line_ir_sum_mean"] = round(line_sum, 1)
            # Gap threshold = midpoint entre ligne et route
            if "road_ir_sum_mean" in thresholds:
                thresholds["gap_threshold"] = round(
                    (thresholds["road_ir_sum_mean"] + line_sum) / 2, 1)

        a5 = phases.get("A5_grass")
        if a5 and a5.get("ir_mean"):
            grass_sum = (a5["ir_mean"][1] + a5["ir_mean"][3]) / 2
            thresholds["grass_ir_sum_mean"] = round(grass_sum, 1)
            # Off-road threshold = midpoint entre gazon et route
            if "road_ir_sum_mean" in thresholds:
                thresholds["off_road_threshold"] = round(
                    (thresholds["road_ir_sum_mean"] + grass_sum) / 2, 1)

        if thresholds:
            derived["surface_thresholds"] = thresholds

        # Asymétrie moteur depuis phases B (RAW)
        motor = {}
        for speed_label, phase_id in [("10", "B1a_fwd_10_raw"), ("20", "B2a_fwd_20_raw"),
                                       ("30", "B3a_fwd_30_raw")]:
            b = phases.get(phase_id)
            if b and "gyro_z_drift_rate" in b:
                motor["speed_" + speed_label] = {
                    "drift_deg_per_s": b["gyro_z_drift_rate"],
                }
        if motor:
            derived["motor_asymmetry"] = motor

        # Gyro depuis phases C
        gyro = {}
        c1 = phases.get("C1_rot_left")
        if c1 and "angle_covered" in c1:
            gyro["left_2s_angle"] = c1["angle_covered"]
        c2 = phases.get("C2_rot_right")
        if c2 and "angle_covered" in c2:
            gyro["right_2s_angle"] = c2["angle_covered"]
        if gyro:
            derived["gyro_characterization"] = gyro

        self.profile_data["derived"] = derived
        print("[SensorProfiler] Dérivés calculés: {}".format(list(derived.keys())))

    def save_profile(self):
        """Sauvegarde le profil en JSON."""
        output_dir = Path(__file__).parent.parent.parent / "MLP_model_trainer" / "sensor_profiles"
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "sensor_profile_{}_{}.json".format(self.robot_id, date_str)
        filepath = output_dir / filename

        # Sauvegarder sans les raw_samples pour garder un fichier lisible
        # Les raw sont dans un fichier séparé si nécessaire
        with open(str(filepath), 'w') as f:
            json.dump(self.profile_data, f, indent=2, default=str)

        self._last_save_path = filepath
        print("[SensorProfiler] Profil sauvegardé: {}".format(filepath))
        return filepath

    def get_summary(self):
        """Retourne un résumé des résultats pour l'écran de fin."""
        phases = self.profile_data.get("phases", {})
        derived = self.profile_data.get("derived", {})

        # Total samples
        total_samples = 0
        for p in phases.values():
            n = p.get("n_samples", 0)
            total_samples += n
            # Phases manuelles: compter les runs
            for run in p.get("runs", []):
                if run.get("quality") == "valid":
                    total_samples += run.get("n_samples", 0)

        summary = {
            "robot_id": self.profile_data.get("robot_id", "?"),
            "n_phases_completed": len(phases),
            "total_samples": total_samples,
        }

        # IR offsets
        if "ir_offsets" in derived:
            summary["ir_offsets"] = derived["ir_offsets"]

        # Seuils
        if "surface_thresholds" in derived:
            summary["thresholds"] = derived["surface_thresholds"]

        # Asymétrie moteur
        if "motor_asymmetry" in derived:
            summary["motor_asymmetry"] = derived["motor_asymmetry"]

        # Gyro
        if "gyro_characterization" in derived:
            summary["gyro"] = derived["gyro_characterization"]

        # Chemin du fichier sauvegardé
        if hasattr(self, '_last_save_path'):
            summary["save_path"] = str(self._last_save_path)

        return summary
