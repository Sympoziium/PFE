#!/usr/bin/env python
# -*- coding: utf-8 -*-
# manual_controller.py
# ------------------
"""Contrôleur manuel pour le pilotage via l'interface web (WASD + D-pad).

    Supporte les actions composées (throttle + steering) pour des mouvements fluides:
    - W/S (throttle): avancer/reculer
    - A/D (steering): tourner gauche/droite
    - W+A, W+D: virages en arc (différentiel blend)
    - A/D seuls: rotation sur place (avec PWM logiciel pour vitesse réduite)

    Intègre un Watchdog: si aucune commande n'est reçue pendant X ms,
    les moteurs sont arrêtés.

    La méthode statique compute_speeds() est la SOURCE UNIQUE DE VÉRITÉ
    pour le calcul des vitesses, utilisée par step() ET par le sampling.
"""

import time
from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand

# Mapping des actions simples (D-pad) vers throttle/steering
_ACTION_MAP = {
    "forward":  ( 1,  0),
    "reverse":  (-1,  0),
    "left":     ( 0, -1),
    "right":    ( 0,  1),
    "stop":     ( 0,  0),
}


class ManualController(ControllerBase):
    def __init__(self, default_speed=20, watchdog_timeout=0.3):
        self._name = "manual_controller"
        self.default_speed = default_speed
        self.watchdog_timeout = watchdog_timeout

        # --- État composé (throttle/steering) ---
        self._throttle = 0    # -1 (recul), 0 (neutre), +1 (avance)
        self._steering = 0    # -1 (gauche), 0 (neutre), +1 (droite)
        self._last_action_time = time.time()

        # --- Paramètres de virage ---
        self.turn_speed = 1           # Vitesse rotation sur place (minimum hardware)
        self.steering_ratio = 0.5     # Sévérité du virage en arc (0=droit, 1=roue intérieure arrêtée)

        # --- PWM logiciel pour rotations sur place ---
        # Conservé car speed=1 est le minimum hardware et reste trop rapide.
        # Appliqué UNIQUEMENT dans step() (moteur), PAS dans compute_speeds() (sampling).
        self._turn_tick = 0
        self.turn_duty_on  = 2   # ticks actifs
        self.turn_duty_off = 1   # ticks inactifs → vitesse effective 2/3

        # --- Flag de transition virage→droit pour reset gyro ---
        self._was_steering = False    # True si le tick précédent avait steering != 0
        self._needs_gyro_reset = False  # Flag lu par le ControlManager/serveur

    @property
    def name(self):
        return self._name

    # ------------------------------------------------------------------
    #  Source unique de vérité pour le calcul des vitesses
    # ------------------------------------------------------------------

    @staticmethod
    def compute_speeds(throttle, steering, drive_speed, turn_speed, steering_ratio=0.5):
        """Calcule (left_speed, right_speed) depuis un état throttle+steering.

        Cette méthode est la source unique de vérité pour le calcul des vitesses.
        Elle est utilisée par step() (exécution moteur) ET par le sampling
        (labels d'entraînement), garantissant la cohérence des données.

        Args:
            throttle:       -1 (recul), 0 (neutre), +1 (avance)
            steering:       -1 (gauche), 0 (neutre), +1 (droite)
            drive_speed:    Vitesse de conduite (avance/recul)
            turn_speed:     Vitesse de rotation sur place
            steering_ratio: Ratio de ralentissement de la roue intérieure en arc (0-1)

        Returns:
            tuple: (left_speed, right_speed)
        """
        if throttle == 0 and steering == 0:
            return (0, 0)

        # Rotation sur place (A/D seuls, pas de throttle)
        if throttle == 0:
            return (-steering * turn_speed, steering * turn_speed)

        # Ligne droite (pas de steering)
        base = throttle * drive_speed
        if steering == 0:
            return (base, base)

        # Virage en arc: la roue intérieure ralentit selon steering_ratio
        inner = base * (1.0 - steering_ratio)
        outer = base
        if steering < 0:  # arc gauche → roue gauche = intérieure
            return (inner, outer)
        else:              # arc droit → roue droite = intérieure
            return (outer, inner)

    # ------------------------------------------------------------------
    #  Interface serveur web
    # ------------------------------------------------------------------

    def set_compound_action(self, throttle, steering, drive_speed=None, turn_speed=None):
        """Met à jour l'intention de mouvement composée (WASD).

        Args:
            throttle: -1, 0, +1
            steering: -1, 0, +1
            drive_speed: Vitesse de conduite (optionnel)
            turn_speed: Vitesse de rotation (optionnel)
        """
        self._throttle = throttle
        self._steering = steering
        self._last_action_time = time.time()
        if drive_speed is not None:
            self.default_speed = drive_speed
        if turn_speed is not None:
            self.turn_speed = turn_speed

    def set_action(self, action, speed=None):
        """Met à jour l'intention de mouvement depuis le D-pad (rétrocompatibilité).

        Mappe les actions simples vers throttle/steering composé.
        """
        throttle, steering = _ACTION_MAP.get(action, (0, 0))
        self._throttle = throttle
        self._steering = steering
        self._last_action_time = time.time()
        if speed is not None:
            self.default_speed = speed

    # ------------------------------------------------------------------
    #  Cycle de vie du contrôleur
    # ------------------------------------------------------------------

    def start(self):
        """Appelé quand l'utilisateur prend le contrôle manuel."""
        self._throttle = 0
        self._steering = 0
        self._last_action_time = time.time()
        self._was_steering = False
        self._needs_gyro_reset = False
        self._turn_tick = 0

    def stop(self):
        self._throttle = 0
        self._steering = 0

    # ------------------------------------------------------------------
    #  Boucle de contrôle (appelé à chaque tick ~30Hz)
    # ------------------------------------------------------------------

    def step(self, state):
        """Calcule la commande moteur à partir de l'état throttle+steering.

        Applique:
        - Watchdog timeout
        - forward_step avec gyro PID pour la ligne droite
        - PWM logiciel pour les rotations sur place
        - Vitesses différentielles pour les arcs et la marche arrière
        """
        # 1. Watchdog: arrêt si pas de commande récente
        if time.time() - self._last_action_time > self.watchdog_timeout:
            self._throttle = 0
            self._steering = 0

        # 2. Détection de transition virage → ligne droite pour reset gyro
        currently_steering = (self._steering != 0)
        going_straight_forward = (self._throttle > 0 and self._steering == 0)

        if self._was_steering and going_straight_forward:
            self._needs_gyro_reset = True
        self._was_steering = currently_steering

        # 3. Ligne droite avant → forward_step avec correction gyro PID interne Zumi
        #    forward_step() est conçu pour être appelé en boucle (30Hz = notre cas).
        #    desired_angle=0 = maintenir le cap depuis le dernier reset gyro.
        if going_straight_forward:
            return MotorCommand.make_forward_step(self.default_speed, desired_angle=0)

        # 4. Rotation sur place avec PWM logiciel (A/D seuls)
        #    Le PWM réduit la vitesse effective car speed=1 est déjà le minimum hardware.
        #    Note: compute_speeds() retourne les vitesses intentionnelles (pour le sampling),
        #    le PWM est appliqué ICI uniquement (pour l'exécution moteur).
        if self._throttle == 0 and self._steering != 0:
            self._turn_tick += 1
            active = (self._turn_tick % (self.turn_duty_on + self.turn_duty_off)) < self.turn_duty_on
            if not active:
                return MotorCommand.stop()
            return MotorCommand.make_speed(
                -self._steering * self.turn_speed,
                self._steering * self.turn_speed
            )

        # 5. Tous les autres cas (arcs W+A/W+D, recul S, recul+arc S+A/S+D)
        left, right = self.compute_speeds(
            self._throttle, self._steering,
            self.default_speed, self.turn_speed, self.steering_ratio
        )

        if left == 0 and right == 0:
            return MotorCommand.stop()
        return MotorCommand.make_speed(left, right)

    # ------------------------------------------------------------------
    #  Flag gyro (lu par le serveur/ControlManager)
    # ------------------------------------------------------------------

    def consume_gyro_reset_flag(self):
        """Retourne True si un reset gyro est nécessaire, puis remet le flag à False.

        Appelé par le ControlManager ou le serveur avant d'exécuter la commande.
        """
        if self._needs_gyro_reset:
            self._needs_gyro_reset = False
            return True
        return False

    # ------------------------------------------------------------------
    #  Debug et paramètres
    # ------------------------------------------------------------------

    def get_debug_info(self):
        return {
            "throttle": self._throttle,
            "steering": self._steering,
            "timeout_warning": (time.time() - self._last_action_time > self.watchdog_timeout),
        }

    def get_params(self):
        return {
            "default_speed": self.default_speed,
            "turn_speed": self.turn_speed,
            "steering_ratio": self.steering_ratio,
            "turn_duty_on": self.turn_duty_on,
            "turn_duty_off": self.turn_duty_off,
        }

    def update_params(self, **kwargs):
        if "default_speed" in kwargs:
            self.default_speed = kwargs["default_speed"]
        if "turn_speed" in kwargs:
            self.turn_speed = kwargs["turn_speed"]
        if "steering_ratio" in kwargs:
            self.steering_ratio = float(kwargs["steering_ratio"])
        if "turn_duty_on" in kwargs:
            self.turn_duty_on = kwargs["turn_duty_on"]
        if "turn_duty_off" in kwargs:
            self.turn_duty_off = kwargs["turn_duty_off"]
