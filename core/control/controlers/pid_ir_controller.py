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

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


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
        kp=0.12,
        ki=0.0,
        kd=-0.58,
        max_correction=8,
        line_lost_threshold=80.0,
        ir_offset=0.0,
        calibration_samples=10,
    ):
        self._base_speed = base_speed
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._max_correction = max_correction
        self._line_lost_threshold = line_lost_threshold
        self._ir_offset = ir_offset
        self._calibration_samples = calibration_samples

        # État PID
        self._integral = 0.0
        self._prev_error = 0.0

        # État calibration
        self._calibrating = False
        self._calibration_buffer = []

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
        # Lancer l'auto-calibration sur les N premiers ticks
        self._calibrating = True
        self._calibration_buffer = []
        print("[PID_IR] Démarré (base_speed={}, Kp={}, Ki={}, Kd={}, ir_offset={})".format(
            self._base_speed, self._kp, self._ki, self._kd, self._ir_offset
        ))
        print("[PID_IR] Auto-calibration IR sur {} échantillons...".format(self._calibration_samples))

    def stop(self):
        print("[PID_IR] Arrêté")

    def step(self, state):
        """Calcule la commande moteur via PID sur IR_diff.

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

        # Détection de perte de ligne
        ir_sum = (ir_bottom_left + ir_bottom_right) / 2.0
        self._last_ir_sum = ir_sum

        if ir_sum < self._line_lost_threshold:
            self._line_lost = True
            self._integral = 0.0
            return MotorCommand.stop()

        self._line_lost = False

        # PID sur l'erreur corrigée du biais capteur
        # (right - left) - offset pour que Kp positif = suit la ligne
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

        # Commande différentielle (correction > 0 → tourne à droite)
        left_speed = self._base_speed + correction
        right_speed = self._base_speed - correction

        # Clamp aux limites moteur
        left_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, left_speed))
        right_speed = max(-self.MOTOR_SPEED_MAX, min(self.MOTOR_SPEED_MAX, right_speed))

        return MotorCommand.make_speed(left_speed, right_speed)

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
