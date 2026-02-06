#!/usr/bin/env python
# -*- coding: utf-8 -*-
# detector_base.py
# ------------------
# ce module défini la classe de base pour les détecteurs de vision
# il servira de base pour l'implémentation du CNN

from abc import ABC, abstractmethod

class BaseDetector(ABC):
    @abstractmethod
    def process(self, frame, filename=None):
        """
        Analyse une image et retourne un résultat standardisé.

        Args:
            frame: Image BGR (format OpenCV natif)
            filename: Nom du fichier image capturé (optionnel, pour nouveaux détecteurs)

        Returns:
            dict: Résultat de détection avec les clés standardisées suivantes:
            {
                'Object_detected': bool,           # True si objet détecté, False sinon
                'detection_box': tuple or None,    # (x, y, w, h) coordonnées bbox, None si pas de détection
                'confidence': float or None,       # Score de confiance [0.0-1.0], None si pas de détection
                'area': int or None,               # Aire du contour en pixels, None si pas de détection
                'logs': list,                      # Liste de messages de debug pour terminal (optionnel)
                'steps': list,                     # Liste d'étapes de diagnostic avec URLs (optionnel)
                'source_file_url': str or None,    # URL de l'image source (optionnel)
                'annotated_url': str or None,      # URL de l'image avec annotations (bbox tracée)
                'Processing time': float           # Temps de traitement en secondes (ajouté par le pipeline)
            }

        Note:
            - Les anciens détecteurs peuvent avoir une interface legacy (frame seulement).
            - Le pipeline vision utilise l'introspection pour détecter la signature.
            - Les clés 'logs', 'steps', 'source_file_url', 'annotated_url' sont optionnelles.
            - Pour compatibilité, les détecteurs legacy peuvent retourner d'autres formats.
        """
        pass

    @abstractmethod
    def atach_capture_dir(self, capture_dir):
        """
        Attache le dossier de capture d'images au détecteur.
        """
        pass