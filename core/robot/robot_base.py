#!/usr/bin/env python
# -*- coding: utf-8 -*-
# robot_base.py
# ------------------
"""Interface abstraite pour un robot.

Toute implémentation de robot doit hériter de cette classe.
Les méthodes abstraites (control_motors, stop, turn) doivent être implémentées.
Les méthodes de capteurs ont des implémentations par défaut (retournent None/0)
pour permettre aux mocks de fonctionner sans modification.
"""

from abc import ABC, abstractmethod


class RobotBase(ABC):
    """Interface abstraite pour un robot."""

    # ------------------------------------------------------------------
    #  Contrôle moteur (abstraites — doivent être implémentées)
    # ------------------------------------------------------------------

    @abstractmethod
    def control_motors(self, roue_gauche_speed, roue_droite_speed):
        """Définit la vitesse des moteurs gauche et droit.

        Args:
            roue_gauche_speed: Vitesse moteur gauche [-127, 127].
            roue_droite_speed: Vitesse moteur droit [-127, 127].
        """

    @abstractmethod
    def stop(self):
        """Arrête les moteurs immédiatement."""

    @abstractmethod
    def turn(self, angle):
        """Fait tourner le robot d'un angle donné.

        Args:
            angle: Angle en degrés. Positif = gauche, négatif = droite.
        """

    # ------------------------------------------------------------------
    #  Contrôle avancé (optionnel)
    # ------------------------------------------------------------------

    def forward_step(self, speed, desired_angle):
        """Un pas en avant avec correction de cap via PID interne.

        Args:
            speed:         Vitesse de déplacement [0, 127].
            desired_angle: Cap désiré en degrés.
        """
        # Fallback : avancer en ligne droite
        self.control_motors(speed, speed)

    # ------------------------------------------------------------------
    #  Capteurs (implémentations par défaut pour compatibilité mocks)
    # ------------------------------------------------------------------

    def get_angles(self):
        """Lit les angles gyroscope/accéléromètre.

        Returns:
            list ou None: [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y,
                           Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
                          (11 valeurs) ou None si non disponible.
        """
        return None

    def get_ir_data(self):
        """Lit les 6 capteurs IR.

        Returns:
            list ou None: [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
                          valeurs 0-255, ou None si non disponible.
        """
        return None

    def get_orientation(self):
        """Retourne l'état d'orientation du robot.

        Returns:
            int: -1=inconnu, 0=chute/transition, 1=caméra en haut,
                 2=caméra en bas, 3=côté droit, 4=côté gauche,
                 5=roues au sol, 6=à l'envers, 7=accélération >1g.
        """
        return -1

    def get_battery_voltage(self):
        """Retourne la tension de la batterie en volts.

        Returns:
            float: Tension en volts (max 4.2V, min 3.0V), ou 0.0 si non disponible.
        """
        return 0.0