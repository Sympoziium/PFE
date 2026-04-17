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

    Correction de cap: un PID léger non-bloquant utilise le gyroscope (Rot_z)
    pour maintenir le cap en ligne droite. S'active automatiquement quand
    throttle > 0 et steering == 0.

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

# Index du cap (heading) dans state.gyro_angles
# gyro_angles = [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y, Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt]
# Gyro_z (index 2) = angle yaw intégré du GYROSCOPE — suit les rotations horizontales.
# Rot_z (index 9) = rotation Z de l'ACCÉLÉROMÈTRE — insensible au yaw sur surface plane.
_HEADING_INDEX = 2  # Gyro_z = heading intégré en degrés


class ManualController(ControllerBase):
    def __init__(self, default_speed=14, watchdog_timeout=0.3):
        self._name = "manual_controller"
        self.default_speed = default_speed
        self.watchdog_timeout = watchdog_timeout

        # --- État composé (throttle/steering) ---
        self._throttle = 0    # -1 (recul), 0 (neutre), +1 (avance)
        self._steering = 0    # -1 (gauche), 0 (neutre), +1 (droite)
        self._last_action_time = time.time()

        # --- Paramètres de virage ---
        self.turn_speed = 1           # Vitesse rotation sur place (minimum hardware)
        self.steering_ratio = 0.95     # Sévérité du virage en arc (0=droit, 1=roue intérieure arrêtée)

        # --- PWM logiciel pour rotations sur place ---
        # Conservé car speed=1 est le minimum hardware et reste trop rapide.
        # Appliqué UNIQUEMENT dans step() (moteur), PAS dans compute_speeds() (sampling).
        self._turn_tick = 0
        self.turn_duty_on  = 2   # ticks actifs
        self.turn_duty_off = 1   # ticks inactifs → vitesse effective 2/3

        # --- PID de cap léger (correction de dérive en ligne droite) ---
        self._heading_hold_active = False
        self._desired_heading = 0.0
        self.heading_kp = 2.1         # Gain proportionnel (tunable via UI)
        self.heading_max_correction = 9  # Correction max en unités de vitesse

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
        # steering=-1 (gauche): left=-ts, right=+ts → roue gauche recule, droite avance → tourne à gauche
        if throttle == 0:
            return (steering * turn_speed, -steering * turn_speed)

        # Ligne droite (pas de steering)
        base = throttle * drive_speed
        if steering == 0:
            return (base, base)

        # Virage en arc: différentiel symétrique autour de la vitesse de base
        # La roue intérieure ralentit ET la roue extérieure accélère.
        # Cela garantit un différentiel suffisant même avec des moteurs asymétriques.
        half_diff = base * steering_ratio
        inner = base - half_diff
        outer = base + half_diff
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
        self._heading_hold_active = False
        self._turn_tick = 0

    def stop(self):
        self._throttle = 0
        self._steering = 0
        self._heading_hold_active = False

    # ------------------------------------------------------------------
    #  Correction de cap (PID léger non-bloquant)
    # ------------------------------------------------------------------

    def _get_heading(self, state):
        """Extrait le cap intégré (Rot_z) depuis l'état capteur.

        Returns:
            float: cap en degrés, ou None si indisponible.
        """
        if state and state.gyro_angles and len(state.gyro_angles) > _HEADING_INDEX:
            return float(state.gyro_angles[_HEADING_INDEX])
        return None

    def apply_heading_correction(self, state, base_left, base_right):
        """Applique une correction de cap proportionnelle aux vitesses de base.

        Méthode publique — utilisable par d'autres contrôleurs ou par
        l'override WASD pour maintenir le cap en ligne droite.

        Quand on commence à avancer droit, on capture le cap courant comme
        référence. À chaque tick, on calcule l'erreur et on ajuste les
        vitesses des roues pour maintenir le cap.

        Args:
            state: SensorState avec gyro_angles
            base_left: vitesse gauche avant correction
            base_right: vitesse droite avant correction

        Returns:
            tuple: (left_speed, right_speed) après correction
        """
        heading = self._get_heading(state)
        if heading is None:
            return (base_left, base_right)

        # Capture du cap de référence au début du mouvement droit
        if not self._heading_hold_active:
            self._desired_heading = heading
            self._heading_hold_active = True
            return (base_left, base_right)  # Pas de correction au premier tick

        # Calcul de l'erreur et correction proportionnelle
        # Convention Zumi: tourner à gauche = Gyro_z AUGMENTE (positif)
        # Si le robot dérive à gauche: heading > desired → error négatif
        # On veut: ralentir la roue droite (trop forte) → correction négative sur right
        # Donc: error = heading - desired (pas l'inverse!)
        error = heading - self._desired_heading
        correction = error * self.heading_kp
        correction = max(-self.heading_max_correction, min(self.heading_max_correction, correction))

        # correction > 0 quand le robot a dérivé à gauche:
        #   left += correction  → booste la roue faible (gauche)
        #   right -= correction → freine la roue forte (droite)
        return (base_left + correction, base_right - correction)

    # ------------------------------------------------------------------
    #  Boucle de contrôle (appelé à chaque tick ~30Hz)
    # ------------------------------------------------------------------

    def step(self, state):
        """Calcule la commande moteur à partir de l'état throttle+steering.

        Applique:
        - Watchdog timeout
        - Correction de cap PID pour la ligne droite (avant et arrière)
        - PWM logiciel pour les rotations sur place
        - Vitesses différentielles pour les arcs
        """
        # 1. Watchdog: arrêt si pas de commande récente
        if time.time() - self._last_action_time > self.watchdog_timeout:
            self._throttle = 0
            self._steering = 0

        # 2. Désactiver le heading hold si on ne va plus tout droit
        if self._steering != 0 or self._throttle == 0:
            self._heading_hold_active = False

        # 3. Ligne droite (avant ou arrière) → correction de cap PID
        if self._throttle != 0 and self._steering == 0:
            base_left, base_right = self.compute_speeds(
                self._throttle, 0,
                self.default_speed, self.turn_speed, self.steering_ratio
            )
            left, right = self.apply_heading_correction(state, base_left, base_right)
            return MotorCommand.make_speed(left, right)

        # 4. Rotation sur place avec PWM logiciel (A/D seuls)
        if self._throttle == 0 and self._steering != 0:
            self._turn_tick += 1
            active = (self._turn_tick % (self.turn_duty_on + self.turn_duty_off)) < self.turn_duty_on
            if not active:
                return MotorCommand.stop()
            return MotorCommand.make_speed(
                self._steering * self.turn_speed,
                -self._steering * self.turn_speed
            )

        # 5. Tous les autres cas (arcs W+A/W+D, stop)
        left, right = self.compute_speeds(
            self._throttle, self._steering,
            self.default_speed, self.turn_speed, self.steering_ratio
        )

        if left == 0 and right == 0:
            return MotorCommand.stop()
        return MotorCommand.make_speed(left, right)

    # ------------------------------------------------------------------
    #  Debug et paramètres
    # ------------------------------------------------------------------

    def get_debug_info(self):
        return {
            "throttle": self._throttle,
            "steering": self._steering,
            "heading_hold": self._heading_hold_active,
            "desired_heading": self._desired_heading if self._heading_hold_active else None,
            "timeout_warning": (time.time() - self._last_action_time > self.watchdog_timeout),
        }

    def get_params(self):
        return {
            "default_speed": self.default_speed,
            "turn_speed": self.turn_speed,
            "steering_ratio": self.steering_ratio,
            "heading_kp": self.heading_kp,
            "heading_max_correction": self.heading_max_correction,
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
        if "heading_kp" in kwargs:
            self.heading_kp = float(kwargs["heading_kp"])
        if "heading_max_correction" in kwargs:
            self.heading_max_correction = float(kwargs["heading_max_correction"])
        if "turn_duty_on" in kwargs:
            self.turn_duty_on = kwargs["turn_duty_on"]
        if "turn_duty_off" in kwargs:
            self.turn_duty_off = kwargs["turn_duty_off"]
