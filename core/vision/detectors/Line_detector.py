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
        # Appel de la méthode interne
        line_center = self.detect_lines(frame)
        return {"detector": "line", "value": line_center}
    
    def attach_capture_dir(self, capture_dir):
        self.CAPTURE_DIR = capture_dir

    def detect_lines(self, frame):
        # 1. Définition de la zone de détection
        height, width = frame.shape[:2]         
        offset_y = int(height * 0.7) 
        roi = frame[offset_y:height, :] 
        
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        # 3. Calcul de la position
        M = cv2.moments(thresh)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"]) + offset_y 
            offset = cx - (width / 2)

            # --- DESSIN POUR L'AFFICHAGE ---
            # Cercle sur la ligne
            cv2.circle(frame, (cx, cy), 10, (0, 0, 255), -1) 
            # Ligne de guidage
            cv2.line(frame, (cx, 0), (cx, height), (0, 255, 0), 2)
            
            # Texte (Format compatible Python 3.5)
            text = "Offset: " + str(int(offset))
            cv2.putText(frame, text, (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            return offset
        
        return None