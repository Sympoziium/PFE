#!/usr/bin/env python
# -*- coding: utf-8 -*-
# motor_driver.py
# ------------------
"""Driver d'exécution des commandes moteur.

Traduit un MotorCommand standardisé en appels concrets au SDK Zumi
via l'abstraction RobotBase.

Fonctions Zumi SDK utilisées :
    - zumi.control_motors(right, left)   ⚠️ ordre SDK = (right, left)
    - zumi.stop()
    - zumi.turn_left(angle) / zumi.turn_right(angle)
    - zumi.forward_step(speed, desired_angle)
    - Gestion des LEDs (clignotants, freins, phares)
"""

from core.control.IO_drivers.motor_command import MotorCommand, CommandType


class MotorDriver:
    """Exécute des MotorCommand sur le robot physique.

    Centralise toute la logique d'interaction avec les moteurs :
    appels SDK, gestion des LEDs, clamping des vitesses, etc.

    Args:
        robot: Instance de RobotBase (ex. RobotZumi).
    """

    def __init__(self, robot):
        self.robot = robot
        self._last_command = MotorCommand.stop()

    def execute(self, command):
        """Exécute une commande moteur sur le robot.

        Args:
            command (MotorCommand): Commande à exécuter.
        """
        self._last_command = command

        if command.command_type == CommandType.STOP:
            self.robot.stop()

        elif command.command_type == CommandType.SPEED:
            self.robot.control_motors(command.left_speed, command.right_speed)

        elif command.command_type == CommandType.TURN:
            if command.angle != 0:
                self.robot.turn(command.angle)

        elif command.command_type == CommandType.FORWARD_STEP:
            if hasattr(self.robot, 'forward_step'):
                self.robot.forward_step(command.speed, command.desired_angle)
            else:
                # Fallback : avancer avec les deux moteurs à la même vitesse
                self.robot.control_motors(command.speed, command.speed)

    @property
    def last_command(self):
        """MotorCommand : Dernière commande exécutée."""
        return self._last_command
