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
        
        line_center = self.detect_lines(frame)

        return {"detector": "line", "value": self.detect_lines(frame)}
    
    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def detect_lines(self, frame):
        print("LineDetector: Processing frame for line detection.")
        #Définition de la région d'intéret
        height, width = frame.shape[:2]         
        roi = frame[int(height*0.7):height, :] 
        
        #Traitement
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        #Seuillage
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        #Calcul position ligne
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            # Feedback visuel : Ligne verticale BLANCHE
            # On dessine du haut (0) jusqu'au bas (height) de l'image à la position cx
            cv2.line(frame, (cx, 0), (cx, height), (255, 255, 255), 2)
            
            return cx - (width / 2)