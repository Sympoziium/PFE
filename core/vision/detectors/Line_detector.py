#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Line_detector.py
# ------------------
# Module de détecteur de lignes dans une image
# en appliquant des filtres de traitement d'image,
# comme la détection de contours

from .detector_base import BaseDetector
import cv2
import numpy as np

class LineDetector(BaseDetector):
    def process(self, frame):
        # On récupère le centre de la ligne
        line_center = self.detect_lines(frame)
        return {"detector": "line", "value": line_center}
    
    def detect_lines(self, frame):
        # Dessiner un point sur l'image pour l'interface web
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cv2.circle(frame, (cx, int(height*0.8)), 5, (0, 255, 0), -1) 
    # Le point vert apparaîtra sur ton flux Flask !
        # 1. Région d'Intérêt (ROI) : on ne regarde que le bas de l'image
        height, width = frame.shape[:2]
        roi = frame[int(height*0.6):height, :] # Garde les 40% du bas

        # 2. Conversion en Gris et Flou pour réduire le bruit
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 3. Seuillage (Threshold) : Isoler la ligne noire
        # Ajuste le 60 selon l'éclairage de ta pièce
        _, thresh = cv2.threshold(blur, 60, 255, cv2.THRESH_BINARY_INV)

        # 4. Calcul du centre de masse (Moments)
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            # On retourne l'erreur par rapport au centre (0 = parfaitement centré)
            error = cx - (width / 2)
            return error
        
        return None # Aucune ligne détectée