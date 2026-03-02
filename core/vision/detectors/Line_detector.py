#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Line_detector.py
# ------------------
# Module de détecteur de lignes en pointillés dans une image

from .detector_base import BaseDetector
import cv2
import numpy as np

class LineDetector(BaseDetector):
    def __init__(self, white_threshold=150, min_area=20, offset_ratio=0.7):
        """
        Initialise le détecteur de ligne.
        
        Args:
            white_threshold: Seuil pour détecter le blanc (0-255). Plus élevé = plus strict
            min_area: Aire minimale d'un pointillé (réduit à 50 pour petits pointillés)
            offset_ratio: Ratio de la hauteur où commencer la détection (0.3 = commence à 30%)
        """
        self.white_threshold = white_threshold
        self.min_area = min_area
        self.offset_ratio = offset_ratio
        self.CAPTURE_DIR = None
        self.debug_mode = True  # Mode debug activé pour diagnostiquer le problème
        
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
        result = {"detector": "line", "value": line_center}
        # LOG DEBUG pour diagnostiquer
        if self.debug_mode:
            print("[LINE_DETECTOR] process() retourne: value={} (type: {})".format(
                line_center, type(line_center).__name__ if line_center is not None else "NoneType"))
        return result
    
    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process_passive(self, frame):
        """Détection de lignes optimisée pour le live feed."""
        return {"detector": "line", "value": self.detect_lines(frame)}

    def detect_lines(self, frame):
        # 1. Définition de la zone de détection
        height, width = frame.shape[:2]         
        offset_y = int(height * self.offset_ratio) 
        roi = frame[offset_y:height, :] 
        roi_height = roi.shape[0]
        
        # Dessiner la zone de détection (rectangle rouge)
        cv2.rectangle(frame, (0, offset_y), (width, height), (0, 0, 255), 2)
        
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Utiliser le seuil configurable pour détecter les lignes BLANCHES sur fond noir
        _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
        
        # Morphologie légère
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # 3. Détection de contours (compatible OpenCV 3 et 4)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
        
        # DEBUG: Afficher le nombre de contours trouvés
        debug_text = "Contours: " + str(len(contours))
        cv2.putText(frame, debug_text, (20, 100), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        if len(contours) == 0:
            cv2.putText(frame, "Aucune ligne detectee", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            print("[LINE_DETECTOR] Aucun contour trouvé -> retourne None")
            return None
        
        # 4. Filtrer les contours pour trouver les POINTILLÉS
        valid_dashes = []
        rejected_count = {'too_small': 0, 'too_large': 0, 'bad_ratio': 0}
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            x, y, w, h = cv2.boundingRect(cnt)
            
            # DEBUG: Dessiner TOUS les contours en violet
            cv2.drawContours(frame, [cnt], -1, (255, 0, 255), 1, offset=(0, offset_y))
            
            if area < self.min_area:
                rejected_count['too_small'] += 1
                continue
            
            # Critères plus permissifs
            if w > width * 0.4 or h > roi_height * 0.5:  # Rejeté si trop grand
                rejected_count['too_large'] += 1
                continue
                
            aspect_ratio = float(h) / float(w) if w > 0 else 0
            # Accepter presque toutes les formes (très permissif)
            if aspect_ratio < 0.3 or aspect_ratio > 10:  
                rejected_count['bad_ratio'] += 1
                continue
            
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
        
        # DEBUG: Afficher les stats de filtrage
        debug_text2 = "Valid: " + str(len(valid_dashes)) + " | Small: " + str(rejected_count['too_small']) + " | Large: " + str(rejected_count['too_large']) + " | Ratio: " + str(rejected_count['bad_ratio'])
        cv2.putText(frame, debug_text2, (20, 120), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        
        if len(valid_dashes) == 0:
            cv2.putText(frame, "Pas de ligne valide apres filtrage", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            print("[LINE_DETECTOR] Aucun pointillé valide après filtrage -> retourne None")
            return None
        
        # 5. Grouper les pointillés alignés verticalement
        X_TOLERANCE = width * 0.25  # AUGMENTÉ: 25% de tolérance
        
        best_group = []
        
        for dash in valid_dashes:
            group = [dash]
            base_cx = dash['cx']
            
            for other_dash in valid_dashes:
                if other_dash is dash:
                    continue
                if abs(other_dash['cx'] - base_cx) < X_TOLERANCE:
                    group.append(other_dash)
            
            if len(group) > len(best_group):
                best_group = group
        
        # DEBUG: Afficher le nombre de pointillés dans le meilleur groupe
        debug_text3 = "Meilleur groupe: " + str(len(best_group)) + " pointilles"
        cv2.putText(frame, debug_text3, (20, 140), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        
        # CHANGEMENT: Accepter un seul pointillé si c'est tout ce qu'on a
        if len(best_group) < 1:
            cv2.putText(frame, "Aucun pointille trouve", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 2)
            print("[LINE_DETECTOR] Aucun groupe de pointillés valide -> retourne None")
            return None
        
        # 6. Calculer le centre moyen
        total_cx = sum([d['cx'] for d in best_group])
        total_cy = sum([d['cy'] for d in best_group])
        avg_cx = int(total_cx / len(best_group))
        avg_cy = int(total_cy / len(best_group)) + offset_y
        
        offset = avg_cx - (width / 2)
        
        # Dessin pour debug
        for dash in best_group:
            x, y, w, h = dash['x'], dash['y'], dash['w'], dash['h']
            # Rectangle VERT autour des pointillés valides (dans le groupe)
            cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (0, 255, 0), 2)
        
        # Autres pointillés valides non retenus en jaune
        for dash in valid_dashes:
            if dash not in best_group:
                x, y, w, h = dash['x'], dash['y'], dash['w'], dash['h']
                cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (0, 255, 255), 1)
        
        # Cercle rouge au centre moyen
        cv2.circle(frame, (avg_cx, avg_cy), 10, (0, 0, 255), -1)
        
        # Ligne verte au centre de l'image (cible)
        cv2.line(frame, (int(width/2), 0), (int(width/2), height), (0, 255, 0), 2)
        
        # Ligne cyan montrant la position détectée
        cv2.line(frame, (avg_cx, 0), (avg_cx, height), (0, 255, 255), 2)
        
        # Texte avec offset
        text = "Offset: " + str(int(offset)) + " (Points: " + str(len(best_group)) + ")"
        cv2.putText(frame, text, (20, 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Afficher le seuil
        threshold_text = "Seuil: " + str(self.white_threshold)
        cv2.putText(frame, threshold_text, (20, 70), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        print("[LINE_DETECTOR] Ligne détectée! offset={:.1f}, {} pointillés dans le groupe".format(offset, len(best_group)))
        return offset
