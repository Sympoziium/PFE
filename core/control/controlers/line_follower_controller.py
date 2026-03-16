#!/usr/bin/env python
# -*- coding: utf-8 -*-
# line_follower_controller.py
# ------------------
"""Contrôleur de suivi de ligne avec commutation automatique rotation/avance.

Implémente ControllerBase dans le nouveau standard d'architecture :
    SensorState → LineFollowerController → MotorCommand

Stratégie de commutation automatique basée sur l'offset courant :
  - |offset| > turn_threshold  → MotorCommand.make_turn()  (recadrage rapide)
  - |offset| <= turn_threshold → MotorCommand.make_speed() (suivi fluide via PID)

Aucun flag externe n'est nécessaire. La logique de mode est entièrement
encapsulée ici et décidée dynamiquement à chaque step().

REMARQUE:
la détection de ligne par vision fonctionne bien mais on a un bottleneck
que a une certaine distance/orientation la ligne n'est plus visible.
il faudrais intégrer la lecture des capteurs IR du bas pour faire le suivit primaire
et utiliser la vision comme système d'entisipation, il permettrait de corriger 
les dérives du suivi IR et de recadrer la ligne en cas de virage serré ou de décalage important.

"""

from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand
from core.control.legacy.line_following_pid import PIDController


class LineFollowerController(ControllerBase):
    """Contrôleur de suivi de ligne avec commutation automatique.

    Deux modes, sélectionnés automatiquement à chaque step() :

    **Mode rotation** (|offset| > turn_threshold) :
        Effectue une petite rotation proportionnelle à l'offset pour recadrer
        rapidement la ligne. Utilisé pour les virages serrés ou les grands
        décentrements. Bloquant (~0.5 s le temps que le Zumi pivote).

    **Mode avance** (|offset| <= turn_threshold) :
        Avance avec correction différentielle gauche/droite calculée par un PID
        sur l'offset de ligne. Fluide pour les lignes droites et courbes douces.

    Args:
        base_speed (int): Vitesse de base en mode avance [0-127].
        turn_threshold (int): Offset pixel à partir duquel on bascule en rotation.
        max_turn_angle (float): Angle maximal d'une correction de rotation (degrés).
        turn_angle_scale (float): Pixels d'offset → degrés de rotation (gain proportionnel).
        kp (float): Gain proportionnel PID pour le mode avance.
        ki (float): Gain intégral PID pour le mode avance.
        kd (float): Gain dérivé PID pour le mode avance.
        max_correction (int): Correction différentielle maximale en mode avance.
    """

    def __init__(
        self,
        base_speed=20,
        turn_threshold=60,
        max_turn_angle=30.0,
        turn_angle_scale=0.25,
        kp=0.2,
        ki=0.0,
        kd=0.05,
        max_correction=25,
    ):
        self._base_speed = base_speed
        self._turn_threshold = turn_threshold
        self._max_turn_angle = max_turn_angle
        self._turn_angle_scale = turn_angle_scale

        # PID interne utilisé UNIQUEMENT en mode avance (rotation_mode=False)
        # Le pid_controller.py reste l'algorithme, on lui retire la responsabilité
        # de décider du mode — c'est notre job ici.
        self._pid = PIDController(
            kp=kp,
            ki=ki,
            kd=kd,
            base_speed=base_speed,
            max_correction=max_correction,
            rotation_mode=False,  # fixé à False : on gère la rotation nous-mêmes
        )

        # Pour le debug
        self._last_mode = "idle"
        self._last_offset = None

    # ------------------------------------------------------------------
    #  Interface ControllerBase
    # ------------------------------------------------------------------

    @property
    def name(self):
        return "line_follower"

    def start(self):
        """Réinitialise le PID d'avance à l'activation."""
        self._pid.reset()
        self._last_mode = "idle"
        self._last_offset = None

    def stop(self):
        pass

    def step(self, state):
        """Calcule la commande moteur à partir de l'état capteur.

        Commutation automatique :
          - Ligne absente                → STOP
          - |offset| > turn_threshold   → TURN  (correction angulaire)
          - |offset| <= turn_threshold  → SPEED (avance différentielle PID)

        Args:
            state (SensorState): État capteur courant.

        Returns:
            MotorCommand: Commande à exécuter ce tick.
        """
        if not state.line_detected or state.line_offset is None:
            self._last_mode = "stop"
            return MotorCommand.stop()

        offset = state.line_offset
        self._last_offset = offset

        if abs(offset) > self._turn_threshold:
            return self._mode_rotation(offset)
        else:
            return self._mode_avance(offset)

    # ------------------------------------------------------------------
    #  Modes internes
    # ------------------------------------------------------------------

    def _mode_rotation(self, offset):
        """Correction angulaire pour les grands décalages.

        L'offset négatif = ligne à gauche → angle positif (tourner à gauche).
        L'offset positif = ligne à droite → angle négatif (tourner à droite).
        Le PID est réinitialisé pour éviter une intégrale obsolète quand on
        reprend le mode avance juste après.
        """
        angle = -offset * self._turn_angle_scale
        angle = max(-self._max_turn_angle, min(self._max_turn_angle, angle))
        self._pid.reset()  # flush l'intégrale avant de reprendre l'avance
        self._last_mode = "rotation"
        return MotorCommand.make_turn(angle)

    def _mode_avance(self, offset):
        """Avance différentielle avec correction PID sur l'offset de ligne."""
        left, right = self._pid.compute(offset)
        self._last_mode = "avance"
        return MotorCommand.make_speed(left, right)

    # ------------------------------------------------------------------
    #  Tuning & debug
    # ------------------------------------------------------------------

    def get_debug_info(self):
        """Retourne les informations de debug pour l'interface."""
        info = self._pid.get_debug_info()
        info["mode"] = self._last_mode
        info["last_offset"] = self._last_offset
        info["turn_threshold"] = self._turn_threshold
        return info

    def get_params(self):
        """Retourne tous les paramètres réglables en runtime."""
        return {
            "base_speed": self._base_speed,
            "turn_threshold": self._turn_threshold,
            "max_turn_angle": self._max_turn_angle,
            "turn_angle_scale": self._turn_angle_scale,
            **self._pid.get_params(),
        }

    def update_params(self, **kwargs):
        """Met à jour les paramètres en runtime (depuis l'interface Flask).

        Paramètres propres au contrôleur :
            base_speed, turn_threshold, max_turn_angle, turn_angle_scale

        Le reste est transmis au PID interne (kp, ki, kd, max_correction…).
        """
        if "base_speed" in kwargs:
            self._base_speed = kwargs.pop("base_speed")
            self._pid.update_params(base_speed=self._base_speed)
        if "turn_threshold" in kwargs:
            self._turn_threshold = kwargs.pop("turn_threshold")
        if "max_turn_angle" in kwargs:
            self._max_turn_angle = kwargs.pop("max_turn_angle")
        if "turn_angle_scale" in kwargs:
            self._turn_angle_scale = kwargs.pop("turn_angle_scale")
        # Tout le reste part au PID
        if kwargs:
            self._pid.update_params(**kwargs)
