#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pid_ir_controller.py
# ------------------
"""Contrôleur PID de suivi de ligne basé sur les capteurs IR bottom.

Implémente ControllerBase. Utilise la différence entre IR_bottom_left et
IR_bottom_right comme signal d'erreur pour un PID classique.

Contexte physique :
    Route NOIRE, ligne BLANCHE (traitillée).
    IR bottom : valeur HAUTE = surface claire (ligne), BASSE = surface sombre (route).

Signal d'erreur :
    error = IR_bottom_right - IR_bottom_left
    > 0 : ligne sous capteur droit → robot décalé à gauche → tourner à droite
    < 0 : ligne sous capteur gauche → robot décalé à droite → tourner à gauche

Commande différentielle :
    left_speed  = base_speed + correction   (correction > 0 → accélère gauche → tourne à droite)
    right_speed = base_speed - correction

Détection de perte de ligne :
    Si IR_sum (moyenne des deux IR bottom) passe SOUS un seuil, les deux capteurs
    voient du noir (route) → la ligne est perdue → arrêt.
"""

import time

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand

# Index du cap (heading) dans state.gyro_angles
# gyro_angles = [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt]
_HEADING_INDEX = 2  # Gyro_z = cap intégré en degrés


class PIDIRController(ControllerBase):
    """Contrôleur PID sur capteurs IR bottom pour le suivi de ligne.

    Args:
        base_speed (int): Vitesse de base en ligne droite [1-50].
        kp (float): Gain proportionnel.
        ki (float): Gain intégral.
        kd (float): Gain dérivé.
        max_correction (int): Correction différentielle maximale.
        line_lost_threshold (float): Seuil IR_sum en-dessous duquel
            la ligne est considérée perdue (les deux capteurs voient noir/route).
    """

    MOTOR_SPEED_MAX = 50

    def __init__(
        self,
        base_speed=5,
        kp=0.0475,
        ki=0.0,
        kd=-0.00463,
        max_correction=8,
        line_lost_threshold=80.0,
        ir_offset=0.0,
        calibration_samples=10,
        gap_threshold=195.0,
        heading_kp=1.8,
        heading_max_correction=10.0,
    ):
        self._base_speed = base_speed
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._max_correction = max_correction
        self._line_lost_threshold = line_lost_threshold
        self._ir_offset = ir_offset
        self._calibration_samples = calibration_samples

        # Maintien de cap gyroscopique (actif dans les trous de la ligne traitillée)
        self._gap_threshold = gap_threshold
        self._heading_kp = heading_kp
        self._heading_max_correction = heading_max_correction
        self._heading_hold_active = False
        self._desired_heading = 0.0
        self._in_gap = False

        # État PID
        self._integral = 0.0
        self._prev_error = 0.0

        # État calibration
        self._calibrating = False
        self._calibration_buffer = []

        # Détection d'oscillation (pour trouver Tu)
        self._osc_zero_crossings = []  # timestamps des changements de signe de correction
        self._osc_prev_sign = 0        # signe précédent de la correction (+1, -1, 0)
        self._osc_tu = None            # période d'oscillation détectée (secondes)
        self._osc_min_crossings = 6    # min de zero-crossings pour valider Tu
        self._osc_max_variation = 0.3  # variation max entre périodes (30%) pour considérer stable

        # Debug
        self._last_error = 0.0
        self._last_correction = 0.0
        self._last_ir_left = 0
        self._last_ir_right = 0
        self._last_ir_sum = 0.0
        self._line_lost = False

    # ------------------------------------------------------------------
    #  Interface ControllerBase
    # ------------------------------------------------------------------

    @property
    def name(self):
        return "pid_ir"

    def start(self):
        """Réinitialise l'état PID et lance l'auto-calibration IR."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._line_lost = False
        # Reset oscillation detection
        self._osc_zero_crossings = []
        self._osc_prev_sign = 0
        self._osc_tu = None
        # Reset heading hold
        self._heading_hold_active = False
        self._desired_heading = 0.0
        self._in_gap = False
        # Lancer l'auto-calibration sur les N premiers ticks
        self._calibrating = True
        self._calibration_buffer = []
        print("[PID_IR] Démarré (base_speed={}, Kp={}, Ki={}, Kd={}, ir_offset={})".format(
            self._base_speed, self._kp, self._ki, self._kd, self._ir_offset
        ))
        print("[PID_IR] Auto-calibration IR sur {} échantillons...".format(self._calibration_samples))

    def stop(self):
        print("[PID_IR] Arrêté")

    def _get_heading(self, state):
        """Extrait le cap intégré (Gyro_z) depuis l'état capteur."""
        if state and state.gyro_angles and len(state.gyro_angles) > _HEADING_INDEX:
            return float(state.gyro_angles[_HEADING_INDEX])
        return None

    def step(self, state):
        """Calcule la commande moteur via PID IR + heading hold dans les trous.

        Deux modes :
        - Ligne détectée (ir_sum < gap_threshold) : PID classique sur IR_diff
        - Trou détecté (ir_sum > gap_threshold) : maintien de cap gyroscopique

        Args:
            state (SensorState): État capteur courant.

        Returns:
            MotorCommand: Commande moteur.
        """
        # Lire les IR bottom depuis ir_sensors
        # ir_sensors = [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
        if state.ir_sensors is None or len(state.ir_sensors) < 6:
            self._line_lost = True
            return MotorCommand.stop()

        ir_bottom_right = state.ir_sensors[1]
        ir_bottom_left = state.ir_sensors[3]

        self._last_ir_left = ir_bottom_left
        self._last_ir_right = ir_bottom_right

        # Auto-calibration : accumule les N premiers échantillons puis calcule l'offset
        if self._calibrating:
            raw_diff = float(ir_bottom_right - ir_bottom_left)
            self._calibration_buffer.append(raw_diff)
            if len(self._calibration_buffer) >= self._calibration_samples:
                self._ir_offset = sum(self._calibration_buffer) / len(self._calibration_buffer)
                self._calibrating = False
                print("[PID_IR] Calibration terminée: ir_offset = {:.1f}".format(self._ir_offset))
            # Pendant la calibration, rouler tout droit sans correction
            return MotorCommand.make_speed(self._base_speed, self._base_speed)

        # Détection de perte de ligne (hors piste)
        ir_sum = (ir_bottom_left + ir_bottom_right) / 2.0
        self._last_ir_sum = ir_sum

        if ir_sum < self._line_lost_threshold:
            self._line_lost = True
            self._integral = 0.0
            self._heading_hold_active = False
            return MotorCommand.stop()

        self._line_lost = False

        # Détection de trou : les deux capteurs voient du noir (route)
        self._in_gap = ir_sum > self._gap_threshold

        # =============================================================
        #  MODE HEADING HOLD (trou entre les tirets)
        # =============================================================
        if self._in_gap:
            heading = self._get_heading(state)
            if heading is None:
                # Pas de gyro : rouler droit sans correction (fallback)
                return MotorCommand.make_speed(self._base_speed, self._base_speed)

            if not self._heading_hold_active:
                # Premier tick dans le trou : activer le heading hold
                self._heading_hold_active = True
                # Si aucun cap n'a encore été capturé en mode IR, prendre le cap courant
                if self._desired_heading == 0.0:
                    self._desired_heading = heading

            # Correction proportionnelle sur le cap
            error = heading - self._desired_heading
            correction = error * self._heading_kp
            correction = max(-self._heading_max_correction,
                             min(self._heading_max_correction, correction))

            self._last_error = error
            self._last_correction = correction

            left_speed = self._base_speed + correction
            right_speed = self._base_speed - correction

            left_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, left_speed))
            right_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, right_speed))

            return MotorCommand.make_speed(left_speed, right_speed)

        # =============================================================
        #  MODE IR PID (ligne détectée)
        # =============================================================
        self._heading_hold_active = False

        # PID sur l'erreur corrigée du biais capteur
        error = float(ir_bottom_right - ir_bottom_left) - self._ir_offset
        self._last_error = error

        self._integral += error
        derivative = error - self._prev_error
        self._prev_error = error

        # Anti-windup : limiter l'intégrale
        max_integral = self._max_correction / max(self._ki, 1e-6)
        self._integral = max(-max_integral, min(max_integral, self._integral))

        correction = (
            self._kp * error
            + self._ki * self._integral
            + self._kd * derivative
        )

        # Limiter la correction
        correction = max(-self._max_correction, min(self._max_correction, correction))
        self._last_correction = correction

        # Détection d'oscillation : tracker les changements de signe de la correction
        self._track_oscillation(correction)

        # Capturer le cap courant pour le heading hold du prochain trou
        heading = self._get_heading(state)
        if heading is not None:
            self._desired_heading = heading

        # Commande différentielle (correction > 0 → tourne à droite)
        left_speed = self._base_speed + correction
        right_speed = self._base_speed - correction

        # Clamp aux limites moteur
        left_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, left_speed))
        right_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, right_speed))

        return MotorCommand.make_speed(left_speed, right_speed)

    # ------------------------------------------------------------------
    #  Détection d'oscillation (mesure de Tu pour Ziegler-Nichols)
    # ------------------------------------------------------------------

    def _track_oscillation(self, correction):
        """Détecte les oscillations en suivant les changements de signe de la correction.

        Quand la correction change de signe de façon régulière (période stable),
        on en déduit Tu. Un cycle complet = 2 zero-crossings (positif→négatif→positif).
        """
        if abs(correction) < 0.001:
            return  # ignorer les valeurs quasi-nulles

        current_sign = 1 if correction > 0 else -1

        if self._osc_prev_sign != 0 and current_sign != self._osc_prev_sign:
            # Changement de signe détecté
            now = time.monotonic()
            self._osc_zero_crossings.append(now)

            # Garder seulement les crossings récents (dernières 10s)
            cutoff = now - 10.0
            self._osc_zero_crossings = [t for t in self._osc_zero_crossings if t > cutoff]

            # Calculer Tu si assez de crossings
            if len(self._osc_zero_crossings) >= self._osc_min_crossings:
                # Intervalles entre crossings consécutifs
                intervals = []
                for i in range(1, len(self._osc_zero_crossings)):
                    intervals.append(self._osc_zero_crossings[i] - self._osc_zero_crossings[i - 1])

                mean_interval = sum(intervals) / len(intervals)
                if mean_interval > 0.01:
                    # Vérifier la stabilité des intervalles
                    max_dev = max(abs(iv - mean_interval) for iv in intervals)
                    if max_dev / mean_interval <= self._osc_max_variation:
                        # Tu = période complète = 2 x intervalle moyen entre crossings
                        tu = mean_interval * 2.0
                        if self._osc_tu is None or abs(tu - self._osc_tu) > 0.01:
                            self._osc_tu = tu
                            print("[PID_IR] Oscillation détectée! Tu = {:.3f}s ({:.1f} ticks à 20Hz)".format(
                                tu, tu * 20))
                    else:
                        self._osc_tu = None  # oscillations instables
        self._osc_prev_sign = current_sign

    # ------------------------------------------------------------------
    #  Debug & tuning
    # ------------------------------------------------------------------

    def get_debug_info(self):
        return {
            "error": self._last_error,
            "correction": self._last_correction,
            "ir_bottom_left": self._last_ir_left,
            "ir_bottom_right": self._last_ir_right,
            "left_speed": self._base_speed + self._last_correction,
            "right_speed": self._base_speed - self._last_correction,
            "ir_sum": self._last_ir_sum,
            "ir_offset": self._ir_offset,
            "calibrating": self._calibrating,
            "line_lost": self._line_lost,
            "integral": self._integral,
            "oscillation_Tu": self._osc_tu,
            "in_gap": self._in_gap,
            "heading_hold_active": self._heading_hold_active,
            "desired_heading": self._desired_heading,
        }

    def get_params(self):
        return {
            "base_speed": self._base_speed,
            "kp": self._kp,
            "ki": self._ki,
            "kd": self._kd,
            "max_correction": self._max_correction,
            "line_lost_threshold": self._line_lost_threshold,
            "ir_offset": self._ir_offset,
            "calibration_samples": self._calibration_samples,
            "gap_threshold": self._gap_threshold,
            "heading_kp": self._heading_kp,
            "heading_max_correction": self._heading_max_correction,
        }

    def trigger_calibration(self):
        """Relance l'auto-calibration IR (appelable depuis l'UI)."""
        self._calibrating = True
        self._calibration_buffer = []
        self._integral = 0.0
        self._prev_error = 0.0
        print("[PID_IR] Recalibration IR lancée ({} échantillons)...".format(self._calibration_samples))

    def update_params(self, **kwargs):
        if "base_speed" in kwargs:
            self._base_speed = int(kwargs["base_speed"])
        if "kp" in kwargs:
            self._kp = float(kwargs["kp"])
        if "ki" in kwargs:
            self._ki = float(kwargs["ki"])
        if "kd" in kwargs:
            self._kd = float(kwargs["kd"])
        if "max_correction" in kwargs:
            self._max_correction = int(kwargs["max_correction"])
        if "line_lost_threshold" in kwargs:
            self._line_lost_threshold = float(kwargs["line_lost_threshold"])
        if "ir_offset" in kwargs:
            self._ir_offset = float(kwargs["ir_offset"])
        if "calibration_samples" in kwargs:
            self._calibration_samples = int(kwargs["calibration_samples"])
        if "gap_threshold" in kwargs:
            self._gap_threshold = float(kwargs["gap_threshold"])
        if "heading_kp" in kwargs:
            self._heading_kp = float(kwargs["heading_kp"])
        if "heading_max_correction" in kwargs:
            self._heading_max_correction = float(kwargs["heading_max_correction"])
