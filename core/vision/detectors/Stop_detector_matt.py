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
import time

try:
    from flask import url_for
except ImportError:
    url_for = None

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

    def __init__(self, min_area=400, min_score=0.35,
                 h_low_min=0, h_low_max=10,
                 h_high_min=160, h_high_max=180,
                 s_min=70, s_max=255,
                 v_min=50, v_max=255):
        """
        Args:
            min_area (int): Aire minimale du contour pour être considéré
            min_score (float): Score de confiance minimum pour valider une détection
            h_low_min (int): Hue minimum pour la plage basse du rouge (défaut: 0)
            h_low_max (int): Hue maximum pour la plage basse du rouge (défaut: 10)
            h_high_min (int): Hue minimum pour la plage haute du rouge (défaut: 160)
            h_high_max (int): Hue maximum pour la plage haute du rouge (défaut: 180)
            s_min (int): Saturation minimum (défaut: 70)
            s_max (int): Saturation maximum (défaut: 255)
            v_min (int): Value minimum (défaut: 50)
            v_max (int): Value maximum (défaut: 255)
        """
        self.min_area = int(min_area)
        self.min_score = float(min_score)

        # Paramètres HSV configurables pour le filtrage du rouge
        self.h_low_min = int(h_low_min)
        self.h_low_max = int(h_low_max)
        self.h_high_min = int(h_high_min)
        self.h_high_max = int(h_high_max)
        self.s_min = int(s_min)
        self.s_max = int(s_max)
        self.v_min = int(v_min)
        self.v_max = int(v_max)

        self.name = "StopDetectorMatt"
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        self.steps = []  # pour stocker les étapes de diagnostic
        self.logs = []   # pour stocker les logs de diagnostic

        # Log des paramètres utilisés
        self._log_config()

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def _log_config(self):
        """Log la configuration actuelle des paramètres HSV."""
        print('[{}] Configuration HSV:'.format(self.name))
        print('  Red Low:  H=[{}, {}], S=[{}, {}], V=[{}, {}]'.format(
            self.h_low_min, self.h_low_max, self.s_min, self.s_max, self.v_min, self.v_max))
        print('  Red High: H=[{}, {}], S=[{}, {}], V=[{}, {}]'.format(
            self.h_high_min, self.h_high_max, self.s_min, self.s_max, self.v_min, self.v_max))
        print('  Detection: min_area={}, min_score={}'.format(self.min_area, self.min_score))

    def process_passive(self, frame):
        """Détection passive optimisée pour le live feed.

        Retourne le format standardisé (sans logs ni disk I/O).
        """
        if frame is None:
            return {'Object_detected': False, 'detections': [], 'timestamp': time.time()}

        try:
            raw_dets = self._detect_stop_signs(frame, diagnostic_mode=False)
            detections = []
            for (x, y, w, h, conf) in raw_dets:
                detections.append({
                    'object': 'Stop Sign',
                    'detection_box': (x, y, w, h)
                })
            return {
                'Object_detected': len(detections) > 0,
                'detections': detections,
                'timestamp': time.time()
            }
        except Exception:
            return {'Object_detected': False, 'detections': [], 'timestamp': time.time()}

    def process(self, frame, filename=None):
        """Analyse une image BGR et retourne un dict de résultat standardisé.

        Returns:
            dict: {
                'Object_detected': bool,
                'detections': [{object, detection_box, confidence?}, ...],
                'logs': list
            }
        """
        # Réinitialiser
        self.steps = []
        self.logs = []

        # Déterminer l'image source
        if filename and self.CAPTURE_DIR:
            img_path = os.path.join(self.CAPTURE_DIR, filename)
            if not os.path.exists(img_path):
                return {'error': 'last captured image not found on server'}
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}
        else:
            if frame is None:
                return {'error': 'no frame provided'}
            frame_bgr = frame

        try:
            self.logs.append('=== DETECTION STOP DETECTOR MATT ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Config: min_area={}, min_score={}'.format(self.min_area, self.min_score))
            self.logs.append('HSV: H=[{}-{}]+[{}-{}], S=[{}-{}], V=[{}-{}]'.format(
                self.h_low_min, self.h_low_max, self.h_high_min, self.h_high_max,
                self.s_min, self.s_max, self.v_min, self.v_max))

            # Détection
            raw_dets = self._detect_stop_signs(frame_bgr, diagnostic_mode=False)

            # Construire la liste de détections standardisée
            detections = []
            for (x, y, w, h, conf) in raw_dets:
                self.logs.append('Résultat: STOP DÉTECTÉ')
                self.logs.append('  Position: x={}, y={}'.format(x, y))
                self.logs.append('  Taille: w={}, h={}'.format(w, h))
                self.logs.append('  Confiance: {:.1%}'.format(conf))
                detections.append({
                    'object': 'Stop Sign',
                    'detection_box': (x, y, w, h),
                    'confidence': float(conf),
                })

            if not detections:
                self.logs.append('Résultat: Aucun panneau stop détecté')

            self.logs.append('=== FIN DETECTION ===')

            return {
                'Object_detected': len(detections) > 0,
                'detections': detections,
                'logs': self.logs,
            }

        except Exception as e:
            return {'error': 'process failed', 'details': str(e)}

    def diagnostique_detecteur(self, filename):
        """
        Réalise un diagnostic détaillé avec toutes les étapes intermédiaires.

        Returns:
            dict: Format standardisé avec clés 'Object_detected', 'detection_box', 'confidence', 'area', 'logs', 'steps', 'annotated_url'
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

            self.logs.append('=== DIAGNOSTIC STOP DETECTOR MATT ===')
            self.logs.append('Image dimensions: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Configuration: min_area={}, min_score={}'.format(self.min_area, self.min_score))

            # Étape 0: Image originale
            self._save_step(frame_bgr.copy(), 'original_rgb', mode='bgr')

            # Étape 1: Détection des zones rouges
            self.logs.append('--- Étape 1: Segmentation HSV du rouge ---')
            red_mask = self._get_red_mask(frame_bgr, diagnostic_mode=True)
            self.logs.append('Filtres HSV: H=[{}-{}]+[{}-{}], S=[{}-{}], V=[{}-{}]'.format(
                self.h_low_min, self.h_low_max, self.h_high_min, self.h_high_max,
                self.s_min, self.s_max, self.v_min, self.v_max))

            # Étape 2: Détection des contours
            self.logs.append('--- Étape 2: Extraction des contours ---')
            result = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = result[0] if len(result) == 2 else result[1]
            self.logs.append('Contours trouvés: {}'.format(len(contours)))

            # Visualiser tous les contours
            all_contours_img = frame_bgr.copy()
            cv2.drawContours(all_contours_img, contours, -1, (255, 0, 0), 2)
            self._save_step(all_contours_img, 'all_contours', mode='bgr')

            # Étape 3: Analyse approfondie et détection
            self.logs.append('--- Étape 3: Analyse des candidats ---')
            # Passer red_mask et contours déjà calculés pour éviter recalcul
            detections = self._detect_stop_signs(frame_bgr, red_mask, contours, diagnostic_mode=True)

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

            # Formater la réponse avec format standardisé
            source_url = url_for('static', filename='captured_images/{}'.format(filename))

            if best_detection:
                x, y, w, h, conf = best_detection
                area = w * h
                payload = {
                    'source_file_url': source_url,
                    'annotated_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Object_detected': True,
                    'detection_box': (x, y, w, h),
                    'confidence': float(conf),
                    'area': area,
                    'logs': self.logs
                }
            else:
                payload = {
                    'source_file_url': source_url,
                    'annotated_url': self.steps[-1]['url'] if self.steps else None,
                    'steps': self.steps,
                    'Object_detected': False,
                    'detection_box': None,
                    'confidence': 0.0,
                    'area': 0,
                    'logs': self.logs
                }

            self.logs.append('=== FIN DIAGNOSTIC ===')
            return payload

        except Exception as e:
            import traceback
            traceback.print_exc()
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

        # Masques pour le rouge (utilise les paramètres configurables)
        mask_lo = cv2.inRange(hsv,
                             np.array([self.h_low_min, self.s_min, self.v_min]),
                             np.array([self.h_low_max, self.s_max, self.v_max]))
        mask_hi = cv2.inRange(hsv,
                             np.array([self.h_high_min, self.s_min, self.v_min]),
                             np.array([self.h_high_max, self.s_max, self.v_max]))
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

    def _analyze_red_blob(self, frame, x, y, w, h, hsv_frame=None, white_frame=None, diagnostic_mode=False):
        """
        Analyse un blob rouge pour détecter les caractéristiques d'un panneau stop.
        Retourne un dict de scores.

        Args:
            frame: Image BGR
            x, y, w, h: Coordonnées du blob
            hsv_frame: Image HSV précalculée (optionnel, pour performance)
            white_frame: Masque blanc précalculé (optionnel, pour performance)
            diagnostic_mode: Mode diagnostic
        """
        img_h, img_w = frame.shape[:2]

        # Clamper le ROI
        x1 = max(0, x)
        y1 = max(0, y)
        x2 = min(img_w, x + w)
        y2 = min(img_h, y + h)
        roi = frame[y1:y2, x1:x2]

        if roi.size == 0:
            return {"ratio": 0, "center": 0, "edge": 0, "aspect": 0, "purity": 0}

        # Utiliser les valeurs précalculées ou calculer si non fournies
        hsv_full = hsv_frame if hsv_frame is not None else cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_full = white_frame if white_frame is not None else cv2.inRange(hsv_full, np.array([0, 0, 140]), np.array([180, 70, 255]))

        hsv_roi = hsv_full[y1:y2, x1:x2]
        rh, rw = roi.shape[:2]
        total_pixels = rh * rw

        # --- Pixels rouges dans le ROI (utilise les paramètres configurables) ---
        red_lo = cv2.inRange(hsv_roi,
                            np.array([self.h_low_min, self.s_min, self.v_min]),
                            np.array([self.h_low_max, self.s_max, self.v_max]))
        red_hi = cv2.inRange(hsv_roi,
                            np.array([self.h_high_min, self.s_min, self.v_min]),
                            np.array([self.h_high_max, self.s_max, self.v_max]))
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

        # 3) Bordure blanche autour du blob rouge - Vérification multi-côtés
        # Les panneaux stop ont une bordure blanche sur tous les côtés
        pad = max(5, int(min(w, h) * 0.20))
        ex1 = max(0, x - pad)
        ey1 = max(0, y - pad)
        ex2 = min(img_w, x + w + pad)
        ey2 = min(img_h, y + h + pad)

        sides_with_white = 0
        side_threshold = 0.06

        # Haut
        top_strip = white_full[ey1:y1, ex1:ex2]
        if top_strip.size > 0 and cv2.countNonZero(top_strip) / max(1, top_strip.size) > side_threshold:
            sides_with_white += 1

        # Bas
        bot_strip = white_full[y2:ey2, ex1:ex2]
        if bot_strip.size > 0 and cv2.countNonZero(bot_strip) / max(1, bot_strip.size) > side_threshold:
            sides_with_white += 1

        # Gauche
        left_strip = white_full[ey1:ey2, ex1:x1]
        if left_strip.size > 0 and cv2.countNonZero(left_strip) / max(1, left_strip.size) > side_threshold:
            sides_with_white += 1

        # Droite
        right_strip = white_full[ey1:ey2, x2:ex2]
        if right_strip.size > 0 and cv2.countNonZero(right_strip) / max(1, right_strip.size) > side_threshold:
            sides_with_white += 1

        edge_score = sides_with_white / 4.0  # 0.0 à 1.0 selon le nombre de côtés avec du blanc

        # 4) Aspect ratio (panneaux stop sont carrés)
        aspect = w / float(h) if h > 0 else 0
        aspect_score = max(0, 1.0 - abs(aspect - 1.0) * 2.0)

        # 5) Pureté des couleurs: les panneaux stop sont SEULEMENT rouge + blanc + un peu de noir
        dark_mask = cv2.inRange(hsv_roi, np.array([0, 0, 0]), np.array([180, 255, 50]))
        red_white_dark = red_count + white_count + cv2.countNonZero(dark_mask)
        other_color_ratio = 1.0 - (red_white_dark / total_pixels) if total_pixels > 0 else 0
        # Panneau stop: other_color_ratio devrait être très bas (<15%)
        purity_score = max(0, 1.0 - other_color_ratio * 5.0)

        self.logs.append('  Blob analysis: red_ratio={:.2f}, white_ratio={:.2f}, '
                        'center_score={:.2f}, edge_score={:.2f}, aspect_score={:.2f}, purity_score={:.2f}'.format(
                            red_ratio, white_ratio, center_score, edge_score, aspect_score, purity_score))

        return {
            "ratio": ratio_score,
            "center": center_score,
            "edge": edge_score,
            "aspect": aspect_score,
            "purity": purity_score,
        }

    def _detect_stop_signs(self, frame, red_mask=None, contours=None, diagnostic_mode=False):
        """
        Détecte les panneaux stop dans une image.

        Args:
            frame: Image BGR
            red_mask: Masque rouge précalculé (optionnel, pour éviter recalcul)
            contours: Contours précalculés (optionnel, pour éviter recalcul)
            diagnostic_mode: Mode diagnostic

        Retourne une liste de détections: [(x, y, w, h, confidence), ...]
        """
        # Utiliser le masque précalculé ou le calculer
        if red_mask is None:
            red_mask = self._get_red_mask(frame, diagnostic_mode=diagnostic_mode)

        # Utiliser les contours précalculés ou les extraire
        if contours is None:
            result = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            # Compatibilité OpenCV 3.x (3 valeurs) et 4.x (2 valeurs)
            contours = result[0] if len(result) == 2 else result[1]

        # Précalculer une seule fois pour toute l'image (optimisation)
        hsv_full = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_full = cv2.inRange(hsv_full, np.array([0, 0, 140]), np.array([180, 70, 255]))

        detections = []
        self.logs.append('Analyzing {} contours...'.format(len(contours)))

        for idx, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                self.logs.append('  Contour {}: rejeté - aire trop petite ({} < {})'.format(idx, int(area), self.min_area))
                continue

            # Solidité: rejeter les blobs très irréguliers
            hull = cv2.convexHull(cnt)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < 0.45:
                self.logs.append('  Contour {}: rejeté - solidité trop faible ({:.2f} < 0.45)'.format(idx, solidity))
                continue

            x, y, w, h = cv2.boundingRect(cnt)

            # Aspect ratio rapide
            aspect = w / float(h) if h > 0 else 0
            if aspect < 0.65 or aspect > 1.5:
                self.logs.append('  Contour {}: rejeté - aspect ratio hors limites ({:.2f} pas dans [0.65, 1.5])'.format(idx, aspect))
                continue

            # Rejeter les blobs trop grands
            if w > frame.shape[1] * 0.4 or h > frame.shape[0] * 0.4:
                self.logs.append('  Contour {}: rejeté - dimensions trop grandes (w={} h={}, max=40% image)'.format(idx, w, h))
                continue

            # Densité rouge
            bbox_area = w * h
            red_density = area / bbox_area if bbox_area > 0 else 0
            if red_density < 0.3:
                self.logs.append('  Contour {}: rejeté - densité rouge trop faible ({:.2f} < 0.3)'.format(idx, red_density))
                continue

            # Analyse approfondie
            scores = self._analyze_red_blob(frame, x, y, w, h, hsv_full, white_full, diagnostic_mode)

            # Calcul de la confiance avec poids ajustés
            # Note: purity_score a 20% de poids - pas de hard gate pour éviter faux négatifs
            confidence = (
                scores["ratio"] * 0.15      # Réduit de 0.30
                + scores["center"] * 0.15   # Réduit de 0.30
                + scores["edge"] * 0.25     # Augmenté de 0.20
                + scores["aspect"] * 0.15   # Augmenté de 0.10
                + scores["purity"] * 0.20   # NOUVEAU - soft gate seulement
                + min(0.10, area / 15000)   # bonus de taille
            )
            confidence = round(min(1.0, confidence), 2)

            self.logs.append('  Contour {}: confiance={:.2f} (aire={}, solidité={:.2f})'.format(
                idx, confidence, int(area), solidity))

            if confidence < self.min_score:
                self.logs.append('  → Rejeté: confiance insuffisante ({:.2f} < {})'.format(confidence, self.min_score))
                continue

            self.logs.append('  ✓ Accepté comme détection valide')
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
        cv2.imwrite() attend du BGR, donc on convertit tout vers BGR avant sauvegarde.

        mode:
        'bgr'   -> image BGR OpenCV (deja en BGR, pas de conversion)
        'gray'  -> image 1 canal (converti vers BGR 3 canaux)
        'hsv'   -> image HSV (convertie vers BGR)
        'RGB'   -> image RGB (convertie vers BGR)
        """
        base = 'Diag_Stop_Detector_Matt_{}_{}'.format(name, uuid.uuid4().hex[:6])
        out_name = base + '.jpg'
        out_path = os.path.join(self.DIAGNOSTIC_DIR, out_name)

        if mode == 'bgr':
            to_save = img  # Deja en BGR, pas de conversion
        elif mode == 'gray':
            to_save = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)  # 1 canal -> 3 canaux BGR
        elif mode == 'hsv':
            to_save = cv2.cvtColor(img, cv2.COLOR_HSV2BGR)  # HSV -> BGR
        elif mode == 'RGB':
            to_save = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)  # RGB -> BGR
        else:
            raise ValueError("Unknown save mode: {}".format(mode))

        cv2.imwrite(out_path, to_save)  # imwrite attend BGR
        url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
        self.steps.append({"name": name, "url": url})

