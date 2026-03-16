#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pid_line_follower.py
# ------------------
"""Contrôleur de suivi de ligne basé sur le PID.

Implémente ControllerBase en utilisant le PIDController existant comme
algorithme interne. Reçoit un SensorState, lit le line_offset, calcule
la correction PID et retourne un MotorCommand.

C'est l'exemple de référence de l'architecture standardisée :
    SensorState → PIDLineFollowerController → MotorCommand
"""

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand


class PIDLineFollowerController(ControllerBase):
    """Contrôleur PID pour le suivi de ligne.

    Utilise le PIDController existant comme service de calcul PID.
    En mode rotation, calcule un angle et retourne MotorCommand.turn().
    En mode avance, calcule les vitesses G/D et retourne MotorCommand.speed().

    Args:
        pid_controller: Instance de PIDController (algorithme PID pur).
    """

    def __init__(self, pid_controller):
        self._pid = pid_controller

    @property
    def name(self):
        return "pid_line"

    def step(self, state):
        """Calcule la commande moteur PID à partir de l'offset de ligne.

        Args:
            state (SensorState): État capteur courant.

        Returns:
            MotorCommand: STOP si ligne non détectée, TURN ou SPEED sinon.
        """
        if not state.line_detected or state.line_offset is None:
            return MotorCommand.stop()

        if self._pid.rotation_mode:
            # Mode rotation : calcule un angle et tourne
            angle = self._pid.compute_rotation_angle(state.line_offset)
            if angle is not None:
                return MotorCommand.make_turn(angle)
            return MotorCommand.stop()
        else:
            # Mode avance : calcule les vitesses gauche/droite
            left, right = self._pid.compute(state.line_offset)
            return MotorCommand.make_speed(left, right)

    def start(self):
        """Réinitialise le PID à l'activation."""
        self._pid.reset()

    def stop(self):
        """Rien à nettoyer."""

    def get_debug_info(self):
        """Retourne les infos de debug du PID sous-jacent."""
        return self._pid.get_debug_info()

    def get_params(self):
        """Retourne les paramètres réglables du PID."""
        return self._pid.get_params()

    def update_params(self, **kwargs):
        """Met à jour les paramètres du PID en runtime."""
        self._pid.update_params(**kwargs)
