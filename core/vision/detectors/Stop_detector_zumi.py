#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_zumi.py
# ------------------
# Ce module implémente les fonctions spécifiques pour le détecteur de panneau stop
# pour le robot Zumi en utilisant la bibliothèque Zumi. Celle-ci étant préoptimisée
# pourra servir de référence pour d'autres implémentations.

from .detector_base import BaseDetector
from zumi.util.vision import Vision

class StopDetector(BaseDetector):

    def __init__(self, scale_factor=1.05, min_neighbors=8, min_size=(40, 40)):
        """Initialise le détecteur de panneau stop pour le Zumi.
        Args:
            scale_factor (float): facteur d'échelle pour la détection.
            min_neighbors (int): nombre minimum de voisins pour valider une détection.
            min_size (tuple): taille minimale du panneau à détecter.
        """
        self.zumi_vision = Vision()  # instance de vision du robot Zumi
        self.scaleFactor = scale_factor
        self.minNeighbors = min_neighbors
        self.minSize = min_size
        self.name = "StopDetectorZumi"
        
    def process(self, frame):
        """Analyse une image pour détecter un panneau stop.
        Args:
            frame: image à analyser (format compatible avec la bibliothèque Zumi).
        Returns:
            dict: résultat de la détection (nom du détecteur, état de détection, boîte englobante).
        """
        # Implémentation spécifique pour le Zumi
        
        detection = self.zumi_vision.find_stop_sign(frame, scale_factor=self.scaleFactor, min_neighbors=self.minNeighbors, min_size=self.minSize)
        stop_detected = False
        Coordonées = None
        Taille = None

        if detection is None:
            print("Aucun panneau stop détecté.")
            stop_detected = False
        else:
            stop_detected = True
            Coordonées = (detection["x"], detection["y"])
            Taille = (detection["width"], detection["height"])
        
        resultats = {
                "Detector": self.name,
                "Object detected": stop_detected,
                "Object coordinates": Coordonées,
                "Object size": Taille,
            }
        
        return resultats
