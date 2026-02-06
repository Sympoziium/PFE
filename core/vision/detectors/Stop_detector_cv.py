#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_cv.py
# ------------------
# Détecteur de panneau STOP basé sur OpenCV (HSV + contours + approximation polygonale).

import cv2
import numpy as np
import os, uuid
from flask import url_for

from .detector_base import BaseDetector


class StopDetectorCV(BaseDetector):

    def __init__(self, min_area=500, aspect_tol=0.35, poly_min=5, poly_max=10, h_min=15, w_min=15, fill_ratio_min=0.5):
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
            h_min (int): hauteur minimale du contour pour être considéré.
            w_min (int): largeur minimale du contour pour être considéré.
            fill_ratio_min (float): ratio aire/boîte englobante minimale.
        """
        self.min_area = int(min_area)
        self.aspect_tol = float(aspect_tol)
        self.poly_min = int(poly_min)
        self.poly_max = int(poly_max)
        self.h_min = int(h_min)
        self.w_min = int(w_min)
        self.fill_ratio_min = float(fill_ratio_min)  # ratio aire/boîte englobante minimale
        self.name = "StopDetectorCV"
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        self.steps = []  # pour stocker les étapes de diagnostique
        self.logs = []   # pour stocker les logs de diagnostique

    def atach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process(self, frame, filename=None):
        """Analyse une image BGR et retourne un dict de résultat.

        Returns:
            dict: {
                "Detector": name,
                "Object detected": bool,
                "Object coordinates": (x, y) or None,
                "Object size": (w, h) or None
            }
        """

        
        # Réinitialiser et valider l'entrée
        self.steps = []
        self.logs = []
        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        # Crée le dossier de diagnostics s'il n'existe pas (on y stoque les images intermédiaires)
        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            # Charger l'image capturée
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            self.logs.append('=== DETECTION STOP DETECTOR CV ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Config: min_area={}, aspect_tol={}, poly=[{}-{}]'.format(
                self.min_area, self.aspect_tol, self.poly_min, self.poly_max))
            self.logs.append('HSV: H=[0-10]+[160-180], S=[70-255], V=[50-255]')

            # Étape 2: Conversion en HSV et séparation des canaux
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            mask = self._make_HSV_mask(hsv)
            mask = self._fill_holes(mask) # remplir les trous laisser par le texte du panneau

            # Étape 3: Opérations morphologiques pour nettoyage et reconstruction de l'image
            mask_morpho = self._make_morphological_mask(mask)

            # Étape 4: Détection des contours sur le masque final
            Image_traitée = mask_morpho.copy()
            contours = self._detect_contours(Image_traitée)

            # Étape 5: Analyse des contours et détection finale
            results = self._analyse_detections(contours, frame_bgr)

            # Étape 6: Formatage de la réponse JSON
            source_url = url_for('static', filename='captured_images/{}'.format(filename))

            # Ajouter le résultat aux logs
            if results.get('detected'):
                bbox = results.get('detection_box')
                if bbox:
                    x, y, w, h = bbox
                    self.logs.append('Résultat: STOP DÉTECTÉ')
                    self.logs.append('  Position: x={}, y={}'.format(x, y))
                    self.logs.append('  Taille: w={}, h={}'.format(w, h))
                    self.logs.append('  Aire: {}'.format(results.get('area', 0)))
            else:
                self.logs.append('Résultat: Aucun panneau stop détecté')

            self.logs.append('=== FIN DETECTION ===')

            payload = {
                'source_file_url': source_url,
                'overlay_url': self.steps[-1]['url'] if self.steps else None,
                'steps': self.steps,
                'Stop_detected': bool(results.get('detected')),
                'best': {'bbox': results.get('detection_box'), 'area': int(results.get('area', 0))},
                'detection_box': results.get('detection_box'),
                'area': int(results.get('area', 0)),
                'logs': self.logs
            }

            return payload
        
        except Exception as e:
            return {'error': 'diagnose_stop_cv failed', 'details': str(e)}
        # try:
        #     print("Processing frame in StopDetectorCV...")
        #     bbox = self._detect_stop_bgr(frame)
        # except Exception:
        #     bbox = None

        # if bbox is not None:
        #     x, y, w, h = bbox
        #     return {
        #         "Detector": self.name,
        #         "Object detected": True,
        #         "Object coordinates": (int(x), int(y)),
        #         "Object size": (int(w), int(h)),
        #     }
        # else:
        #     return {
        #         "Detector": self.name,
        #         "Object detected": False,
        #         "Object coordinates": None,
        #         "Object size": None,
        #     }



    # Fonction de détection interne buggé
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
    
    # Diagnostic CV du stop: export des étapes intermédiaires (HSV, masques, morpho, contours)
    def diagnostique_detecteur(self, filename):
        """
        Réalise un diagnostique détaillé du détecteur Stop CV sur la dernière image capturée.
        Retourne un JSON avec les étapes intermédiaires et les résultats. pour afficher dans la console web.
        """
        # Réinitialiser et valider l'entrée
        self.steps = []
        self.logs = []
        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        # Crée le dossier de diagnostics s'il n'existe pas (on y stoque les images intermédiaires)
        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            # Charger l'image capturée
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            self.logs.append('=== DIAGNOSTIC STOP DETECTOR CV ===')
            self.logs.append('Image dimensions: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))

            # Étape 0: Image originale
            self._save_step(frame_bgr.copy(), 'original_rgb', mode='bgr')

            # Étape 1: Conversion en HSV et détection du rouge
            self.logs.append('--- Étape 1: Segmentation HSV du rouge ---')
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            mask = self._make_HSV_mask(hsv, diagnostic_mode=True)
            self.logs.append('Filtres HSV appliqués: H=[0-10] + [160-180], S=[70-255], V=[50-255]')

            # Remplir les trous laissés par le texte du panneau
            mask = self._fill_holes(mask)

            # Étape 2: Opérations morphologiques pour nettoyage
            self.logs.append('--- Étape 2: Nettoyage morphologique ---')
            mask_morpho = self._make_morphological_mask(mask, diagnostic_mode=True)
            self.logs.append('Morphologie: OPEN + CLOSE pour nettoyer et reconstruire')

            # Étape 3: Détection des contours
            self.logs.append('--- Étape 3: Détection des contours ---')
            Image_traitée = mask_morpho.copy()
            contours = self._detect_contours(Image_traitée)

            # Étape 4: Analyse des contours et détection finale
            self.logs.append('--- Étape 4: Analyse des contours ---')
            results = self._analyse_detections(contours, frame_bgr)

            # Étape 5: Formatage de la réponse JSON
            source_url = url_for('static', filename='captured_images/{}'.format(filename))

            payload = {
                'source_file_url': source_url,
                'overlay_url': self.steps[-1]['url'] if self.steps else None,
                'steps': self.steps,
                'Stop_detected': bool(results.get('detected')),
                'best': {'bbox': results.get('detection_box'), 'area': int(results.get('area', 0))},
                'detection_box': results.get('detection_box'),
                'area': int(results.get('area', 0)),
                'logs': self.logs
            }

            self.logs.append('=== FIN DIAGNOSTIC ===')
            return payload

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'error': 'diagnose_stop_cv failed', 'details': str(e)}

    def _save_step(self, img, name, mode):
        """
        Sauvegarde toutes les images en RGB pour l'affichage web

        mode:
        'bgr'   -> image BGR OpenCV
        'gray'  -> image 1 canal
        'hsv'   -> image HSV (sera convertie pour affichage)
        
        """
        print("Saving step: {} ({})".format(name, mode))

        base = 'Diag_Stop_Detector_CV_{}_{}'.format(name, uuid.uuid4().hex[:6])
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

    def _make_HSV_mask(self, hsv, diagnostic_mode=False):
        """Crée un masque binaire pour les zones rouges dans une image HSV.

        Utilise la méthode conventionnelle avec double plage pour le rouge:
        - Plage basse: H=[0, 10] (rouge autour de 0°)
        - Plage haute: H=[160, 180] (rouge autour de 180°)
        """

        if hsv is None:
            raise ValueError('No image provided for HSV masking')

        # Étape 1: Séparation des canaux HSV
        h, s, v = cv2.split(hsv)

        if diagnostic_mode:
            # Sauvegarde des canaux HSV
            self._save_step(h, 'h_channel', mode='gray')
            self._save_step(s, 's_channel', mode='gray')
            self._save_step(v, 'v_channel', mode='gray')

        # Étape 2: Filtrage conventionnel du rouge en HSV
        # Double plage pour capturer le rouge qui wrappe autour de 0/180
        mask_red_low = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        mask_red_high = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))

        if diagnostic_mode:
            self._save_step(mask_red_low, 'red_mask_low', 'gray')
            self._save_step(mask_red_high, 'red_mask_high', 'gray')

        # Combinaison des deux masques
        mask = cv2.bitwise_or(mask_red_low, mask_red_high)

        # Sauvegarde du masque initial
        if diagnostic_mode:
            self._save_step(mask, 'red_mask_combined', mode='gray')

        return mask
    
    def _fill_holes(self, mask):
        h, w = mask.shape
        flood = mask.copy()

        # Masque pour floodFill (obligatoire: +2 pixels)
        ff_mask = np.zeros((h+2, w+2), np.uint8)

        cv2.floodFill(flood, ff_mask, (0, 0), 255)
        flood_inv = cv2.bitwise_not(flood)

        return mask | flood_inv

    
    def _make_morphological_mask(self, mask, diagnostic_mode=False):
        """
        Docstring for _make_morphological_mask
        
        :param mask: Description
        :param diagnostic_mode: Description
        """
        # A. Définition des kernels pour la morphologie
        kernel_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7,7))
                    
        # B. Appliquer les opérations morphologiques
            # I. Nettoyage du bruit
        mask_open = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel_open, iterations=3)

            # II. Reconstruction du panneau
        mask_close = cv2.morphologyEx(mask_open, cv2.MORPH_CLOSE, kernel_close, iterations=4)
        
        if diagnostic_mode:
            # Sauvegarde des masques morphologiques
            self._save_step(mask_open, 'mask_open', mode='gray')
            self._save_step(mask_close, 'mask_close', mode='gray')

        return mask_close
    
    def _detect_contours(self, mask):
        """
        Docstring for _detect_contours
        
        :param mask: Description
        """
        # Trouver les contours (compatibilité OpenCV 3/4)
        result = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(result) == 2:
            contours, hierarchy = result
        elif len(result) == 3:
            _, contours, hierarchy = result
        else:
            contours, hierarchy = [], None

        if hierarchy is None or (hasattr(hierarchy, '__len__') and len(hierarchy) == 0):
            print("No contours found. Hierarchy is empty. voir classe StopDetectorCV méthode _detect_contours") # pour debug retirer plus tard
            self.logs.append('No contours detected.')
            return []
        else:
            self.logs.append('Contours found: {}'.format(len(contours)))
     
        return contours

    def _analyse_detections(self, contours, frame_bgr):
        """
        Docstring for _analyse_detections
        
        :param contours: Description
        :param frame_bgr: Description
        """
        overlay = frame_bgr.copy()
        detection_box = None
        best_area = 0
        best_gess_idx = -1
        # Résumé final
        summary = {'detected': False, 'detection_box': None, 'area': 0}

        for idx, c in enumerate(contours):
            # --- Calcul des caractéristiques du contour ---
            area = cv2.contourArea(c)                                           # Aire du contour
            if area < 1:
                continue

            peri = cv2.arcLength(c, True)                                       # Périmètre du contour
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)                     # Approximation polygonale
            vtx = len(approx)                                                   # Nombre de sommets du polygone approximé
            x, y, w, h = cv2.boundingRect(approx)                               # Boîte englobante
            ratio = float(w) / float(h) if h != 0 else 0.0                      # Ratio largeur/hauteur
            rect_area = float(w * h)                                            # Aire de la boîte englobante
            fill_ratio = float(area) / rect_area if rect_area > 0 else 0.0      # Ratio de remplissage de la boîte
            convex = cv2.isContourConvex(approx)                                # Convexité du contour

            self.logs.append('C{}: area={} vtx={} ratio={:.2f} fill={:.2f} convex={}'.format(idx, int(area), vtx, ratio, fill_ratio, bool(convex)))

            # Dessin du contour détecté
            cv2.drawContours(overlay, [approx], -1, (255, 0, 0), 2)

            # Vérifications avec messages de rejet explicites
            # Si l'aire est inférieure au minimum, on ignore
            if area < self.min_area:
                self.logs.append('  → Rejeté: aire trop petite ({} < {})'.format(int(area), self.min_area))
                continue

            # Si le nombre de sommets n'est pas dans l'intervalle, on ignore
            if vtx < self.poly_min or vtx > self.poly_max:
                self.logs.append('  → Rejeté: nb sommets hors intervalle ({} pas dans [{}, {}])'.format(vtx, self.poly_min, self.poly_max))
                continue

            # Si le contour n'est pas suffisamment convexe, on ignore
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            solidity = area / hull_area if hull_area > 0 else 0
            if solidity < 0.85:
                self.logs.append('  → Rejeté: solidité trop faible ({:.2f} < 0.85)'.format(solidity))
                continue

            # Si la boite englobante est trop petite
            if h < self.h_min or w < self.w_min:
                self.logs.append('  → Rejeté: dimensions trop petites (w={} h={}, min={})'.format(w, h, min(self.w_min, self.h_min)))
                continue

            # Si le ratio largeur/hauteur n'est pas proche de 1 (pas assez carré)
            if abs(ratio - 1.0) > float(self.aspect_tol):
                self.logs.append('  → Rejeté: ratio W/H trop éloigné de 1.0 ({:.2f}, tolérance={})'.format(ratio, self.aspect_tol))
                continue

            # Si le ratio de remplissage est trop faible
            if fill_ratio < self.fill_ratio_min:
                self.logs.append('  → Rejeté: ratio de remplissage trop faible ({:.2f} < {})'.format(fill_ratio, self.fill_ratio_min))
                continue

            # Si c'est le plus grand jusqu'à présent, on le garde comme détection
            self.logs.append('  ✓ Accepté comme candidat (aire={})'.format(int(area)))
            if area > best_area:
                best_area = area
                best_gess_idx = idx
                
        
        if best_gess_idx != -1:
            c = contours[best_gess_idx]
            # Recalculer l'approximation et la bounding box du meilleur contour
            peri_best = cv2.arcLength(c, True)
            approx_best = cv2.approxPolyDP(c, 0.02 * peri_best, True)
            x, y, w, h = cv2.boundingRect(approx_best)
            detection_box = (x, y, w, h)
            # Dessiner le rectangle vert autour de la meilleure detection
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # Journaliser la detection
            self.logs.append('Stop détecté : Position=({}, {}); Largeur={}; hauteur={};'.format(x, y, w, h))
            # Mettre à jour le résumé
            summary = {
                'detected': True,
                'detection_box': detection_box,
                'area': int(best_area)
            }

        self._save_step(overlay, 'contours_overlay', mode='bgr')

        return summary
