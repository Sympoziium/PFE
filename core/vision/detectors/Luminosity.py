#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Luminosity.py
# ------------------
# Module de detecteur ultra simple pour tester le pipeline de vision
# Il calcule la luminosite moyenne de l'image capturee

from .detector_base import BaseDetector
import numpy as np

class LuminosityDetector(BaseDetector):
    def __init__(self):
        self.name = "LuminosityDetector"

    def process(self, frame):
        """
        Calcule la luminosite moyenne de l'image.
        
        Args:
            frame (np.ndarray): Image capturee par la camera.
        
        Returns:
            dict: Dictionnaire contenant le nom du detecteur et la luminosite moyenne de l'image.
        """ 
        # Calculer la luminosite moyenne
        resultats = {
                "Detector": self.name,
                "Luminosity": float(frame.mean()),
                }

        return resultats
    
    def preprocess(self, frame):
        """
        Pretraitement de l'image si necessaire.
        
        Args:
            frame (np.ndarray): Image capturee par la camera.
        
        Returns:
            np.ndarray: Image pretraitee.
        """
        # Pour ce detecteur, aucun pretraitement n'est necessaire
        # voir si on doit convertir en niveaux de gris

        return frame