#!/usr/bin/env python
# -*- coding: utf-8 -*-
# camera/camera_base.py
# ------------------
# Interface abstraite pour une caméra.
# Toute caméra (Pi, Zumi, USB, simulation)

from abc import ABC, abstractmethod
import numpy as np

class CameraBase(ABC):
    """
    Interface abstraite pour une caméra.
    Toute caméra (Pi, Zumi, USB, simulation)
    doit implémenter cette interface.
    """

    @abstractmethod
    def start_camera(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def capture(self) -> np.ndarray:
        """
        Retourne une image BGR (OpenCV compatible)
        """
        pass

    @abstractmethod
    def reconfigure(self, width: int, height: int):
        """
        Reconfigure la caméra à la résolution demandée.

        L'implémentation gère le cycle de vie complet (fermeture,
        recréation et reconfiguration) en interne. L'appelant n'a pas
        besoin d'appeler close() avant ni start_camera() après.

        :param width:  Largeur en pixels.
        :param height: Hauteur en pixels.
        """
        pass
