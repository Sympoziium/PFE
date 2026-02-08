#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Haar_classifier.py
# ------------------
# Module de détecteur de panneaux de stop dans une image
# en utilisant un classifieur de Haar via OpenCV (cv2.CascadeClassifier)
# Recommendations:
# - utiliser des images de basse résolution pour meilleures perf (320x240p)
# - implémenter un modèle préentraîné avant d'entrainer le notre
# - ne pas tenter de faire du real time a plus de 2-3 fps

import os, uuid
from .detector_base import BaseDetector
import cv2 
from flask import url_for
import numpy as np

class HaarStopDetector(BaseDetector):
    def __init__(self, scaleFactor=1.1, minNeighbors=5):
        """
        Initialise le détecteur de panneaux de stop avec un classifieur de Haar.
        
        :param cascade_path: Chemin vers le fichier XML du classifieur de Haar.
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        self.classifiers = {}
        self.cascade_path = {}
        self.scaleFactor = scaleFactor
        self.minNeighbors = minNeighbors
        self.CAPTURE_DIR = None

    def add_classifier(self, name, cascade_path):
        """Ajoute un classifieur à la liste."""
        try:
            self.cascade_path[name] = cascade_path
            self.classifiers[name] = cv2.CascadeClassifier(cascade_path)
        except Exception as e:
            print("Erreur lors de l'ajout du classifieur {name}: {e}".format(name=name, e=str(e)))

    def remove_classifier(self, name):
        """Supprime un classifieur."""
        if name in self.classifiers:
            try:
                del self.classifiers[name]
                del self.cascade_path[name]
            except Exception as e:
                print("Erreur lors de la suppression du classifieur {name}: {e}".format(name=name, e=str(e)))

    def attach_capture_dir(self, capture_dir):
        """
        Attache le dossier de capture d'images au détecteur.
        
        :param capture_dir: Chemin vers le dossier de capture d'images.
        """
        try:
            if not isinstance(capture_dir, str):
                raise ValueError("Le chemin du dossier de capture doit être une chaîne de caractères.")
            self.CAPTURE_DIR = capture_dir
        except Exception as e:
            print("Erreur lors de l'attachement du dossier de capture: {e}".format(e=str(e)))


    def process(self, frame, filename=None):
        """
        Analyse une image et retourne les coordonnées des panneaux de stop détectés.
        
        :param frame: Image à analyser (numpy array).
        :return: Dictionnaire avec les coordonnées des panneaux détectés.
        """

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

            self.logs.append('=== DETECTION STOP HAAR CASCADE ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Config: Classifiers={}, scaleFactor={}, minNeighbors={}'.format(self.classifiers.keys(), self.scaleFactor, self.minNeighbors))
            # Étape 2: Convertir l'image en niveaux de gris
            gray = self._filter_image(frame_bgr)



        detections = []
        for (x, y, w, h) in stops:
            detections.append({"x": int(x), "y": int(y), "width": int(w), "height": int(h)})
        
        return {"detector": "haar_stop", "detections": detections}
  
    def _filter_image(self, frame, diagnostic_mode=False):
        """
        Applique un filtrage à l'image pour réduire le bruit et améliorer la détection.
        Si diagnostic_mode est True, sauvegarde les étapes de filtrage pour l'affichage web.
        """
        # Appliquer un flou gaussien pour réduire le bruit
        img_filter = cv2.GaussianBlur(frame, (5, 5), 0)
        if diagnostic_mode:
            self._save_step(img_filter, 'gaussian_blur', 'bgr')

        # Convertir en niveaux de gris
        gray_filtered = cv2.cvtColor(img_filter, cv2.COLOR_BGR2GRAY)
        if diagnostic_mode:
            self._save_step(gray_filtered, 'gray_filtered', 'gray')

        return gray_filtered


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

        base = 'Diag_Stop_Detector_CV_{}_{}'.format(name, uuid.uuid4().hex[:6])
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

    def _detect_object(self, frame):
        """Détecte un """
        
        
        # filtration de l'image pour réduire le bruit et améliorer la détection
        img_filter = cv2.GaussianBlur(cropped_frame, (5, 5), 0)

        gray_filered = cv2.cvtColor(img_filter, cv2.COLOR_BGR2GRAY)

        stop_signs = stop_sign_cascade.detectMultiScale(gray_filered, scaleFactor=1.05, minNeighbors=15, minSize=(30, 30))

        for (x,y,w,h) in stop_signs:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 255, 0), 3)


