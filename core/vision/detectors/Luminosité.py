# Luminosité.py
# ------------------
# Module de détecteur ultra simple pour tester le pipeline de vision
# Il calcule la luminosité moyenne de l'image capturée

from .detector_base import BaseDetector
import numpy as np

class LuminosityDetector(BaseDetector):
    def process(self, frame):
        """
        Calcule la luminosité moyenne de l'image.
        
        Args:
            frame (np.ndarray): Image capturée par la caméra.
        
        Returns:
            dict: Dictionnaire contenant le nom du détecteur et la luminosité moyenne de l'image.
        """ 
        # Calculer la luminosité moyenne
        return {"detector": "luminosity", "value": float(frame.mean())}
    
    def preprocess(self, frame):
        """
        Prétraitement de l'image si nécessaire.
        
        Args:
            frame (np.ndarray): Image capturée par la caméra.
        
        Returns:
            np.ndarray: Image prétraitée.
        """
        # Pour ce détecteur, aucun prétraitement n'est nécessaire
        # voir si on doit convertir en niveaux de gris

        return frame