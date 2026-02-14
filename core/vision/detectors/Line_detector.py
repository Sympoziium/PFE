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
    def __init__(self, white_threshold=200, min_area=300, offset_ratio=0.6):
        """
        Initialise le détecteur de ligne.
        
        Args:
            white_threshold: Seuil pour détecter le blanc (0-255). Plus élevé = plus strict
            min_area: Aire minimale du contour pour être considéré comme une ligne
            offset_ratio: Ratio de la hauteur où commencer la détection (0.0-1.0)
        """
        self.white_threshold = white_threshold
        self.min_area = min_area
        self.offset_ratio = offset_ratio
        self.CAPTURE_DIR = None
        
    def update_params(self, white_threshold=None, min_area=None, offset_ratio=None):
        """Met à jour les paramètres du détecteur."""
        if white_threshold is not None:
            self.white_threshold = int(white_threshold)
        if min_area is not None:
            self.min_area = int(min_area)
        if offset_ratio is not None:
            self.offset_ratio = float(offset_ratio)
            
    def get_params(self):
        """Retourne les paramètres actuels."""
        return {
            'white_threshold': self.white_threshold,
            'min_area': self.min_area,
            'offset_ratio': self.offset_ratio
        }
        
    def process(self, frame):
        # Appel de la méthode interne
        line_center = self.detect_lines(frame)
        return {"detector": "line", "value": line_center}
    
    def attach_capture_dir(self, capture_dir):
        self.CAPTURE_DIR = capture_dir

    def detect_lines(self, frame):
        # 1. Définition de la zone de détection
        height, width = frame.shape[:2]         
        offset_y = int(height * self.offset_ratio) 
        roi = frame[offset_y:height, :] 
        
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Utiliser le seuil configurable
        _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
        
        # Optionnel: Morphologie pour enlever le bruit
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # 3. Détection de contours (compatible OpenCV 3 et 4)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
        
        if len(contours) == 0:
            cv2.putText(frame, "Aucune ligne detectee", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return None
        
        # 4. Filtrer les contours
        valid_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            if w > width * 0.2:
                aspect_ratio = float(w) / float(h) if h > 0 else 0
                if aspect_ratio > 2:
                    cy = y + h / 2
                    valid_contours.append((cnt, cy, area))
        
        if len(valid_contours) == 0:
            cv2.putText(frame, "Pas de ligne valide", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            return None
        
        # 5. Prendre le contour le plus bas
        valid_contours.sort(key=lambda x: (-x[1], -x[2]))
        best_contour = valid_contours[0][0]
        
        # 6. Calculer le centre
        M = cv2.moments(best_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"]) + offset_y 
            offset = cx - (width / 2)

            # Dessin
            x, y, w, h = cv2.boundingRect(best_contour)
            cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (255, 0, 0), 2)
            cv2.circle(frame, (cx, cy), 10, (0, 0, 255), -1) 
            cv2.line(frame, (cx, 0), (cx, height), (0, 255, 0), 2)
            
            text = "Offset: " + str(int(offset))
            cv2.putText(frame, text, (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Afficher le seuil
            threshold_text = "Seuil: " + str(self.white_threshold)
            cv2.putText(frame, threshold_text, (20, 70), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            return offset
        
        return None