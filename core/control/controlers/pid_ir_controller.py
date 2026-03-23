#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pid_ir_controller.py
# ------------------
"""Contrôleur PID de suivi de ligne basé sur les capteurs IR bottom.

Implémente ControllerBase. Utilise la différence entre IR_bottom_left et
IR_bottom_right comme signal d'erreur pour un PID classique.

Signal d'erreur :
    error = IR_bottom_left - IR_bottom_right
    > 0 : surface plus claire à gauche → ligne à droite → tourner à droite
    < 0 : surface plus claire à droite → ligne à gauche → tourner à gauche

Commande différentielle :
    left_speed  = base_speed + correction
    right_speed = base_speed - correction

Détection de perte de ligne :
    Si IR_sum (moyenne des deux IR bottom) dépasse un seuil, les deux capteurs
    voient une surface claire → la ligne est perdue → arrêt.
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
        line_lost_threshold (float): Seuil IR_sum au-dessus duquel
            la ligne est considérée perdue (les deux capteurs voient clair).
    """

    MOTOR_SPEED_MAX = 50

    def __init__(
        self,
        base_speed=25,
        kp=0.15,
        ki=0.0,
        kd=0.05,
        max_correction=30,
        line_lost_threshold=220.0,
    ):
        self._base_speed = base_speed
        self._kp = kp
        self._ki = ki
        self._kd = kd
        self._max_correction = max_correction
        self._line_lost_threshold = line_lost_threshold

        # État PID
        self._integral = 0.0
        self._prev_error = 0.0

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
        """Réinitialise l'état PID."""
        self._integral = 0.0
        self._prev_error = 0.0
        self._line_lost = False
        print("[PID_IR] Démarré (base_speed={}, Kp={}, Ki={}, Kd={})".format(
            self._base_speed, self._kp, self._ki, self._kd
        ))

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

        # Détection de perte de ligne
        ir_sum = (ir_bottom_left + ir_bottom_right) / 2.0
        self._last_ir_sum = ir_sum

        if ir_sum > self._line_lost_threshold:
            self._line_lost = True
            self._integral = 0.0
            return MotorCommand.stop()
        
        self._line_lost = False

        # PID sur l'erreur
        error = float(ir_bottom_left - ir_bottom_right)
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

        # Commande différentielle
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
            "left_speed":self._base_speed + self._last_correction,
            "right_speed":self._base_speed - self._last_correction,
            "ir_sum": self._last_ir_sum,
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
        }

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
