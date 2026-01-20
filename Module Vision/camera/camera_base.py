# camera/camera_base.py

from abc import ABC, abstractmethod
import numpy as np

class CameraBase(ABC):
    """
    Interface abstraite pour une caméra.
    Toute caméra (Pi, Zumi, USB, simulation)
    doit implémenter cette interface.
    """

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_frame(self) -> np.ndarray:
        """
        Retourne une image BGR (OpenCV compatible)
        """
        pass
