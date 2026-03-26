#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_zumi.py
# ------------------
#
#   DEPRECATION NOTICE : Ce détecteur ne fonctionne plus avec la mise a jours du Pi vers le 2W
#                        Les fichier .xml de Robolink nont pas été copier sur le nouveau système,
#                        comme nous faisons notre propre détecteur avec nos propre .xml on en a plus de besoin.
#
#
# Ce module implémente le détecteur de panneau stop pour le robot Zumi
# en utilisant la bibliothèque Zumi (zumi.util.vision.Vision).
# La bibliothèque utilise un classifieur Haar pré-optimisé pour le Zumi.
# Ce détecteur inclut un mode diagnostic qui teste différentes combinaisons
# de paramètres (scaleFactor, minNeighbors, minSize) en BGR et RGB
# pour aider à trouver les réglages optimaux.

import os, uuid, time
from .detector_base import BaseDetector
from zumi.util.vision import Vision

import cv2

try:
    from flask import url_for
except ImportError:
    url_for = None

class StopDetectorZumi(BaseDetector):

    def __init__(self, scale_factor=1.05, min_neighbors=8, min_size=(40, 40)):
        """Initialise le détecteur de panneau stop pour le Zumi.
        Args:
            scale_factor (float): facteur d'échelle pour la détection.
            min_neighbors (int): nombre minimum de voisins pour valider une détection.
            min_size (tuple): taille minimale du panneau à détecter.
        """
        self.zumi_vision = Vision()  # instance de vision du robot Zumi
        self.scaleFactor = scale_factor
        self.minNeighbors = min_neighbors
        self.minSize = min_size
        self.name = "StopDetectorZumi"
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        self.debug = False  # Flag de debug pour les fonctions d'annotation et de diagnostic
        self.logs = []
        self.steps = []

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process_passive(self, frame):
        """Détection passive de panneau STOP optimisée pour le live feed.

        Retourne le format standardisé (sans logs).
        """
        if frame is None:
            return {'Object_detected': False, 'detections': [], 'timestamp': time.time()}

        try:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            bbox = self.zumi_vision.find_stop_sign(
                frame_rgb,
                scale_factor=self.scaleFactor,
                min_neighbors=self.minNeighbors,
                min_size=self.minSize,
            )

            detections = []
            if bbox is not None:
                x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                detections.append({
                    'object': 'Stop Sign',
                    'detection_box': (x, y, w, h)
                })

            return {
                'Object_detected': len(detections) > 0,
                'detections': detections,
                'timestamp': time.time()
            }
        except Exception as e:
            return {'Object_detected': False, 'detections': [], 'timestamp': time.time()}

    def process(self, frame, filename=None):
        """Analyse une image pour détecter un panneau stop via la lib Zumi.
        Retourne un payload standardisé **sans annotation**.

        Args:
            frame: image BGR (numpy array).
            filename: nom du fichier image capturé (optionnel).
        Returns:
            dict: {Object_detected, detections, logs}.
        """
        self.logs = []
        self.steps = []

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

        self.logs.append('=== DETECTION STOP (Zumi Vision) ===')
        self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
        self.logs.append('Config: scaleFactor={}, minNeighbors={}, minSize={}'.format(
            self.scaleFactor, self.minNeighbors, self.minSize))

        try:
            # La lib Zumi attend du RGB
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            bbox = self.zumi_vision.find_stop_sign(
                frame_rgb,
                scale_factor=self.scaleFactor,
                min_neighbors=self.minNeighbors,
                min_size=self.minSize,
            )

            self.logs.append('Retour brut find_stop_sign: {}'.format(repr(bbox)))

            detections = []
            if bbox is not None:
                x, y, w, h = int(bbox[0]), int(bbox[1]), int(bbox[2]), int(bbox[3])
                self.logs.append('Resultat: STOP DETECTE')
                self.logs.append('  Position: x={}, y={}'.format(x, y))
                self.logs.append('  Taille: {}x{}, aire={}'.format(w, h, w * h))
                detections.append({
                    'object': 'Stop Sign',
                    'detection_box': (x, y, w, h),
                    'confidence': 1.0,
                })
            else:
                self.logs.append('Resultat: Aucun panneau stop detecte')

            self.logs.append('=== FIN DETECTION ===')

            return {
                'Object_detected': len(detections) > 0,
                'detections': detections,
                'logs': self.logs,
            }

        except Exception as e:
            self.logs.append('ERREUR: {}'.format(str(e)))
            import traceback
            traceback.print_exc()
            return {'error': 'process failed', 'details': str(e), 'logs': self.logs}

    def diagnostique_detecteur(self, filename):
        """Diagnostic allege: test rapide puis balayage avec early bailout.
        
        Strategie:
        1. Test rapide avec les params par defaut
        2. Balayage reduit (3 sf x 3 mn x 2 ms x 2 espaces = 36 combos max)
        3. Early bailout: arret apres 3 detections consecutives
        
        :param filename: Nom du fichier image capture.
        :return: dict standardise avec logs, steps, et resultats.
        """
        self.logs = []
        self.steps = []

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

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)

            self.logs.append('=== DIAGNOSTIC StopDetectorZumi ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('')

            # Sauvegarder image source
            self._save_step(frame_bgr, '0_image_source', 'bgr')

            # --- Test rapide avec params par defaut ---
            self.logs.append('--- TEST RAPIDE (params par defaut) ---')
            self.logs.append('  scaleFactor={}, minNeighbors={}, minSize={}'.format(
                self.scaleFactor, self.minNeighbors, self.minSize))

            quick_det = self.zumi_vision.find_stop_sign(
                frame_rgb,
                scale_factor=self.scaleFactor,
                min_neighbors=self.minNeighbors,
                min_size=self.minSize,
            )
            if quick_det is not None:
                qx, qy, qw, qh = int(quick_det[0]), int(quick_det[1]), int(quick_det[2]), int(quick_det[3])
                self.logs.append('  -> DETECTE: pos=({},{}) taille={}x{}'.format(qx, qy, qw, qh))
                overlay_q = frame_bgr.copy()
                cv2.rectangle(overlay_q, (qx, qy), (qx + qw, qy + qh), (255, 0, 255), 2)
                self._save_step(overlay_q, '1_quick_test', 'bgr')
            else:
                self.logs.append('  -> Aucune detection')

            # --- Balayage reduit avec early bailout ---
            self.logs.append('')
            self.logs.append('--- BALAYAGE ---')

            scale_factors = [1.05, 1.1, 1.2]
            min_neighbors_list = [3, 5, 8]
            min_sizes = [30, 60]

            best = {'bbox': None, 'area': 0, 'sf': None, 'mn': None, 'ms': None, 'space': None}
            total_tested = 0
            total_detected = 0
            consecutive_ok = 0
            bailout = False

            for sf in scale_factors:
                if bailout:
                    break
                for mn in min_neighbors_list:
                    if bailout:
                        break
                    for ms in min_sizes:
                        if bailout:
                            break
                        for space_tag, img in (('BGR', frame_bgr), ('RGB', frame_rgb)):
                            if bailout:
                                break
                            total_tested += 1
                            try:
                                det_raw = self.zumi_vision.find_stop_sign(
                                    img,
                                    scale_factor=sf,
                                    min_neighbors=mn,
                                    min_size=(ms, ms),
                                )

                                if det_raw is not None:
                                    total_detected += 1
                                    consecutive_ok += 1
                                    x, y, w, h = int(det_raw[0]), int(det_raw[1]), int(det_raw[2]), int(det_raw[3])
                                    area = w * h
                                    self.logs.append('{} sf={} mn={} ms={} -> DETECTE ({}x{}, aire={})'.format(
                                        space_tag, sf, mn, ms, w, h, area))

                                    if area > best['area']:
                                        best.update({
                                            'bbox': (x, y, w, h), 'area': area,
                                            'sf': sf, 'mn': mn, 'ms': ms, 'space': space_tag
                                        })
                                        # Sauvegarder la meilleure detection
                                        overlay = frame_bgr.copy()
                                        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
                                        label = '{} sf={} mn={}'.format(space_tag, sf, mn)
                                        cv2.putText(overlay, label, (x, max(0, y - 10)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                        self._save_step(overlay, 'best_detection', 'bgr')

                                    # Early bailout
                                    if consecutive_ok >= 3:
                                        self.logs.append('  -> 3 detections consecutives, arret du balayage.')
                                        bailout = True
                                else:
                                    consecutive_ok = 0

                            except Exception as e:
                                consecutive_ok = 0
                                self.logs.append('{} sf={} mn={} ms={} -> ERREUR: {}'.format(
                                    space_tag, sf, mn, ms, str(e)))

            self.logs.append('')
            self.logs.append('--- RESUME ---')
            self.logs.append('Combinaisons testees: {}'.format(total_tested))
            self.logs.append('Detections: {}'.format(total_detected))
            if bailout:
                self.logs.append('Arret anticipe: le modele detecte de maniere fiable.')

            if best['bbox']:
                bx, by, bw, bh = best['bbox']
                self.logs.append('Meilleure detection:')
                self.logs.append('  Espace: {}'.format(best['space']))
                self.logs.append('  scaleFactor: {}'.format(best['sf']))
                self.logs.append('  minNeighbors: {}'.format(best['mn']))
                self.logs.append('  minSize: ({0},{0})'.format(best['ms']))
                self.logs.append('  BBox: x={}, y={}, w={}, h={}'.format(bx, by, bw, bh))
                self.logs.append('  Aire: {}'.format(best['area']))
            else:
                self.logs.append('Aucune detection sur aucune combinaison.')

            self.logs.append('=== FIN DIAGNOSTIC ===')

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            det_box = best['bbox'] if best['bbox'] else None
            det_area = best['area'] if best['area'] > 0 else None
            return {
                'Object_detected': det_box is not None,
                'detection_box': det_box,
                'confidence': 1.0 if det_box else 0.0,
                'area': det_area,
                'logs': self.logs,
                'steps': self.steps,
                'source_file_url': source_url,
                'annotated_url': self.steps[-1]['url'] if self.steps else None,
            }

        except Exception as e:
            self.logs.append('ERREUR DIAGNOSTIC: {}'.format(str(e)))
            import traceback
            traceback.print_exc()
            return {'error': 'diagnostic failed', 'details': str(e), 'logs': self.logs}

    def _select_bbox(self, bboxes):
        """Sélectionne le plus grand bbox depuis une liste. Retourne (x,y,w,h) ou None."""
        valids = [
            b for b in bboxes if isinstance(b, (list, tuple)) and len(b) >= 4 and all(
                isinstance(x, (int, float)) for x in b[:4]
            )
        ]
        if not valids:
            return None
        best = max(valids, key=lambda b: float(b[2]) * float(b[3]))
        return (int(best[0]), int(best[1]), int(best[2]), int(best[3]))

    def _save_step(self, img, name, mode):
        """Sauvegarde une image étape pour l'affichage diagnostic web.

        mode: 'bgr' | 'gray' | 'RGB'
        """
        print("Saving step: {} ({})".format(name, mode))

        base = 'Diag_Zumi_{}_{}'.format(name, uuid.uuid4().hex[:6])
        out_name = base + '.jpg'
        out_path = os.path.join(self.DIAGNOSTIC_DIR, out_name)

        if mode == 'bgr':
            to_save = img
        elif mode == 'gray':
            to_save = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif mode == 'RGB':
            to_save = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError("Unknown save mode: {}".format(mode))

        cv2.imwrite(out_path, to_save)
        url = url_for('static', filename='captured_images/diagnostics/{}'.format(out_name))
        self.steps.append({"name": name, "url": url})