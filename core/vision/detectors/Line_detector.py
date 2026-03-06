#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Line_detector.py
# ------------------
# Module de détecteur de lignes en pointillés dans une image

import os
import time
import uuid

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
        self.debug = True  # Mode debug activé pour diagnostiquer le problème
        self.name = "line"
        self.logs = []
        
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
        """
        Détecte les lignes en pointillés dans l'image.
        
        Returns:
            dict: Format standardisé BaseDetector + clé 'line_offset'::

                {
                    'Object_detected': bool,
                    'detections': [],
                    'line_offset': float ou None,
                    'logs': [],
                }
        """
        self.logs.append('=== DETECTION LIGNE  ===')
        detection_result = self._detect_lines(frame)
        
        if detection_result is None:
            self._last_annotation_data = None
            return {
                'Object_detected': False,
                'detections': [],
                'line_offset': None,
                'logs': self.logs.copy(),
            }
        
        # Stocker les données d'annotation en interne pour annotate_detection()
        self._last_annotation_data = {
            'best_group': detection_result['best_group'],
            'valid_dashes': detection_result['valid_dashes'],
            'image_stats': detection_result['image_stats'],
            'avg_cx': detection_result['avg_cx'],
            'avg_cy': detection_result['avg_cy'],
            'offset': detection_result['offset'],
        }
        
        if self.debug:
            print("[LINE_DETECTOR] Ligne détectée: offset={:.1f}, {} pointillés".format(
                detection_result['offset'], len(detection_result['best_group'])))
        
        return {
            'Object_detected': True,
            'detections': [],
            'line_offset': detection_result['offset'],
            'logs': self.logs.copy(),
        }
    
    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir
    
    def annotate_detection(self, frame):
        """
        Annote une frame avec les résultats de la dernière détection.
        Utilise les données stockées en interne après le dernier appel à process().
        
        Args:
            frame: Image BGR à annoter (sera modifiée in-place)
        
        Returns:
            frame: Image annotée
        """
        ann_data = getattr(self, '_last_annotation_data', None)
        if ann_data is None:
            return frame
        
        best_group = ann_data['best_group']
        valid_dashes = ann_data['valid_dashes']
        image_stats = ann_data['image_stats']
        avg_cx = ann_data['avg_cx']
        avg_cy = ann_data['avg_cy']
        offset = ann_data['offset']
        
        height = image_stats['height']
        width = image_stats['width']
        offset_y = image_stats['offset_y']
        
        # Dessiner la ROI (rectangle rouge)
        cv2.rectangle(frame, (0, offset_y), (width, height), (0, 0, 255), 2)
        
        # Comparaison par identité pour éviter ambiguïté numpy
        best_group_ids = set(id(d) for d in best_group)
        
        # Pointillés du groupe (vert)
        for dash in best_group:
            x, y, w, h = dash['x'], dash['y'], dash['w'], dash['h']
            cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (0, 255, 0), 2)
        
        # Autres pointillés valides (jaune)
        for dash in valid_dashes:
            if id(dash) not in best_group_ids:
                x, y, w, h = dash['x'], dash['y'], dash['w'], dash['h']
                cv2.rectangle(frame, (x, y + offset_y), (x + w, y + h + offset_y), (0, 255, 255), 1)
        
        # Centre moyen (cercle rouge)
        if avg_cx is not None and avg_cy is not None:
            cv2.circle(frame, (int(avg_cx), int(avg_cy)), 10, (0, 0, 255), -1)
        
        # Ligne de référence au centre de l'image (vert)
        cv2.line(frame, (int(width/2), 0), (int(width/2), height), (0, 255, 0), 2)
        
        # Position détectée (cyan)
        if avg_cx is not None:
            cv2.line(frame, (int(avg_cx), 0), (int(avg_cx), height), (255, 255, 0), 2)
        
        # Texte: offset et nombre de pointillés détectés
        text = "Offset: {:.1f}px ({} dashes)".format(offset, len(best_group))
        cv2.putText(frame, text, (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        threshold_text = "Threshold: {}".format(self.white_threshold)
        cv2.putText(frame, threshold_text, (10, 55), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        return frame

    def process_passive(self, frame):
        """Détection de lignes pour le live feed. Format standardisé."""
        result = self.process(frame)
        result['timestamp'] = time.time()
        return result

    def diagnostique_detecteur(self, filename):
        """
        Diagnostic détaillé du détecteur de ligne.
        Visualise chaque étape du pipeline de détection:
          1. Image source originale
          2. Région d'intérêt (ROI) avec rectangle rouge
          3. Image prétraitée (gris → flou → seuillage → morphologie)
          4. Tous les contours trouvés (avant filtrage)
          5. Pointillés valides (après filtrage)
          6. Résultat final annoté (meilleur groupe + offset)

        :param filename: Nom du fichier image capturé (dans CAPTURE_DIR).
        :return: dict standardisé {'Object_detected', 'line_offset', 'logs', 'steps', 'source_file_url', 'annotated_url'}
        """
        from flask import url_for

        self.logs = []
        steps = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}
        if not self.CAPTURE_DIR:
            return {'error': 'CAPTURE_DIR not setup. Call attach_capture_dir() first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(DIAGNOSTIC_DIR, exist_ok=True)

        short_id = uuid.uuid4().hex[:8]

        def _save_step(label, img_bgr):
            fname = 'diag_line_{}_{}.jpg'.format(label.replace(' ', '_'), short_id)
            cv2.imwrite(os.path.join(DIAGNOSTIC_DIR, fname), img_bgr)
            url = url_for('static', filename='captured_images/diagnostics/{}'.format(fname))
            steps.append({'name': label, 'url': url})

        try:
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            h, w = frame_bgr.shape[:2]
            self.logs.append('=== DIAGNOSTIC LIGNE ===')
            self.logs.append('Image: {}  |  Resolution: {}x{}'.format(filename, w, h))
            self.logs.append('Parametres: seuil_blanc={}, min_area={}, offset_ratio={}'.format(
                self.white_threshold, self.min_area, self.offset_ratio))

            # 1. Image source
            _save_step('1 - Source', frame_bgr.copy())

            # 2. ROI tracée sur la frame (rectangle rouge)
            offset_y = int(h * self.offset_ratio)
            roi_vis = frame_bgr.copy()
            cv2.rectangle(roi_vis, (0, offset_y), (w, h), (0, 0, 255), 2)
            cv2.putText(roi_vis, 'ROI (offset_ratio={})'.format(self.offset_ratio),
                        (10, offset_y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            self.logs.append('ROI: y_debut={} ({}% de la hauteur)'.format(offset_y, int(self.offset_ratio * 100)))
            _save_step('2 - ROI', roi_vis)

            # 3. Prétraitement (gris → GaussianBlur → seuillage → morphologie)
            roi = frame_bgr[offset_y:h, :]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            # Convertir en BGR pour sauvegarde couleur
            thresh_full = np.zeros_like(frame_bgr)
            thresh_full[offset_y:h, :] = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
            self.logs.append('Seuil blanc applique: {}'.format(self.white_threshold))
            _save_step('3 - Pretraitement threshold', thresh_full)

            image_stats = {
                'height': h, 'width': w,
                'offset_y': offset_y, 'roi_height': roi.shape[0],
            }

            # 4. Tous les contours (avant filtrage)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
            all_cnt_vis = frame_bgr.copy()
            for cnt in (contours or []):
                cx_, cy_, cw_, ch_ = cv2.boundingRect(cnt)
                cv2.rectangle(all_cnt_vis, (cx_, cy_ + offset_y), (cx_ + cw_, cy_ + ch_ + offset_y), (255, 128, 0), 1)
            self.logs.append('Contours totaux trouves: {}'.format(len(contours) if contours else 0))
            _save_step('4 - Tous les contours', all_cnt_vis)

            # 5. Pointillés valides (après filtrage)
            valid_dashes = self._extract_and_validate_contours(thresh, image_stats)
            valid_vis = frame_bgr.copy()
            for d in (valid_dashes or []):
                cv2.rectangle(valid_vis, (d['x'], d['y'] + offset_y),
                              (d['x'] + d['w'], d['y'] + d['h'] + offset_y), (0, 255, 255), 2)
            self.logs.append('Pointilles valides apres filtrage: {}'.format(len(valid_dashes) if valid_dashes else 0))
            _save_step('5 - Pointilles valides', valid_vis)

            # 6. Résultat final (meilleur groupe + annotation complète)
            object_detected = False
            line_offset = None
            annotated_url = None

            if valid_dashes:
                best_group = self._grouper_pointilles(valid_dashes, image_stats)
                offset_stats = self._compute_offset(best_group, image_stats)
                self._last_annotation_data = {
                    'best_group': best_group,
                    'valid_dashes': valid_dashes,
                    'image_stats': image_stats,
                    'avg_cx': offset_stats['avg_cx'],
                    'avg_cy': offset_stats['avg_cy'],
                    'offset': offset_stats['offset'],
                }
                annotated_frame = self.annotate_detection(frame_bgr.copy())
                _save_step('6 - Resultat annote', annotated_frame)
                annotated_url = steps[-1]['url']
                object_detected = True
                line_offset = offset_stats['offset']
                self.logs.append('Meilleur groupe: {} pointilles'.format(len(best_group)))
                self.logs.append('Offset final: {:.1f} px'.format(line_offset))
            else:
                self.logs.append('Aucune ligne detectee dans cette image.')

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            return {
                'Object_detected': object_detected,
                'line_offset': line_offset,
                'logs': self.logs,
                'steps': steps,
                'source_file_url': source_url,
                'annotated_url': annotated_url,
            }

        except Exception as e:
            import traceback
            self.logs.append('ERREUR: {}'.format(str(e)))
            return {
                'error': 'diagnostic failed: {}'.format(str(e)),
                'logs': self.logs,
                'steps': steps,
            }


#         Méthode interne pour détecter les lignes en pointillés
###########################################################################

    def _detect_lines(self, frame):
        """Détecte les lignes en pointillés dans l'image.
         Args: frame (np.ndarray): Image d'entrée capturée par la caméra.
         Returns: dict ou None: Données de détection brutes.
         """
        
        # 1. Extraire la région d'intérêt (ROI) — pas d'annotation ici, show_ROI=False
        frame_roi, image_stats = self._extract_and_prepare_roi(frame, show_ROI=False)
  
        # 2. Extraire les contours et valider les candidats pour les lignes en pointillés
        valid_dashes = self._extract_and_validate_contours(frame_roi, image_stats)

        if not valid_dashes:
            if self.debug:
                print("[LINE_DETECTOR] Aucun pointillé valide trouvé.")
            return None

        # 3. Grouper les pointillés alignés verticalement
        best_group = self._grouper_pointilles(valid_dashes, image_stats)

        # 4. Calculer le centre moyen et le décalage par rapport au centre
        offset_stats = self._compute_offset(best_group, image_stats)

        return {
            'offset': offset_stats['offset'],
            'avg_cx': offset_stats['avg_cx'],
            'avg_cy': offset_stats['avg_cy'],
            'best_group': best_group,
            'valid_dashes': valid_dashes,
            'image_stats': image_stats,
        }

    def _extract_and_prepare_roi(self, frame, show_ROI=False):
        """Extrait la région d'intérêt (ROI) pour la détection de lignes.
         Args:
             frame (np.ndarray): Image d'entrée capturée par la caméra.
             show_ROI (bool):  si la région d'intérêt doit être affichée.

         Returns:
             np.ndarray: ROI prétraitée pour la détection de lignes.
         """
        # 1. Définition de la zone de détection (ROI)
        height, width = frame.shape[:2]         
        offset_y = int(height * self.offset_ratio) 
        roi = frame[offset_y:height, :] 
        roi_height = roi.shape[0]
        
        if show_ROI:
            # Dessine la zone de détection (rectangle rouge)
            cv2.rectangle(frame, (0, offset_y), (width, height), (0, 0, 255), 2)
            
        # 2. Traitement d'image
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Utiliser le seuil configurable pour détecter les lignes BLANCHES sur fond noir
        _, thresh = cv2.threshold(blur, self.white_threshold, 255, cv2.THRESH_BINARY)
        
        # Morphologie légère
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        # log des données requises pour l'analyse
        image_stats = {
            'height': height,
            'width': width,
            'offset_y': offset_y,
            'roi_height': roi_height,
        }

        return thresh, image_stats
    
    def _extract_and_validate_contours(self, thresh, image_stats):
        """Extrait les contours et valide les candidats pour les lignes en pointillés.
         Args:
             thresh (np.ndarray): Image binaire après seuillage.
             image_stats (dict): Statistiques de l'image pour la validation.

         Returns:
             list: Liste des contours validés correspondant aux lignes en pointillés.
         """
        # Détection de contours (compatible OpenCV 3 et 4)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)[-2:]
        
        if contours is None:
            if self.debug:
                self.logs.append("[LINE_DETECTOR] Aucun contour trouvé dans _extract_and_validate_contours.")
                print("[LINE_DETECTOR] Aucun contour trouvé dans _extract_and_validate_contours.")
            return None

        # DEBUG: Afficher le nombre de contours trouvés
        if self.debug:
            print("[LINE_DETECTOR] Nombre de contours trouvés: {}".format(len(contours)))
        
        # 4. Filtrer les contours pour trouver les POINTILLÉS
        valid_dashes = []
        rejected_count = {'too_small': 0, 'too_large': 0, 'bad_ratio': 0}

        for cnt in contours:
            area = cv2.contourArea(cnt)
            x, y, w, h = cv2.boundingRect(cnt)
            
            if area < self.min_area:
                rejected_count['too_small'] += 1
                continue
            
            if w > image_stats['width'] * 0.4 or h > image_stats['roi_height'] * 0.5:
                rejected_count['too_large'] += 1
                continue
                
            aspect_ratio = float(h) / float(w) if w > 0 else 0
            if aspect_ratio < 0.3 or aspect_ratio > 10:
                rejected_count['bad_ratio'] += 1
                continue
            
            valid_dashes.append({
                'contour': cnt,
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'cx': x + w / 2,
                'cy': y + h / 2
            })
       
        self.logs.append("[LINE_DETECTOR] Contours valides après filtrage: {}".format(len(valid_dashes))) 
        
        if self.debug:
            print("[LINE_DETECTOR] Contours rejetés: trop petits={}, trop grands={}, mauvais ratio={}".format(
                rejected_count['too_small'], rejected_count['too_large'], rejected_count['bad_ratio']
            ))
            print("[LINE_DETECTOR] Contours valides après filtrage: {}".format(len(valid_dashes)))
        
        return valid_dashes
    
    def _grouper_pointilles(self, valid_dashes, image_stats):
        """Groupe les pointillés alignés verticalement.
         Args:
             valid_dashes (list): Liste des contours validés correspondant aux lignes en pointillés.
             image_stats (dict): Statistiques de l'image pour la validation.

         Returns:
             list: Liste du meilleur groupe de pointillés alignés verticalement.
         """
        X_TOLERANCE = image_stats['width'] * 0.25  # Tolérance de 25% de la largeur de l'image
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

        if self.debug:
            print("[LINE_DETECTOR] Meilleur groupe trouvé avec {} pointillés".format(len(best_group)))
        
        return best_group

    def _compute_offset(self, group, image_stats):
        """Calcule le décalage horizontal du centre de la ligne par rapport au centre de l'image.
         Args:
             group (list): Liste du meilleur groupe de pointillés alignés verticalement.
             image_stats (dict): Statistiques de l'image pour le calcul.

         Returns:
             dict: Dictionnaire contenant le décalage et les coordonnées moyennes du groupe.
         """
        # 6. Calculer le centre moyen
        total_cx = sum([d['cx'] for d in group])
        total_cy = sum([d['cy'] for d in group])
        avg_cx = int(total_cx / len(group))
        avg_cy = int(total_cy / len(group)) + image_stats['offset_y']
        
        offset = avg_cx - (image_stats['width'] / 2)

        if self.debug:
            print("[LINE_DETECTOR] Calcul du décalage: avg_cx={}, center_x={}, offset={}".format(
                avg_cx, image_stats['width'] / 2, offset
            ))

        self.logs.append("[LINE_DETECTOR] Calcul du décalage: offset={}".format(offset))

        offset_stats = {
            'offset': offset,
            'avg_cx': avg_cx,
            'avg_cy': avg_cy,
            'total_cx': total_cx,
            'total_cy': total_cy
        }

        return offset_stats
    
    