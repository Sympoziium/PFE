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

        return {"detector": "line", "value": line_center}
    
    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def detect_lines(self, frame):

        #Définition de la région d'intéret
        height, width = frame.shape[:2] 
        offset_y = int(height * 0.3)        
        roi = frame[int(offset_y):height, :] 
        
        #Traitement
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        #Seuillage
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        #Calcul position ligne
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"]) 
            cv2.circle(frame, (cx, int(M["m01"] / M["m00"]) + offset_y), 10, (0, 0, 255), -1)
            cv2.line(frame, (cx, 0), (cx, height), (0, 255, 0), 2)
            return cx - (width / 2)
        
        # Retourner None explicitement si rien n'est détecté
        return None