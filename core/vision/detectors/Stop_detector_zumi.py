#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Stop_detector_zumi.py
# ------------------
# Ce module implémente le détecteur de panneau stop pour le robot Zumi
# en utilisant la bibliothèque Zumi (zumi.util.vision.Vision).
# La bibliothèque utilise un classifieur Haar pré-optimisé pour le Zumi.
# Ce détecteur inclut un mode diagnostic qui teste différentes combinaisons
# de paramètres (scaleFactor, minNeighbors, minSize) en BGR et RGB
# pour aider à trouver les réglages optimaux.

import os, uuid
from .detector_base import BaseDetector
from zumi.util.vision import Vision

import cv2
from flask import url_for

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
        self.logs = []
        self.steps = []

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process(self, frame, filename=None):
        """Analyse une image pour détecter un panneau stop via la lib Zumi.

        Supporte deux modes:
        - Avec filename: charge l'image depuis le disque (mode UI)
        - Sans filename: utilise le frame passé directement (mode legacy/pipeline)

        Args:
            frame: image BGR (numpy array).
            filename: nom du fichier image capturé (optionnel).
        Returns:
            dict: payload standardisé conforme à BaseDetector.
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

            stop_detected = bbox is not None

            if stop_detected:
                x, y, w, h = bbox
                self.logs.append('Resultat: STOP DETECTE')
                self.logs.append('  Position: x={}, y={}'.format(x, y))
                self.logs.append('  Taille: {}x{}, aire={}'.format(w, h, w * h))
            else:
                self.logs.append('Resultat: Aucun panneau stop detecte')

            self.logs.append('=== FIN DETECTION ===')

            # Construire l'URL source si filename disponible
            source_url = None
            if filename:
                source_url = url_for('static', filename='captured_images/{}'.format(filename))

            # Sauvegarder image annotée si détection
            annotated_url = None
            if stop_detected and filename and self.CAPTURE_DIR:
                x, y, w, h = bbox
                annotated = frame_bgr.copy()
                cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(annotated, 'STOP', (x, max(0, y - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                base, ext = os.path.splitext(filename)
                ann_name = '{}_zumi_det{}'.format(base, ext or '.jpg')
                ann_path = os.path.join(self.CAPTURE_DIR, ann_name)
                cv2.imwrite(ann_path, annotated)
                annotated_url = url_for('static', filename='captured_images/{}'.format(ann_name))

            payload = {
                'Object_detected': stop_detected,
                'detection_box': tuple(bbox) if bbox else None,
                'confidence': 1.0 if stop_detected else 0.0,
                'area': (bbox[2] * bbox[3]) if bbox else None,
                'logs': self.logs,
                'source_file_url': source_url,
                'annotated_url': annotated_url,
            }
            return payload

        except Exception as e:
            self.logs.append('ERREUR: {}'.format(str(e)))
            import traceback
            traceback.print_exc()
            return {'error': 'process failed', 'details': str(e), 'logs': self.logs}

    def diagnostique_detecteur(self, filename):
        """Diagnostic détaillé: balayage de paramètres (scaleFactor, minNeighbors, minSize)
        en BGR et RGB pour trouver les meilleurs réglages.
        
        Sauvegarde les résultats annotés et retourne un payload avec les étapes
        et le meilleur résultat trouvé.
        
        :param filename: Nom du fichier image capturé.
        :return: dict standardisé avec logs, steps, et résultats.
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
            self.logs.append('Balayage de parametres en cours...')
            self.logs.append('')

            # Sauvegarder image source
            self._save_step(frame_bgr, '0_image_source', 'bgr')

            # Paramètres à balayer
            scale_factors = [1.03, 1.05, 1.08, 1.12, 1.15, 1.20]
            min_neighbors_list = [3, 5, 7, 8, 10, 12]
            min_sizes = [24, 32, 40, 56, 80]

            best = {'bbox': None, 'area': 0, 'sf': None, 'mn': None, 'ms': None, 'space': None}
            total_tested = 0
            total_detected = 0

            for sf in scale_factors:
                for mn in min_neighbors_list:
                    for ms in min_sizes:
                        for space_tag, img in (('BGR', frame_bgr), ('RGB', frame_rgb)):
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
                                    x, y, w, h = det_raw
                                    area = w * h
                                    self.logs.append('{} sf={} mn={} ms={} -> DETECTE ({}x{}, aire={})'.format(
                                        space_tag, sf, mn, ms, w, h, area))

                                    if area > best['area']:
                                        best.update({
                                            'bbox': det_raw, 'area': area,
                                            'sf': sf, 'mn': mn, 'ms': ms, 'space': space_tag
                                        })

                                        # Sauvegarder la meilleure détection
                                        overlay = frame_bgr.copy()
                                        cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 255, 0), 2)
                                        label = '{} sf={} mn={} ms={}'.format(space_tag, sf, mn, ms)
                                        cv2.putText(overlay, label, (x, max(0, y - 10)),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                        step_name = 'best_{}_sf{}_mn{}_ms{}'.format(
                                            space_tag, str(sf).replace('.', '_'), mn, ms)
                                        self._save_step(overlay, step_name, 'bgr')

                            except Exception as e:
                                self.logs.append('{} sf={} mn={} ms={} -> ERREUR: {}'.format(
                                    space_tag, sf, mn, ms, str(e)))

            self.logs.append('')
            self.logs.append('--- RESUME DU BALAYAGE ---')
            self.logs.append('Combinaisons testees: {}'.format(total_tested))
            self.logs.append('Detections: {}'.format(total_detected))

            if best['bbox']:
                self.logs.append('Meilleure detection:')
                self.logs.append('  Espace: {}'.format(best['space']))
                self.logs.append('  scaleFactor: {}'.format(best['sf']))
                self.logs.append('  minNeighbors: {}'.format(best['mn']))
                self.logs.append('  minSize: ({0},{0})'.format(best['ms']))
                self.logs.append('  BBox: x={}, y={}, w={}, h={}'.format(*best['bbox']))
                self.logs.append('  Aire: {}'.format(best['area']))
            else:
                self.logs.append('Aucune detection sur aucune combinaison.')

            self.logs.append('=== FIN DIAGNOSTIC ===')

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            return {
                'Object_detected': best['bbox'] is not None,
                'detection_box': tuple(best['bbox']) if best['bbox'] else None,
                'confidence': 1.0 if best['bbox'] else 0.0,
                'area': best['area'] if best['area'] > 0 else None,
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