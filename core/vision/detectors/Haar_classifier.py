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

from .detector_base import BaseDetector
import cv2 


class HaarStopDetector(BaseDetector):
    def __init__(self, cascade_path='haarcascade_stop.xml', scaleFactor=1.1, minNeighbors=5):
        """
        Initialise le détecteur de panneaux de stop avec un classifieur de Haar.
        
        :param cascade_path: Chemin vers le fichier XML du classifieur de Haar.
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        self.classifier = cv2.CascadeClassifier(cascade_path)
        self.scaleFactor = scaleFactor
        self.minNeighbors = minNeighbors
        self.CAPTURE_DIR = None  # Dossier de capture d'images, à attacher via attach_capture_dir

    def attach_capture_dir(self, capture_dir):
        """
        Attache le dossier de capture d'images au détecteur.
        
        :param capture_dir: Chemin vers le dossier de capture d'images.
        """
        self.CAPTURE_DIR = capture_dir

    def process(self, frame):
        """
        Analyse une image et retourne les coordonnées des panneaux de stop détectés.
        
        :param frame: Image à analyser (numpy array).
        :return: Dictionnaire avec les coordonnées des panneaux détectés.
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        stops = self.classifier.detectMultiScale(gray, scaleFactor=self.scaleFactor, minNeighbors=self.minNeighbors)
        
        detections = []
        for (x, y, w, h) in stops:
            detections.append({"x": int(x), "y": int(y), "width": int(w), "height": int(h)})
        
        return {"detector": "haar_stop", "detections": detections}
  


