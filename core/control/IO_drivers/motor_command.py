#!/usr/bin/env python
# -*- coding: utf-8 -*-
# motor_command.py
# ------------------
"""DTO standardisé décrivant une commande moteur.

Chaque contrôleur retourne un MotorCommand depuis sa méthode step().
Le MotorDriver se charge de traduire ces commandes en appels au SDK Zumi.
"""

from enum import Enum


class CommandType(Enum):
    """Types de commandes moteur supportées."""
    STOP = 'stop'
    SPEED = 'speed'               # Contrôle direct des vitesses gauche/droite
    TURN = 'turn'                 # Rotation sur place d'un angle donné
    FORWARD_STEP = 'forward_step' # Un pas en avant avec correction de cap


class MotorCommand:
    """Commande moteur standardisée.

    Utiliser les factory methods statiques pour créer des commandes :

        MotorCommand.stop()
        MotorCommand.speed(left=30, right=30)
        MotorCommand.turn(angle=45)
        MotorCommand.forward_step(speed=40, desired_angle=0)

    Attributes:
        command_type:   Type de commande (CommandType enum).
        left_speed:     Vitesse moteur gauche [-127, 127] (SPEED).
        right_speed:    Vitesse moteur droit [-127, 127] (SPEED).
        angle:          Angle de rotation en degrés (TURN). Positif=gauche, négatif=droite.
        speed:          Vitesse de déplacement [0, 127] (FORWARD_STEP).
        desired_angle:  Cap désiré en degrés (FORWARD_STEP) ou None.
        duration:       Durée optionnelle en secondes.
    """

    __slots__ = (
        'command_type', 'left_speed', 'right_speed',
        'angle', 'speed', 'desired_angle', 'duration',
    )

    def __init__(
        self,
        command_type=CommandType.STOP,
        left_speed=0,
        right_speed=0,
        angle=0.0,
        speed=0,
        desired_angle=None,
        duration=0.0,
    ):
        self.command_type = command_type
        self.left_speed = left_speed
        self.right_speed = right_speed
        self.angle = angle
        self.speed = speed
        self.desired_angle = desired_angle
        self.duration = duration

    # ------------------------------------------------------------------
    #  Factory methods
    # ------------------------------------------------------------------

    @staticmethod
    def stop():
        """Crée une commande d'arrêt."""
        return MotorCommand(command_type=CommandType.STOP)

    @staticmethod
    def make_speed(left, right):
        """Crée une commande de vitesse directe gauche/droite.

        Args:
            left:  Vitesse moteur gauche [-127, 127].
            right: Vitesse moteur droit [-127, 127].
        """
        return MotorCommand(
            command_type=CommandType.SPEED,
            left_speed=int(max(-127, min(127, left))),
            right_speed=int(max(-127, min(127, right))),
        )

    @staticmethod
    def make_turn(angle):
        """Crée une commande de rotation.

        Args:
            angle: Angle en degrés. Positif = gauche, négatif = droite.
        """
        return MotorCommand(command_type=CommandType.TURN, angle=float(angle))

    @staticmethod
    def make_forward_step(speed, desired_angle=None):
        """Crée une commande d'un pas en avant avec correction de cap.

        Args:
            speed:         Vitesse de déplacement [0, 127].
            desired_angle: Cap désiré en degrés (None = cap courant).
        """
        return MotorCommand(
            command_type=CommandType.FORWARD_STEP,
            speed=int(max(0, min(127, speed))),
            desired_angle=desired_angle,
        )

    def __repr__(self):
        if self.command_type == CommandType.STOP:
            return "MotorCommand(STOP)"
        elif self.command_type == CommandType.SPEED:
            return "MotorCommand(SPEED L={} R={})".format(self.left_speed, self.right_speed)
        elif self.command_type == CommandType.TURN:
            return "MotorCommand(TURN {:.1f}°)".format(self.angle)
        elif self.command_type == CommandType.FORWARD_STEP:
            return "MotorCommand(STEP spd={} ang={})".format(self.speed, self.desired_angle)
        return "MotorCommand({})".format(self.command_type)
