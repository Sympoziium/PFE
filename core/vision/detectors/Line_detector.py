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
        # DEBUG
        print("DEBUG: detect_lines appelé") 
        
        # Test de luminosité : affiche la valeur maximale trouvée dans la zone
        # print("Max pixel value in ROI:", np.max(gray))

        _, thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)

        # 1. ROI : On regarde le bas du tapis (la route juste devant le robot)
        height, width = frame.shape[:2]
        roi = frame[int(height*0.7):height, :] 

        # 2. Prétraitement
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 3. Seuillage pour ligne BLANCHE
        # On cherche les pixels brillants (proches de 255)
        # Ajuste le 200 selon la luminosité de ta pièce
        _, thresh = cv2.threshold(blur, 200, 255, cv2.THRESH_BINARY)

        # 4. Calcul du centre de masse
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            # On dessine un point bleu sur l'image pour confirmer la détection
            cv2.circle(frame, (cx, int(height*0.85)), 10, (255, 0, 0), -1)
            return cx - (width / 2)
        
        return None