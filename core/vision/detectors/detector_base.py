#!/usr/bin/env python
# -*- coding: utf-8 -*-
# detector_base.py
# ------------------
# Ce module définit la classe de base pour les détecteurs de vision.
# Il servira de base pour l'implémentation du CNN.
#
# IMPORTANT — Convention de sortie standardisée :
# Les détecteurs ne font QUE de la détection.  L'annotation des images
# (dessin de bboxes, sauvegarde d'images annotées) est gérée de façon
# centralisée par le VisionPipeline / server_controller.

from abc import ABC, abstractmethod


class BaseDetector(ABC):
    @abstractmethod
    def process(self, frame, filename=None):
        """
        Analyse une image et retourne un résultat de détection **sans annotation**.

        Le détecteur ne doit PAS dessiner sur l'image ni sauvegarder d'image
        annotée — c'est la responsabilité du pipeline / contrôleur.

        Args:
            frame: Image BGR (format OpenCV natif).
            filename: Nom du fichier image capturé (optionnel).

        Returns:
            dict: Résultat standardisé ::

                {
                    'Object_detected': bool,
                    'detections': [                         # liste de toutes les détections
                        {
                            'object': str,                  # nom de l'objet détecté
                            'detection_box': (x, y, w, h),  # coordonnées de la bbox
                            'confidence': float,            # score de confiance [0.0-1.0] (optionnel)
                        },
                        ...
                    ],
                    'logs': list,                           # messages de debug (optionnel)
                    'Processing time': float,               # ajouté par le pipeline (ne pas remplir)
                }

        Note:
            - Le pipeline ajoute 'Processing time' automatiquement.
            - L'annotation et la génération des URLs ('annotated_url',
              'source_file_url') sont gérées par le pipeline / contrôleur.
        """
        pass

    @abstractmethod
    def attach_capture_dir(self, capture_dir):
        """
        Attache le dossier de capture d'images au détecteur.
        """
        pass

    @abstractmethod
    def process_passive(self, frame):
        """
        Détection passive optimisée pour le live feed.

        Retourne le même format standardisé que process(), mais peut omettre
        les logs et les champs optionnels pour minimiser la latence.

        Returns:
            dict ::

                {
                    'Object_detected': bool,
                    'detections': [
                        {'object': str, 'detection_box': (x, y, w, h)},
                        ...
                    ],
                    'timestamp': float,   # time.time() de la détection
                }
        """
        pass