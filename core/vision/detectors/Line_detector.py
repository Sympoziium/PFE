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
        # 1. Définition de la zone de détection (partie BASSE de l'image)
        height, width = frame.shape[:2]         
        offset_y = int(height * 0.6)  # Chercher dans les 40% inférieurs seulement
        roi = frame[offset_y:height, :] 
        roi_height = roi.shape[0]
        
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

        # 3. Détection de contours pour trouver la ligne
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) == 0:
            return None
        
        # 4. Filtrer les contours : garder ceux qui ressemblent à une ligne
        # Une ligne horizontale aura une largeur importante et une faible hauteur
        valid_contours = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            
            # Critères pour une ligne:
            # - Largeur suffisante (au moins 30% de la largeur de l'image)
            # - Hauteur petite par rapport à la largeur (ratio > 3)
            # - Aire minimale pour éviter le bruit
            if w > width * 0.3 and area > 200:
                aspect_ratio = float(w) / float(h) if h > 0 else 0
                if aspect_ratio > 3:  # Ligne horizontale
                    valid_contours.append((cnt, y + h/2))  # Stocker avec position Y
        
        if len(valid_contours) == 0:
            return None
        
        # 5. Prendre le contour le plus BAS (plus proche du robot)
        valid_contours.sort(key=lambda x: x[1], reverse=True)
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
            
            # Texte (Format compatible Python 3.5)
            text = "Offset: " + str(int(offset))
            cv2.putText(frame, text, (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            return offset
        
        return None