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
        print("PIPELINE -> Appel de LineDetector.process") 
        line_center = self.detect_lines(frame)
        return {"detector": "line", "value": line_center}
    
    def detect_lines(self, frame):
        # 1. Définition de la zone d'intérêt (ROI) en premier
        height, width = frame.shape[:2]
        roi = frame[int(height*0.7):height, :] 

        # 2. Prétraitement (Conversion et Flou)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # DEBUG : Maintenant que 'gray' existe, on peut logger
        #print("DEBUG: detect_lines appelé") 
        #print("Max pixel value in ROI: {}".format(np.max(gray)))

        # 3. Seuillage pour ligne BLANCHE (Utilise 'blur' ici)
        # Note : Si Max pixel < 200, baisse cette valeur à 150
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        # 4. Calcul du centre de masse
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            # Feedback visuel : Cercle BLEU
            cv2.circle(frame, (cx, int(height*0.85)), 10, (255, 0, 0), -1)
            return cx - (width / 2)
        
        return None

class LineFollowerControl:
    def __init__(self, kp=0.4, base_speed=20):
        self.kp = kp  # Gain proportionnel
        self.base_speed = base_speed

    def compute_commands(self, line_error):
        if line_error is None:
            return 0, 0  # On s'arrête si on perd la ligne

        # Calcul de la correction (steering)
        # Si line_error > 0 (ligne à droite), turn_output sera positif
        turn_output = line_error * self.kp

        # Calcul des vitesses pour chaque roue
        left_speed = self.base_speed + turn_output
        right_speed = self.base_speed - turn_output

        return int(left_speed), int(right_speed)