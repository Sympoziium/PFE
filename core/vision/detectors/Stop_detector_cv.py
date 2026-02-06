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

    def __init__(self, min_area=500, aspect_tol=0.35, poly_min=5, poly_max=10, h_min=30, w_min=30, fill_ratio_min=0.5):
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

            # Étape 0: Image originale
            self._save_step(frame_bgr.copy(), 'original_rgb', mode='bgr')

            # Étape diagnostic: Test du format BGR/RGB
            self.logs.append('')  # Ligne vide pour lisibilité
            format_ok = self.diagnostic_bgr_rgb_format(frame_bgr)
            self.logs.append('')  # Ligne vide pour lisibilité

            # Étape diagnostic: Analyse HSV approfondie
            self.logs.append('')  # Ligne vide pour lisibilité
            self.diagnostic_hsv_analysis(frame_bgr)
            self.logs.append('')  # Ligne vide pour lisibilité

            # Étape 1: Conversion en HSV et séparation des canaux
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            mask = self._make_HSV_mask(hsv, diagnostic_mode=True)
            mask = self._fill_holes(mask) # remplir les trous laisser par le texte du panneau




            # Test rapide du filtre HSV pour debug - ANCIEN (incorrect)
            self.logs.append('=== Test filtre HSV ancien (valeurs incorrectes H=[170,180]) ===')
            self.test_hsv_filter(frame_bgr)

            # Test du filtre HSV CORRIGÉ (comme Matt)
            self.logs.append('=== Test filtre HSV corrigé (valeurs correctes H=[160,180]) ===')
            self.test_corrected_hsv_filter(frame_bgr)

            # Étape 3: Opérations morphologiques pour nettoyage et reconstruction de l'image
            mask_morpho = self._make_morphological_mask(mask, diagnostic_mode=True)
            
            # Étape 4: Détection des contours sur le masque final
            Image_traitée = mask_morpho.copy()
            contours = self._detect_contours(Image_traitée)

            # Étape 5: Analyse des contours et détection finale
            results = self._analyse_detections(contours, frame_bgr)

            # Étape 6: Formatage de la réponse JSON
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

            return payload
        
        except Exception as e:
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
        """Crée un masque binaire pour les zones rouges dans une image HSV."""
        
        if hsv is None:
            raise ValueError('No image provided for HSV masking')
        
        # Étape 1: Séparation des canaux HSV 
        h, s, v = cv2.split(hsv)

        if diagnostic_mode:
            # Sauvegarde des canaux HSV
            self._save_step(h, 'h_channel', mode='gray')
            self._save_step(s, 's_channel', mode='gray')
            self._save_step(v, 'v_channel', mode='gray')

        # Étape 2: Conception de masques optmisés pour le rouge en HSV
        # filtrage par saturation
        s_mask = cv2.inRange(s, 95, 255) # 90 et plus semble bien isoler le rouge
        if diagnostic_mode:
            self._save_step(s_mask, 's_mask', 'gray')

        # filtrage par hue
        h_mask = cv2.inRange(h, 120, 130) # plage optimale pour le rouge du panneau stop max (120-150)
        if diagnostic_mode:
            self._save_step(h_mask, 'h_mask', 'gray')
        # filtrage par value
        # le filtre v n'apporte pas grand chose de plus mais on le garde pour le debug
        # il varie énormément selon l'éclairage n'est pas très fiable.
        v_mask = np.zeros(v.shape, dtype=np.uint8)
        v_mask[s > 95] = 255
        if diagnostic_mode:
            self._save_step(v_mask, 'v_mask', 'gray')

        # Étape 3: Combinaison des masques H, S, V
        hsv_combined_mask = np.zeros(h.shape, dtype=np.uint8)
        hsv_combined_mask = cv2.bitwise_and(h_mask, s_mask)
        # le mask v n'apporte pas grand chose on est mieux sans

        # Binarisation du masque combiné
        _, mask = cv2.threshold(hsv_combined_mask, 1, 255, cv2.THRESH_BINARY)
        
        # Sauvegarde du masque initial
        if diagnostic_mode:
            self._save_step(mask, 'initial_mask', mode='gray')
        

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

            # Si l'aire est inférieure au minimum, on ignore
            if area <  self.min_area:
                continue
            # Si le nombre de sommets n'est pas dans l'intervalle, on ignore
            if vtx < self.poly_min or vtx > self.poly_max:
                continue
            # Si le contour n'est pas convexe, on ignore (panneau stop est convexe)
            hull = cv2.convexHull(c)
            hull_area = cv2.contourArea(hull)
            if area / hull_area < 0.85:
                continue
            # Si la boite englobante est trop petite, ces soit une abérration ou le panneau est trop loin 
            if h < self.h_min or w < self.w_min:
                continue
            # Si le ratio largeur/hauteur est proche de 1 la boite est presque carrée, plus ces probable que ce soit un panneau stop
            if abs(ratio - 1.0) > float(self.aspect_tol):
                continue
            # Si le ratio de remplissage est trop faible, cela veut dire que le contour est trop irrégulier pour être un octogone
            if fill_ratio < self.fill_ratio_min:
                continue
            # Si c'est le plus grand jusqu'à présent, on le garde comme détection 
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
            

### fonction de test rapide pour debug

    def test_hsv_filter(self, frame_bgr):
        """Test rapide du filtre HSV pour le rouge sur une image BGR.
        Retourne le masque binaire résultant.
        ATTENTION: Cette fonction utilise des valeurs incorrectes (170-180) pour démonstration.
        """
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        mask_red_low = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
        mask_red_high = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
        mask = cv2.bitwise_or(mask_red_low, mask_red_high)
        self._save_step(mask, 'test_hsv_red_mask_OLD', mode='gray')
        return mask

    def test_corrected_hsv_filter(self, frame_bgr):
        """Test du filtre HSV avec les valeurs CORRIGÉES pour le rouge (comme Matt).

        Valeurs correctes pour le rouge en HSV OpenCV (0-180):
        - Bas: H=[0, 10], S=[70, 255], V=[50, 255]
        - Haut: H=[160, 180], S=[70, 255], V=[50, 255]

        Note: Identique au filtre utilisé par Matt dans hsv_mattv2.py
        """
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

        # Masque bas (autour de 0°)
        mask_red_low = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        # Masque haut (autour de 180°) - CORRIGÉ de 170 à 160
        mask_red_high = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))

        # Combinaison des deux masques
        mask = cv2.bitwise_or(mask_red_low, mask_red_high)

        # Morphologie pour nettoyer (comme dans hsv_mattv2.py)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        # Sauvegarder les étapes
        self._save_step(mask_red_low, 'corrected_red_mask_low', mode='gray')
        self._save_step(mask_red_high, 'corrected_red_mask_high', mode='gray')
        self._save_step(mask, 'corrected_red_mask_combined_morpho', mode='gray')

        self.logs.append('Corrected HSV filter: low H=[0,10], high H=[160,180], S=[70,255], V=[50,255]')

        return mask

    def diagnostic_bgr_rgb_format(self, frame):
        """Détecte si l'image est en format BGR ou RGB (ou inversée).

        Cette fonction analyse les canaux de couleur pour détecter une éventuelle
        inversion BGR↔RGB qui causerait des problèmes de détection.
        """
        self.logs.append('=== BGR/RGB FORMAT DIAGNOSTIC ===')

        b, g, r = cv2.split(frame)

        # Statistiques par canal
        b_mean, b_std = float(b.mean()), float(b.std())
        g_mean, g_std = float(g.mean()), float(g.std())
        r_mean, r_std = float(r.mean()), float(r.std())

        self.logs.append('Channel Statistics (as loaded):')
        self.logs.append('  Channel 0 (B if BGR): Mean={:.2f}, Std={:.2f}'.format(b_mean, b_std))
        self.logs.append('  Channel 1 (G):        Mean={:.2f}, Std={:.2f}'.format(g_mean, g_std))
        self.logs.append('  Channel 2 (R if BGR): Mean={:.2f}, Std={:.2f}'.format(r_mean, r_std))

        # Test 1: Pour un panneau stop ROUGE, le canal R devrait être dominant
        # Si l'image est correctement en BGR, le canal 2 (R) devrait être élevé
        # Si elle est inversée (RGB lu comme BGR), le canal 0 (B) sera élevé

        # Compter les pixels avec forte composante rouge vs bleu
        red_dominant = np.sum((r > 150) & (r > b + 30) & (r > g + 30))
        blue_dominant = np.sum((b > 150) & (b > r + 30) & (b > g + 30))

        self.logs.append('')
        self.logs.append('Dominant Color Analysis (for red object detection):')
        self.logs.append('  Pixels with dominant RED (channel 2):  {} pixels'.format(red_dominant))
        self.logs.append('  Pixels with dominant BLUE (channel 0): {} pixels'.format(blue_dominant))

        # Diagnostic
        if red_dominant > blue_dominant * 2:
            self.logs.append('  → VERDICT: Image appears to be in correct BGR format ✓')
            format_ok = True
        elif blue_dominant > red_dominant * 2:
            self.logs.append('  → VERDICT: Image appears to be in RGB format (INVERTED!) ✗')
            self.logs.append('  → PROBLEM: Red objects will appear BLUE, causing HSV detection to fail!')
            format_ok = False
        else:
            self.logs.append('  → VERDICT: Inconclusive (no strong red/blue dominance)')
            format_ok = None

        # Créer des visualisations des canaux
        self._save_step(r, 'channel_2_red_if_bgr', mode='gray')
        self._save_step(g, 'channel_1_green', mode='gray')
        self._save_step(b, 'channel_0_blue_if_bgr', mode='gray')

        # Test avec conversion forcée
        if not format_ok:
            self.logs.append('')
            self.logs.append('Testing with forced BGR→RGB conversion...')
            frame_corrected = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._save_step(frame_corrected, 'corrected_rgb_to_bgr', mode='RGB')
            self.logs.append('  Corrected image saved as corrected_rgb_to_bgr')
            self.logs.append('  Try reprocessing with this corrected image!')

        self.logs.append('=== END BGR/RGB DIAGNOSTIC ===')
        return format_ok

    def diagnostic_hsv_analysis(self, frame_bgr):
        """Analyse approfondie des caractéristiques HSV de l'image.

        Cette fonction génère des statistiques détaillées pour comparer
        les images entre différents environnements (Zumi vs PiCamera2).
        """
        self.logs.append('=== DIAGNOSTIC HSV ANALYSIS ===')

        # Info de base sur l'image
        h, w, c = frame_bgr.shape
        total_pixels = h * w
        self.logs.append('Image dimensions: {}x{} ({} channels)'.format(w, h, c))
        self.logs.append('Total pixels: {}'.format(total_pixels))

        # Conversion en HSV
        hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
        h_channel, s_channel, v_channel = cv2.split(hsv)

        # Statistiques par canal HSV
        self.logs.append('--- H Channel (Hue) ---')
        self.logs.append('  Min: {}, Max: {}, Mean: {:.2f}, Std: {:.2f}'.format(
            int(h_channel.min()), int(h_channel.max()),
            float(h_channel.mean()), float(h_channel.std())))

        self.logs.append('--- S Channel (Saturation) ---')
        self.logs.append('  Min: {}, Max: {}, Mean: {:.2f}, Std: {:.2f}'.format(
            int(s_channel.min()), int(s_channel.max()),
            float(s_channel.mean()), float(s_channel.std())))

        self.logs.append('--- V Channel (Value) ---')
        self.logs.append('  Min: {}, Max: {}, Mean: {:.2f}, Std: {:.2f}'.format(
            int(v_channel.min()), int(v_channel.max()),
            float(v_channel.mean()), float(v_channel.std())))

        # Détection de pixels rouges avec différentes méthodes
        self.logs.append('--- Red Pixel Detection Comparison ---')

        # Méthode 1: Anciennes valeurs (incorrectes)
        mask_old_low = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
        mask_old_high = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
        mask_old = cv2.bitwise_or(mask_old_low, mask_old_high)
        red_pixels_old = cv2.countNonZero(mask_old)
        percent_old = (red_pixels_old / float(total_pixels)) * 100.0
        self.logs.append('  Method OLD (H=[0-10] + [170-180]): {} pixels ({:.2f}%)'.format(
            red_pixels_old, percent_old))

        # Méthode 2: Valeurs corrigées (comme Matt)
        mask_corr_low = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        mask_corr_high = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
        mask_corr = cv2.bitwise_or(mask_corr_low, mask_corr_high)
        red_pixels_corr = cv2.countNonZero(mask_corr)
        percent_corr = (red_pixels_corr / float(total_pixels)) * 100.0
        self.logs.append('  Method CORRECTED (H=[0-10] + [160-180]): {} pixels ({:.2f}%)'.format(
            red_pixels_corr, percent_corr))

        # Différence
        diff_pixels = red_pixels_corr - red_pixels_old
        self.logs.append('  Difference: {} pixels ({:.2f}% more with corrected)'.format(
            diff_pixels, ((diff_pixels / float(total_pixels)) * 100.0)))

        # Distribution des teintes dans la plage rouge
        red_range_low = np.sum((h_channel >= 0) & (h_channel <= 10))
        red_range_mid = np.sum((h_channel >= 160) & (h_channel <= 170))
        red_range_high = np.sum((h_channel >= 170) & (h_channel <= 180))

        self.logs.append('--- Hue Distribution in Red Range ---')
        self.logs.append('  H in [0, 10]: {} pixels'.format(red_range_low))
        self.logs.append('  H in [160, 170]: {} pixels'.format(red_range_mid))
        self.logs.append('  H in [170, 180]: {} pixels'.format(red_range_high))

        # Créer une visualisation des histogrammes
        self._create_histogram_visualization(h_channel, s_channel, v_channel)

        self.logs.append('=== END DIAGNOSTIC ===')

    def _create_histogram_visualization(self, h_channel, s_channel, v_channel):
        """Crée une visualisation des histogrammes HSV."""
        import matplotlib
        matplotlib.use('Agg')  # Backend sans affichage
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(1, 3, figsize=(15, 4))

        # Histogramme H
        axes[0].hist(h_channel.ravel(), bins=180, range=(0, 180), color='red', alpha=0.7)
        axes[0].set_title('Hue (H) Distribution')
        axes[0].set_xlabel('Hue Value (0-180)')
        axes[0].set_ylabel('Pixel Count')
        axes[0].axvspan(0, 10, alpha=0.2, color='green', label='Red Low')
        axes[0].axvspan(160, 180, alpha=0.2, color='blue', label='Red High')
        axes[0].legend()

        # Histogramme S
        axes[1].hist(s_channel.ravel(), bins=256, range=(0, 256), color='orange', alpha=0.7)
        axes[1].set_title('Saturation (S) Distribution')
        axes[1].set_xlabel('Saturation Value (0-255)')
        axes[1].set_ylabel('Pixel Count')
        axes[1].axvline(70, color='red', linestyle='--', label='Threshold S=70')
        axes[1].legend()

        # Histogramme V
        axes[2].hist(v_channel.ravel(), bins=256, range=(0, 256), color='purple', alpha=0.7)
        axes[2].set_title('Value (V) Distribution')
        axes[2].set_xlabel('Value (0-255)')
        axes[2].set_ylabel('Pixel Count')
        axes[2].axvline(50, color='red', linestyle='--', label='Threshold V=50')
        axes[2].legend()

        plt.tight_layout()

        # Sauvegarder le graphique
        hist_path = os.path.join(self.DIAGNOSTIC_DIR, 'hsv_histograms_{}.png'.format(uuid.uuid4().hex[:6]))
        plt.savefig(hist_path, dpi=100, bbox_inches='tight')
        plt.close()

        # Ajouter à la liste des étapes
        hist_url = url_for('static', filename='captured_images/diagnostics/{}'.format(os.path.basename(hist_path)))
        self.steps.append({"name": "hsv_histograms", "url": hist_url})

        self.logs.append('Histograms saved as: {}'.format(os.path.basename(hist_path)))