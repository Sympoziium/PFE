# base_detecteur.py
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
