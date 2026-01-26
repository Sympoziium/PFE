#!/usr/bin/env python
# -*- coding: utf-8 -*-
# robot_base.py
# ------------------
# Interface abstraite pour un robot.
# Toute implémentation de robot doit hériter de cette classe.

from abc import ABC, abstractmethod

class RobotBase(ABC):
    """
    Interface abstraite pour un robot.
    Toute implémentation de robot doit hériter de cette classe.
    """

    @abstractmethod
    def control_motors(self, roue_droite_speed: float, roue_gauche_speed: float):
        """
        Définit la vitesse du moteur.
        :param speed: Vitesse entre -1.0 (arrière) et 1.0 (avant)
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Arrête le moteur.
        """
        pass