#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_cv.py
# ------------------
# Détecteur de panneau STOP basé sur OpenCV (HSV + contours + approximation polygonale).

import cv2
import numpy as np

from .detector_base import BaseDetector


class StopDetectorCV(BaseDetector):

    def __init__(self, min_area=500, aspect_tol=0.35, poly_min=6, poly_max=10):
        """Détecteur de panneau STOP en utilisant une approche simple:
        - Segmentation des zones rouges en HSV
        - Extraction des contours
        - Approximation polygonale pour repérer des formes ~octogonales
        - Filtrage par superficie et ratio largeur/hauteur

        Args:
            min_area (int): aire minimale du contour pour être considéré.
            aspect_tol (float): tolérance sur le ratio (w/h) autour de 1.0.
            poly_min (int): nombre minimum de sommets du polygone approximé.
            poly_max (int): nombre maximum de sommets du polygone approximé.
        """
        self.min_area = int(min_area)
        self.aspect_tol = float(aspect_tol)
        self.poly_min = int(poly_min)
        self.poly_max = int(poly_max)
        self.name = "StopDetectorCV"

    def process(self, frame):
        """Analyse une image BGR et retourne un dict de résultat.

        Returns:
            dict: {
                "Detector": name,
                "Object detected": bool,
                "Object coordinates": (x, y) or None,
                "Object size": (w, h) or None
            }
        """
        try:
            bbox = self._detect_stop_bgr(frame)
        except Exception:
            bbox = None

        if bbox is not None:
            x, y, w, h = bbox
            return {
                "Detector": self.name,
                "Object detected": True,
                "Object coordinates": (int(x), int(y)),
                "Object size": (int(w), int(h)),
            }
        else:
            return {
                "Detector": self.name,
                "Object detected": False,
                "Object coordinates": None,
                "Object size": None,
            }

    def _detect_stop_bgr(self, bgr):
        if bgr is None:
            return None
        # Convertir en HSV
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

        # Masques pour le rouge (autour de 0° et 180°)
        lower1 = np.array([0, 70, 50], dtype=np.uint8)
        upper1 = np.array([10, 255, 255], dtype=np.uint8)
        lower2 = np.array([170, 70, 50], dtype=np.uint8)
        upper2 = np.array([180, 255, 255], dtype=np.uint8)
        mask1 = cv2.inRange(hsv, lower1, upper1)
        mask2 = cv2.inRange(hsv, lower2, upper2)
        mask = cv2.bitwise_or(mask1, mask2)

        # Morphologie pour nettoyer
        kernel3 = np.ones((3, 3), np.uint8)
        kernel5 = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel3, iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel5, iterations=2)

        # Trouver contours
        cnts = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cnts = cnts[0] if len(cnts) == 2 else cnts[1]
        if not cnts:
            return None

        best = None
        best_area = 0

        for c in cnts:
            area = cv2.contourArea(c)
            if area < self.min_area:
                continue
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            vtx = len(approx)
            if vtx < self.poly_min or vtx > self.poly_max:
                continue
            if not cv2.isContourConvex(approx):
                continue
            x, y, w, h = cv2.boundingRect(approx)
            # Ratio largeur/hauteur proche de 1
            if w == 0 or h == 0:
                continue
            ratio = float(w) / float(h)
            if abs(ratio - 1.0) > self.aspect_tol:
                continue
            # Rapports d'aire
            rect_area = float(w * h)
            fill_ratio = float(area) / rect_area if rect_area > 0 else 0.0
            if fill_ratio < 0.30:
                continue
            # Choisir le plus grand
            if area > best_area:
                best_area = area
                best = (x, y, w, h)

        return best