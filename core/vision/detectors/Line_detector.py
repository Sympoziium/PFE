#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Line_detector.py
# ------------------
# Module de détecteur de lignes en pointillés dans une image

from .detector_base import BaseDetector
import cv2
import numpy as np

class LineDetector(BaseDetector):
    def __init__(self, white_threshold=200, min_area=100, offset_ratio=0.5):
        """
        Initialise le détecteur de ligne.
        
        Args:
            white_threshold: Seuil pour détecter le blanc (0-255). Plus élevé = plus strict
            min_area: Aire minimale d'un pointillé pour être considéré (plus petit que pour ligne continue)
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
        # 1. Définition de la zone de détection (partie BASSE de l'image)
        height, width = frame.shape[:2]         
        offset_y = int(height * self.offset_ratio) 
        roi = frame[offset_y:height, :] 
        roi_height = roi.shape[0]
        
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Utiliser le seuil configurable
        _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
        
        # Morphologie légère pour connecter les pointillés proches
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # 3. Détection de contours (compatible OpenCV 3 et 4)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
        
        if len(contours) == 0:
            cv2.putText(frame, "Aucune ligne detectee", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            return None
        
        # 4. Filtrer les contours pour trouver les POINTILLÉS
        # On cherche plusieurs petits rectangles alignés verticalement
        valid_dashes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            
            x, y, w, h = cv2.boundingRect(cnt)
            
            # Critères pour un pointillé de ligne discontinue:
            # - Petits rectangles (pas trop larges ni trop hauts)
            # - Forme à peu près rectangulaire
            # - Pas trop près des bords
            if w < width * 0.3 and h < roi_height * 0.4:  # Pas trop grand
                aspect_ratio = float(h) / float(w) if w > 0 else 0
                # Accepter les formes rectangulaires (verticales ou carrées)
                if 0.5 < aspect_ratio < 5:  
                    cx = x + w / 2
                    cy = y + h / 2
                    valid_dashes.append({
                        'contour': cnt,
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h,
                        'cx': cx,
                        'cy': cy,
                        'area': area
                    })
        
        if len(valid_dashes) == 0:
            cv2.putText(frame, "Pas de ligne valide", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            return None
        
        # 5. Grouper les pointillés qui sont alignés verticalement
        # On cherche les pointillés qui ont une position X similaire (tolérance)
        X_TOLERANCE = width * 0.15  # 15% de la largeur comme tolérance
        
        # Trouver le groupe de pointillés le plus aligné
        best_group = []
        
        # Essayer chaque pointillé comme point de départ d'un groupe
        for dash in valid_dashes:
            group = [dash]
            base_cx = dash['cx']
            
            # Trouver tous les pointillés alignés avec celui-ci
            for other_dash in valid_dashes:
                if other_dash is dash:
                    continue
                if abs(other_dash['cx'] - base_cx) < X_TOLERANCE:
                    group.append(other_dash)
            
            # Garder le groupe le plus grand
            if len(group) > len(best_group):
                best_group = group
        
        if len(best_group) < 2:  # Au moins 2 pointillés pour former une ligne
            cv2.putText(frame, "Pas assez de pointilles alignes", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            return None
        
        # 6. Calculer le centre moyen de tous les pointillés du groupe
        total_cx = sum([d['cx'] for d in best_group])
        total_cy = sum([d['cy'] for d in best_group])
        avg_cx = int(total_cx / len(best_group))
        avg_cy = int(total_cy / len(best_group)) + offset_y
        
        offset = avg_cx - (width / 2)
        
        # Dessin pour debug
        # Dessiner tous les pointillés du groupe
        for dash in best_group:
            x, y, w, h = dash['x'], dash['y'], dash['w'], dash['h']
            cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (255, 0, 0), 2)
        
        # Cercle rouge au centre moyen
        cv2.circle(frame, (avg_cx, avg_cy), 10, (0, 0, 255), -1)
        
        # Ligne verte au centre de l'image (cible)
        cv2.line(frame, (int(width/2), 0), (int(width/2), height), (0, 255, 0), 2)
        
        # Ligne cyan montrant la position détectée de la ligne
        cv2.line(frame, (avg_cx, 0), (avg_cx, height), (0, 255, 255), 2)
        
        # Texte avec offset et nombre de pointillés détectés
        text = "Offset: " + str(int(offset)) + " (Points: " + str(len(best_group)) + ")"
        cv2.putText(frame, text, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Afficher le seuil
        threshold_text = "Seuil: " + str(self.white_threshold)
        cv2.putText(frame, threshold_text, (20, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return offset