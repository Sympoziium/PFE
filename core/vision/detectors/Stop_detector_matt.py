#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_matt.py
# ------------------
# Détecteur de panneau STOP basé sur l'approche de Matt (hsv_matt.py)
# avec analyse avancée des ratios rouge/blanc et détection des bordures blanches.

import cv2
import numpy as np
import os
import uuid
from flask import url_for

from .detector_base import BaseDetector


class StopDetectorMatt(BaseDetector):
    """
    Détecteur de panneau STOP utilisant une approche avancée:
    - Segmentation des zones rouges en HSV
    - Analyse du ratio rouge/blanc
    - Détection du texte blanc au centre
    - Détection de la bordure blanche
    - Score de confiance composite
    """

    def __init__(self, min_area=400, min_score=0.35):
        """
        Args:
            min_area (int): Aire minimale du contour pour être considéré
            min_score (float): Score de confiance minimum pour valider une détection
        """
        self.min_area = int(min_area)
        self.min_score = float(min_score)
        self.name = "StopDetectorMatt"
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        self.steps = []  # pour stocker les étapes de diagnostic
        self.logs = []   # pour stocker les logs de diagnostic

    def atach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process(self, frame, filename=None):
        """
        Analyse une image BGR et retourne un dict de résultat.

        Returns:
            dict: {
                "source_file_url": str,
                "overlay_url": str,
                "Stop_detected": bool,
                "best": dict with bbox and confidence,
                "detection_box": tuple or None,
                "confidence": float,
                "logs": list
            }
        """
        # Réinitialiser
        self.steps = []
        self.logs = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        # Créer le dossier de diagnostics
        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            # Charger l'image
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            # Détection
            detections = self._detect_stop_signs(frame_bgr)

            # Créer l'overlay avec les détections
            overlay = frame_bgr.copy()
            best_detection = None

            for (x, y, w, h, conf) in detections:
                # Dessiner les détections
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(overlay, "STOP {:.0%}".format(conf), (x, y - 8),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                # Garder la meilleure détection
                if best_detection is None:
                    best_detection = (x, y, w, h, conf)
                    self.logs.append('Best detection: x={}, y={}, w={}, h={}, confidence={:.2%}'.format(x, y, w, h, conf))

            # Sauvegarder l'overlay
            self._save_step(overlay, 'final_detections', mode='bgr')

            # Formater la réponse
            source_url = url_for('static', filename='captured_images/{}'.format(filename))

            if best_detection:
                x, y, w, h, conf = best_detection
                payload = {
                    'source_file_url': source_url,
                    'overlay_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Stop_detected': True,
                    'best': {
                        'bbox': (x, y, w, h),
                        'confidence': float(conf)
                    },
                    'detection_box': (x, y, w, h),
                    'confidence': float(conf),
                    'logs': self.logs
                }
            else:
                self.logs.append('No stop sign detected.')
                payload = {
                    'source_file_url': source_url,
                    'overlay_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Stop_detected': False,
                    'best': {'bbox': None, 'confidence': 0.0},
                    'detection_box': None,
                    'confidence': 0.0,
                    'logs': self.logs
                }

            return payload

        except Exception as e:
            return {'error': 'process failed', 'details': str(e)}

    def diagnostique_detecteur(self, filename):
        """
        Réalise un diagnostic détaillé avec toutes les étapes intermédiaires.
        """
        # Réinitialiser
        self.steps = []
        self.logs = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            # Étape 0: Image originale
            self._save_step(frame_bgr.copy(), 'original_rgb', mode='bgr')

            # Étape 1: Masque rouge
            red_mask = self._get_red_mask(frame_bgr, diagnostic_mode=True)

            # Étape 2: Détection des contours
            contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            self.logs.append('Found {} contours'.format(len(contours)))

            # Créer une image pour visualiser tous les contours
            all_contours_img = frame_bgr.copy()
            cv2.drawContours(all_contours_img, contours, -1, (255, 0, 0), 2)
            self._save_step(all_contours_img, 'all_contours', mode='bgr')

            # Étape 3: Détection avec diagnostic détaillé
            detections = self._detect_stop_signs(frame_bgr, diagnostic_mode=True)

            # Créer l'overlay final
            overlay = frame_bgr.copy()
            best_detection = None

            for (x, y, w, h, conf) in detections:
                cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), 2)
                cv2.putText(overlay, "STOP {:.0%}".format(conf), (x, y - 8),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                if best_detection is None:
                    best_detection = (x, y, w, h, conf)

            self._save_step(overlay, 'final_detections', mode='bgr')

            # Formater la réponse
            source_url = url_for('static', filename='captured_images/{}'.format(filename))

            if best_detection:
                x, y, w, h, conf = best_detection
                payload = {
                    'source_file_url': source_url,
                    'overlay_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Stop_detected': True,
                    'best': {'bbox': (x, y, w, h), 'confidence': float(conf)},
                    'detection_box': (x, y, w, h),
                    'confidence': float(conf),
                    'logs': self.logs
                }
            else:
                payload = {
                    'source_file_url': source_url,
                    'overlay_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Stop_detected': False,
                    'best': {'bbox': None, 'confidence': 0.0},
                    'detection_box': None,
                    'confidence': 0.0,
                    'logs': self.logs
                }

            return payload

        except Exception as e:
            return {'error': 'diagnostic failed', 'details': str(e)}

    # ========== Méthodes internes de détection (adaptées de hsv_matt.py) ==========

    def _get_red_mask(self, frame, diagnostic_mode=False):
        """Crée un masque binaire pour les zones rouges."""
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        if diagnostic_mode:
            # Sauvegarder les canaux HSV
            h, s, v = cv2.split(hsv)
            self._save_step(h, 'h_channel', mode='gray')
            self._save_step(s, 's_channel', mode='gray')
            self._save_step(v, 'v_channel', mode='gray')

        # Masques pour le rouge (autour de 0° et 180°)
        mask_lo = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        mask_hi = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        mask = cv2.bitwise_or(mask_lo, mask_hi)

        if diagnostic_mode:
            self._save_step(mask_lo, 'red_mask_low', mode='gray')
            self._save_step(mask_hi, 'red_mask_high', mode='gray')
            self._save_step(mask, 'red_mask_combined', mode='gray')

        # Morphologie
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        if diagnostic_mode:
            self._save_step(mask, 'red_mask_morpho', mode='gray')

        return mask

    def _analyze_red_blob(self, frame, x, y, w, h, diagnostic_mode=False):
        """
        Analyse un blob rouge pour détecter les caractéristiques d'un panneau stop.
        Retourne un dict de scores.
        """
        img_h, img_w = frame.shape[:2]

        # Clamper le ROI
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_w, x + w)
        y2 = min(img_h, y + h)
        roi = frame[y1:y2, x1:x2]

        if roi.size == 0:
            return {"ratio": 0, "center": 0, "edge": 0, "aspect": 0}

        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        rh, rw = roi.shape[:2]
        total_pixels = rh * rw

        # --- Pixels rouges dans le ROI ---
        red_lo = cv2.inRange(hsv_roi, np.array([0, 70, 50]), np.array([10, 255, 255]))
        red_hi = cv2.inRange(hsv_roi, np.array([160, 70, 50]), np.array([180, 255, 255]))
        red_mask = cv2.bitwise_or(red_lo, red_hi)
        red_count = cv2.countNonZero(red_mask)

        # --- Pixels blancs dans le ROI ---
        white_mask = cv2.inRange(hsv_roi, np.array([0, 0, 140]), np.array([180, 70, 255]))
        white_count = cv2.countNonZero(white_mask)

        if diagnostic_mode:
            # Sauvegarder les masques de l'analyse
            roi_bgr = frame[y1:y2, x1:x2].copy()
            red_overlay = cv2.cvtColor(red_mask, cv2.COLOR_GRAY2BGR)
            white_overlay = cv2.cvtColor(white_mask, cv2.COLOR_GRAY2BGR)
            self._save_step(roi_bgr, 'roi_x{}_y{}'.format(x, y), mode='bgr')
            self._save_step(red_overlay, 'roi_red_mask_x{}_y{}'.format(x, y), mode='bgr')
            self._save_step(white_overlay, 'roi_white_mask_x{}_y{}'.format(x, y), mode='bgr')

        # 1) Ratio rouge/blanc
        red_ratio = red_count / total_pixels if total_pixels > 0 else 0
        white_ratio = white_count / total_pixels if total_pixels > 0 else 0
        ratio_score = 0.0
        if 0.3 < red_ratio < 0.85 and 0.08 < white_ratio < 0.45:
            ratio_score = min(1.0, white_ratio * 4.0)

        # 2) Blanc concentré au centre (zone de texte)
        cy1 = int(rh * 0.25)
        cy2 = int(rh * 0.75)
        cx1 = int(rw * 0.25)
        cx2 = int(rw * 0.75)
        center_region = white_mask[cy1:cy2, cx1:cx2]
        center_total = center_region.size
        center_white = cv2.countNonZero(center_region) if center_total > 0 else 0
        center_ratio = center_white / center_total if center_total > 0 else 0

        outer_white = white_count - center_white
        outer_total = total_pixels - center_total
        outer_ratio = outer_white / outer_total if outer_total > 0 else 0

        center_score = 0.0
        if center_ratio > 0.10:
            center_score = min(1.0, center_ratio * 3.0)
            if center_ratio > outer_ratio:
                center_score = min(1.0, center_score + 0.15)

        # 3) Bordure blanche autour du blob rouge
        pad = max(3, int(min(w, h) * 0.15))
        ex1 = max(0, x - pad)
        ey1 = max(0, y - pad)
        ex2 = min(img_w, x + w + pad)
        ey2 = min(img_h, y + h + pad)

        # Créer un masque de bordure
        border_mask = np.zeros((img_h, img_w), dtype=np.uint8)
        cv2.rectangle(border_mask, (ex1, ey1), (ex2, ey2), 255, -1)
        cv2.rectangle(border_mask, (x1 + 2, y1 + 2), (x2 - 2, y2 - 2), 0, -1)

        hsv_full = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_full = cv2.inRange(hsv_full, np.array([0, 0, 140]), np.array([180, 70, 255]))
        border_pixels = cv2.countNonZero(border_mask)
        border_white = cv2.countNonZero(cv2.bitwise_and(white_full, border_mask))
        edge_ratio = border_white / border_pixels if border_pixels > 0 else 0

        edge_score = 0.0
        if edge_ratio > 0.06:
            edge_score = min(1.0, edge_ratio * 4.0)

        # 4) Aspect ratio (panneaux stop sont carrés)
        aspect = w / float(h) if h > 0 else 0
        aspect_score = max(0, 1.0 - abs(aspect - 1.0) * 2.0)

        self.logs.append('  Blob analysis: red_ratio={:.2f}, white_ratio={:.2f}, '
                        'center_score={:.2f}, edge_score={:.2f}, aspect_score={:.2f}'.format(
                            red_ratio, white_ratio, center_score, edge_score, aspect_score))

        return {
            "ratio": ratio_score,
            "center": center_score,
            "edge": edge_score,
            "aspect": aspect_score,
        }

    def _detect_stop_signs(self, frame, diagnostic_mode=False):
        """
        Détecte les panneaux stop dans une image.
        Retourne une liste de détections: [(x, y, w, h, confidence), ...]
        """
        red_mask = self._get_red_mask(frame, diagnostic_mode=diagnostic_mode)
        contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        detections = []
        self.logs.append('Analyzing {} contours...'.format(len(contours)))

        for idx, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue

            # Solidité: rejeter les blobs très irréguliers
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < 0.45:
                self.logs.append('  Contour {}: rejected (low solidity={:.2f})'.format(idx, solidity))
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Aspect ratio rapide
            aspect = w / float(h) if h > 0 else 0
            if aspect < 0.5 or aspect > 2.0:
                self.logs.append('  Contour {}: rejected (bad aspect={:.2f})'.format(idx, aspect))
                continue

            # Rejeter les blobs trop grands
            if w > frame.shape[1] * 0.4 or h > frame.shape[0] * 0.4:
                self.logs.append('  Contour {}: rejected (too large)'.format(idx))
                continue

            # Densité rouge
            bbox_area = w * h
            red_density = area / bbox_area if bbox_area > 0 else 0
            if red_density < 0.3:
                self.logs.append('  Contour {}: rejected (low red density={:.2f})'.format(idx, red_density))
                continue

            # Analyse approfondie
            scores = self._analyze_red_blob(frame, x, y, w, h, diagnostic_mode=diagnostic_mode)

            # Calcul de la confiance
            confidence = (
                scores["ratio"] * 0.30
                + scores["center"] * 0.30
                + scores["edge"] * 0.20
                + scores["aspect"] * 0.10
                + min(0.10, area / 15000)  # bonus de taille
            )
            confidence = round(min(1.0, confidence), 2)

            self.logs.append('  Contour {}: confidence={:.2f} '
                           '(area={}, solidity={:.2f})'.format(idx, confidence, int(area), solidity))

            if confidence < self.min_score:
                self.logs.append('  Contour {}: rejected (confidence={:.2f} < {})'.format(
                    idx, confidence, self.min_score))
                continue

            detections.append((x, y, w, h, confidence))

        # Trier par confiance (meilleure en premier)
        detections.sort(key=lambda d: d[4], reverse=True)

        if detections:
            self.logs.append('Found {} valid detection(s)'.format(len(detections)))
        else:
            self.logs.append('No valid detections found')

        return detections

    def _save_step(self, img, name, mode):
        """
        Sauvegarde une image intermédiaire pour le diagnostic.
        mode: 'bgr', 'gray', 'hsv', 'RGB'
        """
        base = 'Diag_Stop_Detector_Matt_{}_{}'.format(name, uuid.uuid4().hex[:6])
        out_name = base + '.jpg'
        out_path = os.path.join(self.DIAGNOSTIC_DIR, out_name)

        if mode == 'bgr':
            to_save = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif mode == 'gray':
            to_save = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif mode == 'hsv':
            to_save = cv2.cvtColor(img, cv2.COLOR_HSV2RGB)
        elif mode == 'RGB':
            to_save = img
        else:
            raise ValueError("Unknown save mode: {}".format(mode))

        cv2.imwrite(out_path, to_save)
        url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
        self.steps.append({"name": name, "url": url})
