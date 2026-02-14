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
    def __init__(self, white_threshold=200, min_area=300):
        """
        Initialise le détecteur de ligne.
        
        Args:
            white_threshold: Seuil pour détecter le blanc (180-255). Plus élevé = plus strict
            min_area: Aire minimale du contour pour être considéré comme une ligne
        """
        self.white_threshold = white_threshold
        self.min_area = min_area
        self.CAPTURE_DIR = None
        
    def process(self, frame):
        # Appel de la méthode interne
        line_center = self.detect_lines(frame)
        return {"detector": "line", "value": line_center}
    
    def attach_capture_dir(self, capture_dir):
        self.CAPTURE_DIR = capture_dir

    def detect_lines(self, frame):
        # 1. Définition de la zone de détection (partie BASSE de l'image)
        height, width = frame.shape[:2]         
        offset_y = int(height * 0.6)  # Chercher dans les 40% inférieurs
        roi = frame[offset_y:height, :] 
        roi_height = roi.shape[0]
        
        # 2. Traitement d'image pour détecter UNIQUEMENT le blanc
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # CHANGEMENT: Seuil plus élevé pour détecter uniquement le blanc pur
        # Tout ce qui est en dessous de white_threshold sera noir (0)
        _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
        
        # Optionnel: Morphologie pour enlever le bruit
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)  # Enlève petits points
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)  # Ferme petits trous

        # 3. Détection de contours pour trouver la ligne
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            # Afficher un message si aucune ligne blanche détectée
            cv2.putText(frame, "Aucune ligne blanche detectee", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return None
        
        # 4. Filtrer et trier les contours
        valid_contours = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            
            # Filtrer par aire minimale
            if area < self.min_area:
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Critères pour une ligne horizontale:
            # - Largeur suffisante (au moins 20% de la largeur de l'image)
            # - Hauteur petite par rapport à la largeur (ratio > 2)
            if w > width * 0.2:
                aspect_ratio = float(w) / float(h) if h > 0 else 0
                if aspect_ratio > 2:  # Ligne horizontale
                    # Calculer la position Y (pour prendre la plus basse)
                    cy = y + h / 2
                    valid_contours.append((cnt, cy, area))
        
        if len(valid_contours) == 0:
            # Afficher un message si les contours ne correspondent pas à une ligne
            cv2.putText(frame, "Contours detectes mais pas de ligne", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            return None
        
        # 5. Prendre le contour le plus BAS (plus proche du robot)
        # ou le plus GRAND si plusieurs à la même hauteur
        valid_contours.sort(key=lambda x: (-x[1], -x[2]))  # Trier par Y desc, puis aire desc
        best_contour = valid_contours[0][0]
        
        # 6. Calculer le centre de la ligne détectée
        M = cv2.moments(best_contour)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"]) + offset_y 
            offset = cx - (width / 2)

            # --- DESSIN POUR L'AFFICHAGE ---
            # Rectangle autour du contour détecté (pour debug)
            x, y, w, h = cv2.boundingRect(best_contour)
            cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (255, 0, 0), 2)
            
            # Cercle sur le centre de la ligne
            cv2.circle(frame, (cx, cy), 10, (0, 0, 255), -1) 
            
            # Ligne de guidage verticale
            cv2.line(frame, (cx, 0), (cx, height), (0, 255, 0), 2)
            
            # Texte avec offset et info de seuil
            text = "Offset: " + str(int(offset))
            cv2.putText(frame, text, (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Afficher le seuil utilisé (pour debug)
            threshold_text = "Seuil: " + str(self.white_threshold)
            cv2.putText(frame, threshold_text, (20, 70), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            return offset
        
        return None