#!/usr/bin/env python
# -*- coding: utf-8 -*-
# detector_base.py
# ------------------
# ce module défini la classe de base pour les détecteurs de vision
# il servira de base pour l'implémentation du CNN

from abc import ABC, abstractmethod

class BaseDetector(ABC):
    @abstractmethod
    def process(self, frame):
        """
        Analyse une image et retourne un résultat.
        """
        pass

    @abstractmethod
    def atach_capture_dir(self, capture_dir):
        """
        Attache le dossier de capture d'images au détecteur.
        """
        pass