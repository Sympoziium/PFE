#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Haar_classifier.py
# ------------------
# Module de détection d'objets générique via classifieurs de Haar (cv2.CascadeClassifier).
# Supporte le chargement de multiples fichiers .xml pré-entraînés.
# Chaque classifieur est identifié par un nom (ex: 'stop_sign', 'pieton', etc.)
# et tous sont appliqués séquentiellement sur l'image pour accumuler les détections.
# Recommendations:
# - utiliser des images de basse résolution pour meilleures perf (320x240p)
# - implémenter un modèle préentraîné avant d'entrainer le notre
# - ne pas tenter de faire du real time a plus de 2-3 fps

import os, uuid
from .detector_base import BaseDetector
import cv2 
from flask import url_for
import numpy as np

class HaarDetector(BaseDetector):
    def __init__(self, scaleFactor=1.1, minNeighbors=5):
        """
        Initialise le détecteur générique basé sur des classifieurs de Haar.
        On peut y charger plusieurs fichiers .xml via add_classifier().
        
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        self.name = "HaarDetector"
        self.classifiers = {}      # {nom: cv2.CascadeClassifier}
        self.cascade_paths = {}    # {nom: chemin_xml}
        self.scaleFactor = scaleFactor
        self.minNeighbors = minNeighbors
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        # Diagnostique et logs des messages
        self.logs = []
        self.steps = []


    def add_classifier(self, name, cascade_path):
        """Ajoute un classifieur .xml à la liste.
        
        :param name: Nom identifiant le classifieur (ex: 'stop_sign').
        :param cascade_path: Chemin vers le fichier .xml du classifieur.
        """
        try:
            if not os.path.exists(cascade_path):
                print("ATTENTION: fichier cascade introuvable: {}".format(cascade_path))
            self.cascade_paths[name] = cascade_path
            classifier = cv2.CascadeClassifier(cascade_path)
            if classifier.empty():
                print("ATTENTION: le classifieur '{}' est vide (fichier invalide?)".format(name))
            self.classifiers[name] = classifier
            print("Classifieur '{}' chargé depuis: {}".format(name, cascade_path))
        except Exception as e:
            print("Erreur lors de l'ajout du classifieur {}: {}".format(name, str(e)))

    def remove_classifier(self, name):
        """Supprime un classifieur par nom."""
        if name in self.classifiers:
            try:
                del self.classifiers[name]
                del self.cascade_paths[name]
                print("Classifieur '{}' supprimé.".format(name))
            except Exception as e:
                print("Erreur lors de la suppression du classifieur {}: {}".format(name, str(e)))

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        try:
            if not isinstance(capture_dir, str):
                raise ValueError("Le chemin du dossier de capture doit être une chaîne de caractères.")
            self.CAPTURE_DIR = capture_dir
        except Exception as e:
            print("Erreur lors de l'attachement du dossier de capture: {}".format(str(e)))


    def process(self, frame, filename=None):
        """
        Analyse une image avec tous les classifieurs chargés.
        Retourne un payload standardisé compatible avec l'UI.
        Les logs contiennent le détail de chaque objet détecté par chaque classifieur.
        
        :param frame: Image à analyser (numpy array, non utilisé ici car on relit depuis le disque).
        :param filename: Nom du fichier image capturé.
        :return: Dictionnaire standardisé (voir BaseDetector).
        """
        # Réinitialisation des logs
        self.steps = []
        self.logs = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        # Crée le dossier de diagnostics s'il n'existe pas
        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            # Étape 1: Charger l'image capturée en BGR
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            classifier_names = list(self.classifiers.keys())
            self.logs.append('=== DETECTION HAAR CASCADE ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Classifieurs charges: {}'.format(', '.join(classifier_names) if classifier_names else 'aucun'))
            self.logs.append('Config: scaleFactor={}, minNeighbors={}'.format(self.scaleFactor, self.minNeighbors))

            if not self.classifiers:
                self.logs.append('ERREUR: aucun classifieur charge. Utilisez add_classifier().')
                self.logs.append('=== FIN DETECTION ===')
                return {
                    'Object_detected': False, 'detection_box': None,
                    'confidence': 0.0, 'area': None, 'logs': self.logs,
                    'source_file_url': url_for('static', filename='captured_images/{}'.format(filename)),
                    'annotated_url': None,
                }

            # Étape 2: Filtrage + conversion en niveaux de gris
            gray = self._filter_image(frame_bgr)

            # Étape 3: Appliquer tous les classifieurs et accumuler les détections
            detections = self._detect_objects(gray, frame_bgr)

            # Étape 4: Résumé dans les logs pour la console UI
            self.logs.append('')
            self.logs.append('--- RESUME DES DETECTIONS ---')
            if detections:
                self.logs.append('Total: {} objet(s) detecte(s)'.format(len(detections)))
                # Compter les détections par classifieur
                counts = {}
                for det in detections:
                    obj_name = det['object']
                    counts[obj_name] = counts.get(obj_name, 0) + 1
                for obj_name, count in counts.items():
                    self.logs.append('  - {}: {} detection(s)'.format(obj_name, count))
            else:
                self.logs.append('Aucun objet detecte par aucun classifieur.')

            self.logs.append('=== FIN DETECTION ===')

            # Étape 5: Sauvegarder l'image annotée (toutes les bbox dessinées)
            annotated_url = None
            if detections:
                base, ext = os.path.splitext(filename)
                ann_name = '{}_haar_det{}'.format(base, ext or '.jpg')
                ann_path = os.path.join(self.CAPTURE_DIR, ann_name)
                cv2.imwrite(ann_path, frame_bgr)
                annotated_url = url_for('static', filename='captured_images/{}'.format(ann_name))

            # Étape 6: Construire le payload standardisé
            # On prend la plus grande bbox comme détection principale (pour l'indicateur UI)
            best_box = None
            best_area = 0
            for det in detections:
                bx, by, bw, bh = det['detection_box']
                a = bw * bh
                if a > best_area:
                    best_area = a
                    best_box = det['detection_box']

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = {
                'Object_detected': len(detections) > 0,
                'detection_box': best_box,
                'confidence': 1.0 if detections else 0.0,
                'area': best_area if best_area > 0 else None,
                'logs': self.logs,
                'source_file_url': source_url,
                'annotated_url': annotated_url,
            }

            return payload

        except Exception as e:
            self.logs.append('ERREUR: {}'.format(str(e)))
            return {'error': 'process failed', 'details': str(e), 'logs': self.logs}

    def diagnostique_detecteur(self, filename):
        """
        Diagnostic détaillé: relance la détection en mode diagnostic
        (sauvegarde des étapes intermédiaires de filtrage et détection).
        
        :param filename: Nom du fichier image capturé.
        :return: dict standardisé avec les étapes intermédiaires.
        """
        self.steps = []
        self.logs = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            classifier_names = list(self.classifiers.keys())
            self.logs.append('=== DIAGNOSTIC HAAR CASCADE ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Classifieurs: {}'.format(', '.join(classifier_names) if classifier_names else 'aucun'))
            self.logs.append('Config: scaleFactor={}, minNeighbors={}'.format(self.scaleFactor, self.minNeighbors))

            # Sauvegarder l'image source
            self._save_step(frame_bgr, '0_image_source', 'bgr')

            # Filtrage en mode diagnostic (sauvegarde étapes intermédiaires)
            gray = self._filter_image(frame_bgr, diagnostic_mode=True)

            # Détection en mode diagnostic
            detections = self._detect_objects(gray, frame_bgr, diagnostic_mode=True)

            # Résumé
            self.logs.append('')
            self.logs.append('--- RESUME DES DETECTIONS ---')
            if detections:
                self.logs.append('Total: {} objet(s) detecte(s)'.format(len(detections)))
                counts = {}
                for det in detections:
                    obj_name = det['object']
                    counts[obj_name] = counts.get(obj_name, 0) + 1
                for obj_name, count in counts.items():
                    self.logs.append('  - {}: {} detection(s)'.format(obj_name, count))
            else:
                self.logs.append('Aucun objet detecte.')

            self.logs.append('=== FIN DIAGNOSTIC ===')

            # Sauvegarder l'image finale annotée
            self._save_step(frame_bgr, 'resultat_final', 'bgr')

            best_box = None
            best_area = 0
            for det in detections:
                bx, by, bw, bh = det['detection_box']
                a = bw * bh
                if a > best_area:
                    best_area = a
                    best_box = det['detection_box']

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            return {
                'Object_detected': len(detections) > 0,
                'detection_box': best_box,
                'confidence': 1.0 if detections else 0.0,
                'area': best_area if best_area > 0 else None,
                'logs': self.logs,
                'steps': self.steps,
                'source_file_url': source_url,
                'annotated_url': self.steps[-1]['url'] if self.steps else None,
            }

        except Exception as e:
            self.logs.append('ERREUR DIAGNOSTIC: {}'.format(str(e)))
            import traceback
            traceback.print_exc()
            return {'error': 'diagnostic failed', 'details': str(e), 'logs': self.logs}

    def _filter_image(self, frame, diagnostic_mode=False):
        """
        Applique un filtrage à l'image pour réduire le bruit et améliorer la détection.
        Si diagnostic_mode est True, sauvegarde les étapes de filtrage pour l'affichage web.
        """
        # Appliquer un flou gaussien pour réduire le bruit
        img_filter = cv2.GaussianBlur(frame, (5, 5), 0)
        if diagnostic_mode:
            self._save_step(img_filter, '1_gaussian_blur', 'bgr')

        # Convertir en niveaux de gris
        gray_filtered = cv2.cvtColor(img_filter, cv2.COLOR_BGR2GRAY)
        if diagnostic_mode:
            self._save_step(gray_filtered, '2_gray_filtered', 'gray')

        return gray_filtered


    def _detect_objects(self, gray_filtered, frame_bgr, diagnostic_mode=False):
        """
        Parcourt tous les classifieurs chargés et accumule les détections.
        Dessine les bbox + labels directement sur frame_bgr (pour l'annotation).
        
        :param gray_filtered: Image en niveaux de gris filtrée.
        :param frame_bgr: Image BGR originale (sera annotée en place).
        :param diagnostic_mode: Si True, sauvegarde après chaque classifieur.
        :return: Liste de dicts [{'object': nom, 'detected': True, 'detection_box': (x,y,w,h)}, ...]
        """
        detections = []

        for name, classifier in self.classifiers.items():
            self.logs.append('')
            self.logs.append('--- Classifieur: {} ---'.format(name))

            if classifier.empty():
                self.logs.append('  ATTENTION: classifieur vide, ignore.')
                continue

            results = classifier.detectMultiScale(
                gray_filtered,
                scaleFactor=self.scaleFactor,
                minNeighbors=self.minNeighbors
            )

            # test de détection
            if len(results) == 0:
                self.logs.append('  Aucune detection.')
                continue

            self.logs.append('  {} detection(s) trouvee(s):'.format(len(results)))

            for i, (x, y, w, h) in enumerate(results):
                self.logs.append('    #{}: pos=({},{}) taille={}x{} aire={}'.format(
                    i + 1, x, y, w, h, w * h))

                # Dessiner le rectangle et le label sur l'image
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame_bgr, "{}".format(name), (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                detections.append({
                    "object": name,
                    "detected": True,
                    "detection_box": (x, y, w, h)
                })

            if diagnostic_mode:
                self._save_step(frame_bgr, '3_detection_{}'.format(name), 'bgr')

        return detections

    
    def _save_step(self, img, name, mode):
        """
        Sauvegarde toutes les images pour l'affichage web.
        cv2.imwrite() attend du BGR, donc on convertit tout vers BGR avant sauvegarde.

        mode:
        'bgr'   -> image BGR OpenCV (deja en BGR, pas de conversion)
        'gray'  -> image 1 canal (converti vers BGR 3 canaux)
        'hsv'   -> image HSV (convertie vers BGR)
        'RGB'   -> image RGB (convertie vers BGR)

        """
        print("Saving step: {} ({})".format(name, mode))

        base = 'Diag_Haar_{}_{}'.format(name, uuid.uuid4().hex[:6])
        out_name = base + '.jpg'
        out_path = os.path.join(self.DIAGNOSTIC_DIR, out_name)

        if mode == 'bgr':
            to_save = img  # Deja en BGR, pas de conversion

        elif mode == 'gray':
            to_save = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)  # 1 canal -> 3 canaux BGR

        elif mode == 'hsv':
            to_save = cv2.cvtColor(img, cv2.COLOR_HSV2BGR)  # HSV -> BGR

        elif mode == 'RGB':
            to_save = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # RGB -> BGR

        else:
            raise ValueError("Unknown save mode: {}".format(mode))

        cv2.imwrite(out_path, to_save)  # imwrite attend BGR
        url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
        self.steps.append({"name": name, "url": url})
