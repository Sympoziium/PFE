#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ml_controller.py
# ------------------
"""Contrôleur propulsé par un modèle de Machine Learning (MLP).

Implémente ControllerBase. Utilise le VisionAdapter pour transformer
le SensorState en vecteur, passe ce vecteur à un modèle d'inférence (TFLite),
et convertit la sortie en MotorCommand.
"""

import numpy as np
from core.control.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand

class MLController(ControllerBase):
    def __init__(self, vision_adapter, model_path=None):
        """
        Args:
            vision_adapter (VisionAdapter): Instance de l'adaptateur pour vectoriser l'état.
            model_path (str): Chemin vers le modèle TFLite (optionnel pour l'instant).
        """
        self.vision_adapter = vision_adapter
        self.model_path = model_path
        self._model = None
        
        if self.model_path:
            self._load_model()
            
    def _load_model(self):
        """Charge le modèle (ex: TensorFlow Lite). (Espace réservé)"""
        # Exemple:
        # import tflite_runtime.interpreter as tflite
        # self._model = tflite.Interpreter(model_path=self.model_path)
        # self._model.allocate_tensors()
        '''TODO: Implémenter le chargement du modèle TFLite'''
        pass

    @property
    def name(self):
        return "ml_controller"

    def step(self, state):
        """Calcule la commande moteur via le modèle MLP.

        Args:
            state (SensorState): État courant des capteurs.

        Returns:
            MotorCommand: Commande moteur calculée.
        """
        # 1. Vectoriser l'état via la méthode corrigée
        input_vector = state.to_vector(self.vision_adapter)
        
        # 2. Inférence dans le modèle
        if self._model is not None:
            # TODO: Implémenter l'inférence réelle
            left_speed, right_speed = 0, 0
        else:
            # Fallback simple si pas de modèle actif (ex: arrêt)
            left_speed, right_speed = 0, 0
            
        # 3. Retourner la commande
        return MotorCommand.make_speed(left_speed, right_speed)
        
    def start(self):
        print(f"[MLController] Démarré.")

    def stop(self):
        print(f"[MLController] Arrêté.")