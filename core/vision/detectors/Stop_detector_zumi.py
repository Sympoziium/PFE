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

        detection = self.zumi_vision.find_stop_sign(
            frame,
            scale_factor=self.scaleFactor,
            min_neighbors=self.minNeighbors,
            min_size=self.minSize,
        )

        # Normaliser la sortie de la bibliothèque (liste, tuple, dict, etc.)
        coords, size = self._normalize_detection(detection)

        stop_detected = coords is not None and size is not None

        if stop_detected:
            print("Detection : {}".format(detection))
        else:
            print("Aucun panneau stop détecté.")

        resultats = {
            "Detector": self.name,
            "Object detected": stop_detected,
            "Object coordinates": coords,
            "Object size": size,
        }

        return resultats

    def _normalize_detection(self, detection):
        """Convertit la sortie de `find_stop_sign` en (coords, size).

        Cette fonction gère plusieurs formats possibles:
        - None ou liste/tuple vide -> (None, None)
        - Tuple/list de 4 nombres [x, y, w, h] -> ((x, y), (w, h))
        - Liste de rectangles -> sélectionne le plus grand (si possible)
        - Dictionnaire avec clés usuelles ('x','y','w','h' ou 'left','top','width','height')
        - Dictionnaire contenant une liste sous 'rects'
        """
        # Aucun résultat
        if detection is None:
            return None, None

        # Format dictionnaire
        if isinstance(detection, dict):
            for keys in (("x", "y", "w", "h"), ("left", "top", "width", "height")):
                if all(k in detection for k in keys):
                    return (detection[keys[0]], detection[keys[1]]), (
                        detection[keys[2]],
                        detection[keys[3]],
                    )
            # Liste de rectangles dans une clé dédiée
            rects = detection.get("rects")
            if isinstance(rects, (list, tuple)) and len(rects) > 0:
                bbox = self._select_bbox(rects)
                if bbox is not None:
                    return (bbox[0], bbox[1]), (bbox[2], bbox[3])
            return None, None

        # Format liste/tuple
        if isinstance(detection, (list, tuple)):
            if len(detection) == 0:
                return None, None

            # Liste de bboxes
            if isinstance(detection[0], (list, tuple)):
                bbox = self._select_bbox(detection)
                if bbox is not None and len(bbox) >= 4:
                    return (bbox[0], bbox[1]), (bbox[2], bbox[3])
                return None, None

            # Un seul bbox [x, y, w, h]
            if len(detection) >= 4 and all(isinstance(v, (int, float)) for v in detection[:4]):
                return (detection[0], detection[1]), (detection[2], detection[3])

        # Format non reconnu
        return None, None

    def _select_bbox(self, bboxes):
        """Sélectionne un bbox depuis une liste (prend le plus grand si possible)."""
        valids = [
            b for b in bboxes if isinstance(b, (list, tuple)) and len(b) >= 4 and all(
                isinstance(x, (int, float)) for x in b[:4]
            )
        ]
        if not valids:
            return None
        # Choisir le plus grand rectangle (aire w*h)
        return max(valids, key=lambda b: float(b[2]) * float(b[3]))
