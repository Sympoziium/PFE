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
