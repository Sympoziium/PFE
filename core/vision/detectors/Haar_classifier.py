#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Haar_classifier.py
# ------------------
# Module de détection d'objets générique via classifieurs de Haar (cv2.CascadeClassifier).
# Supporte le chargement de multiples fichiers .xml pré-entraînés.
# Chaque classifieur est identifié par un nom (ex: 'stop_sign', 'pieton', etc.)
# et tous sont appliqués séquentiellement sur l'image pour accumuler les détections.
# Recommendations:
# - utiliser des images de basse résolution pour meilleures perf (320x240p)
# - implémenter un modèle préentraîné avant d'entrainer le notre
# - ne pas tenter de faire du real time a plus de 2-3 fps

import os, uuid
from .detector_base import BaseDetector
import cv2 
from flask import url_for
import numpy as np

class HaarDetector(BaseDetector):
    def __init__(self, scaleFactor=1.1, minNeighbors=5):
        """
        Initialise le détecteur générique basé sur des classifieurs de Haar.
        On peut y charger plusieurs fichiers .xml via add_classifier().
        
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        self.name = "HaarDetector"
        self.classifiers = {}      # {nom: cv2.CascadeClassifier}
        self.cascade_paths = {}    # {nom: chemin_xml}
        self.scaleFactor = scaleFactor
        self.minNeighbors = minNeighbors
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        # Diagnostique et logs des messages
        self.logs = []
        self.steps = []


    def add_classifier(self, name, cascade_path):
        """Ajoute un classifieur .xml à la liste.
        
        :param name: Nom identifiant le classifieur (ex: 'stop_sign').
        :param cascade_path: Chemin vers le fichier .xml du classifieur.
        """
        try:
            if not os.path.exists(cascade_path):
                print("ATTENTION: fichier cascade introuvable: {}".format(cascade_path))
            self.cascade_paths[name] = cascade_path
            classifier = cv2.CascadeClassifier(cascade_path)
            if classifier.empty():
                print("ATTENTION: le classifieur '{}' est vide (fichier invalide?)".format(name))
            self.classifiers[name] = classifier
            print("Classifieur '{}' chargé depuis: {}".format(name, cascade_path))
        except Exception as e:
            print("Erreur lors de l'ajout du classifieur {}: {}".format(name, str(e)))

    def remove_classifier(self, name):
        """Supprime un classifieur par nom."""
        if name in self.classifiers:
            try:
                del self.classifiers[name]
                del self.cascade_paths[name]
                print("Classifieur '{}' supprimé.".format(name))
            except Exception as e:
                print("Erreur lors de la suppression du classifieur {}: {}".format(name, str(e)))

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        try:
            if not isinstance(capture_dir, str):
                raise ValueError("Le chemin du dossier de capture doit être une chaîne de caractères.")
            self.CAPTURE_DIR = capture_dir
        except Exception as e:
            print("Erreur lors de l'attachement du dossier de capture: {}".format(str(e)))


    def process(self, frame, filename=None):
        """
        Analyse une image avec tous les classifieurs chargés.
        Retourne un payload standardisé compatible avec l'UI.
        Les logs contiennent le détail de chaque objet détecté par chaque classifieur.
        
        :param frame: Image à analyser (numpy array, non utilisé ici car on relit depuis le disque).
        :param filename: Nom du fichier image capturé.
        :return: Dictionnaire standardisé (voir BaseDetector).
        """
        # Réinitialisation des logs
        self.steps = []
        self.logs = []

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        # Crée le dossier de diagnostics s'il n'existe pas
        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            # Étape 1: Charger l'image capturée en BGR
            frame_bgr = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr is None:
                return {'error': 'failed to read captured image'}

            classifier_names = list(self.classifiers.keys())
            self.logs.append('=== DETECTION HAAR CASCADE ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Classifieurs charges: {}'.format(', '.join(classifier_names) if classifier_names else 'aucun'))
            self.logs.append('Config: scaleFactor={}, minNeighbors={}'.format(self.scaleFactor, self.minNeighbors))

            if not self.classifiers:
                self.logs.append('ERREUR: aucun classifieur charge. Utilisez add_classifier().')
                self.logs.append('=== FIN DETECTION ===')
                return {
                    'Object_detected': False, 'detection_box': None,
                    'confidence': 0.0, 'area': None, 'logs': self.logs,
                    'source_file_url': url_for('static', filename='captured_images/{}'.format(filename)),
                    'annotated_url': None,
                }

            # Étape 2: Filtrage + conversion en niveaux de gris
            gray = self._filter_image(frame_bgr)

            # Étape 3: Appliquer tous les classifieurs et accumuler les détections
            detections = self._detect_objects(gray, frame_bgr)

            # Étape 4: Résumé dans les logs pour la console UI
            self.logs.append('')
            self.logs.append('--- RESUME DES DETECTIONS ---')
            if detections:
                self.logs.append('Total: {} objet(s) detecte(s)'.format(len(detections)))
                # Compter les détections par classifieur
                counts = {}
                for det in detections:
                    obj_name = det['object']
                    counts[obj_name] = counts.get(obj_name, 0) + 1
                for obj_name, count in counts.items():
                    self.logs.append('  - {}: {} detection(s)'.format(obj_name, count))
            else:
                self.logs.append('Aucun objet detecte par aucun classifieur.')

            self.logs.append('=== FIN DETECTION ===')

            # Étape 5: Sauvegarder l'image annotée (toutes les bbox dessinées)
            annotated_url = None
            if detections:
                base, ext = os.path.splitext(filename)
                ann_name = '{}_haar_det{}'.format(base, ext or '.jpg')
                ann_path = os.path.join(self.CAPTURE_DIR, ann_name)
                cv2.imwrite(ann_path, frame_bgr)
                annotated_url = url_for('static', filename='captured_images/{}'.format(ann_name))

            # Étape 6: Construire le payload standardisé
            # On prend la plus grande bbox comme détection principale (pour l'indicateur UI)
            best_box = None
            best_area = 0
            for det in detections:
                bx, by, bw, bh = det['detection_box']
                a = bw * bh
                if a > best_area:
                    best_area = a
                    best_box = det['detection_box']

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            payload = {
                'Object_detected': len(detections) > 0,
                'detection_box': best_box,
                'confidence': 1.0 if detections else 0.0,
                'area': best_area if best_area > 0 else None,
                'logs': self.logs,
                'source_file_url': source_url,
                'annotated_url': annotated_url,
            }

            return payload

        except Exception as e:
            self.logs.append('ERREUR: {}'.format(str(e)))
            return {'error': 'process failed', 'details': str(e), 'logs': self.logs}

    def diagnostique_detecteur(self, filename):
        """
        Diagnostic détaillé du classificateur Haar:
        1. Validation des modèles chargés (fichier existe, non-vide, taille)
        2. Analyse de l'image source (résolution, contraste, luminosité)
        3. Prétraitements multiples: brut, GaussianBlur, equalizeHist, CLAHE
        4. Balayage de paramètres: scaleFactor × minNeighbors × minSize
        5. Résumé: nombre de combinaisons testées vs détections, meilleur résultat
        
        Sauvegarde chaque étape intermédiaire pour la galerie web.
        
        :param filename: Nom du fichier image capturé.
        :return: dict standardisé avec les étapes intermédiaires.
        """
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

            h_img, w_img = frame_bgr.shape[:2]
            classifier_names = list(self.classifiers.keys())

            # =====================================================
            # PHASE 1 : Informations générales et validation
            # =====================================================
            self.logs.append('=' * 60)
            self.logs.append('   DIAGNOSTIC COMPLET - HAAR CASCADE')
            self.logs.append('=' * 60)
            self.logs.append('')

            # --- 1a. Validation des modèles chargés ---
            self.logs.append('--- VALIDATION DES MODELES ---')
            if not classifier_names:
                self.logs.append('ERREUR: Aucun classifieur charge!')
                self.logs.append('  -> Utilisez add_classifier(nom, chemin_xml) dans main.py')
                self.logs.append('=' * 60)
                source_url = url_for('static', filename='captured_images/{}'.format(filename))
                return {
                    'Object_detected': False, 'detection_box': None,
                    'confidence': 0.0, 'area': None,
                    'logs': self.logs, 'steps': self.steps,
                    'source_file_url': source_url, 'annotated_url': None,
                }

            for cname in classifier_names:
                cpath = self.cascade_paths.get(cname, '???')
                clf = self.classifiers.get(cname)
                exists = os.path.exists(cpath)
                fsize = os.path.getsize(cpath) if exists else 0
                empty = clf.empty() if clf else True
                status = 'OK' if (exists and not empty) else 'PROBLEME'
                self.logs.append('  [{}] Classifieur: {}'.format(status, cname))
                self.logs.append('       Fichier: {}'.format(os.path.basename(cpath)))
                self.logs.append('       Existe: {}  |  Taille: {} Ko  |  Vide: {}'.format(
                    exists, round(fsize / 1024.0, 1) if exists else 0, empty))
                if empty:
                    self.logs.append('       -> ATTENTION: Ce classifieur ne detectera rien!')

            # --- 1b. Analyse de l'image source ---
            self.logs.append('')
            self.logs.append('--- ANALYSE DE L\'IMAGE SOURCE ---')
            self.logs.append('  Resolution: {}x{} pixels'.format(w_img, h_img))
            self.logs.append('  Canaux: {}'.format(frame_bgr.shape[2] if len(frame_bgr.shape) > 2 else 1))

            gray_raw = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            mean_val = float(np.mean(gray_raw))
            std_val = float(np.std(gray_raw))
            min_val = int(np.min(gray_raw))
            max_val = int(np.max(gray_raw))
            self.logs.append('  Luminosite moyenne: {:.1f}/255'.format(mean_val))
            self.logs.append('  Ecart-type (contraste): {:.1f}'.format(std_val))
            self.logs.append('  Plage intensite: [{}, {}]'.format(min_val, max_val))

            if mean_val < 50:
                self.logs.append('  -> ATTENTION: Image tres sombre, detection difficile')
            elif mean_val > 210:
                self.logs.append('  -> ATTENTION: Image tres claire/surexposee')
            if std_val < 30:
                self.logs.append('  -> ATTENTION: Faible contraste, la cascade pourrait avoir du mal')

            if w_img < 200 or h_img < 200:
                self.logs.append('  -> INFO: Basse resolution, les petits objets seront manques')
            elif w_img > 1000:
                self.logs.append('  -> INFO: Haute resolution, les petits minSize seront lents')

            # Sauvegarder l'image source
            self._save_step(frame_bgr, '0_image_source', 'bgr')

            # =====================================================
            # PHASE 2 : Prétraitements multiples
            # =====================================================
            self.logs.append('')
            self.logs.append('--- PRETRAITEMENTS ---')

            # Préparer les variantes de prétraitement
            preprocess_variants = []

            # 2a. Gray brut (aucun filtre)
            preprocess_variants.append(('gray_brut', gray_raw))
            self._save_step(gray_raw, '1a_gray_brut', 'gray')
            self.logs.append('  1. Gray brut (aucun filtrage)')

            # 2b. Gaussian blur + gray
            blurred = cv2.GaussianBlur(frame_bgr, (5, 5), 0)
            gray_blur = cv2.cvtColor(blurred, cv2.COLOR_BGR2GRAY)
            preprocess_variants.append(('gauss_blur_5x5', gray_blur))
            self._save_step(gray_blur, '1b_gaussian_blur', 'gray')
            self.logs.append('  2. GaussianBlur(5,5) + gray')

            # 2c. equalizeHist (étalement d'histogramme global)
            gray_eq = cv2.equalizeHist(gray_raw)
            preprocess_variants.append(('equalize_hist', gray_eq))
            self._save_step(gray_eq, '1c_equalize_hist', 'gray')
            self.logs.append('  3. equalizeHist (etalement histogramme global)')
            self.logs.append('     -> Utile si image sombre ou faible contraste')

            # 2d. CLAHE (Contrast Limited Adaptive Histogram Equalization)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray_raw)
            preprocess_variants.append(('CLAHE_2.0', gray_clahe))
            self._save_step(gray_clahe, '1d_CLAHE', 'gray')
            self.logs.append('  4. CLAHE (clipLimit=2.0, grid=8x8)')
            self.logs.append('     -> Egalization locale, souvent meilleur que global')

            # 2e. Bilateral filter (réduit bruit mais préserve les arêtes)
            bilateral = cv2.bilateralFilter(frame_bgr, 9, 75, 75)
            gray_bilateral = cv2.cvtColor(bilateral, cv2.COLOR_BGR2GRAY)
            preprocess_variants.append(('bilateral_filter', gray_bilateral))
            self._save_step(gray_bilateral, '1e_bilateral', 'gray')
            self.logs.append('  5. Bilateral filter (preserve les aretes)')

            # =====================================================
            # PHASE 3 : Balayage de paramètres
            # =====================================================
            self.logs.append('')
            self.logs.append('--- BALAYAGE DE PARAMETRES ---')

            scale_factors = [1.03, 1.05, 1.08, 1.1, 1.15, 1.2, 1.3]
            min_neighbors_list = [2, 3, 4, 5, 7, 10]
            min_sizes = [20, 30, 40, 60, 80]

            total_combos = len(preprocess_variants) * len(scale_factors) * len(min_neighbors_list) * len(min_sizes) * len(classifier_names)
            self.logs.append('  Pretraitements: {}'.format(len(preprocess_variants)))
            self.logs.append('  scaleFactors: {}'.format(scale_factors))
            self.logs.append('  minNeighbors: {}'.format(min_neighbors_list))
            self.logs.append('  minSizes: {}'.format(min_sizes))
            self.logs.append('  Classifieurs: {}'.format(len(classifier_names)))
            self.logs.append('  TOTAL combinaisons a tester: {}'.format(total_combos))
            self.logs.append('')

            best = {'bbox': None, 'area': 0, 'sf': None, 'mn': None, 'ms': None,
                    'preprocess': None, 'classifier': None, 'count': 0}
            total_tested = 0
            total_detected = 0
            detect_by_preprocess = {}
            detect_by_params = {}

            for prep_name, gray_img in preprocess_variants:
                detect_by_preprocess[prep_name] = 0

                for cname, clf in self.classifiers.items():
                    if clf.empty():
                        continue

                    for sf in scale_factors:
                        for mn in min_neighbors_list:
                            for ms in min_sizes:
                                total_tested += 1
                                try:
                                    results = clf.detectMultiScale(
                                        gray_img,
                                        scaleFactor=sf,
                                        minNeighbors=mn,
                                        minSize=(ms, ms)
                                    )
                                    n_det = len(results) if results is not None else 0
                                except Exception:
                                    n_det = 0

                                if n_det > 0:
                                    total_detected += 1
                                    detect_by_preprocess[prep_name] = detect_by_preprocess.get(prep_name, 0) + 1

                                    param_key = 'sf={} mn={} ms={}'.format(sf, mn, ms)
                                    detect_by_params[param_key] = detect_by_params.get(param_key, 0) + 1

                                    for (rx, ry, rw, rh) in results:
                                        a = rw * rh
                                        if a > best['area']:
                                            best.update({
                                                'bbox': (rx, ry, rw, rh), 'area': a,
                                                'sf': sf, 'mn': mn, 'ms': ms,
                                                'preprocess': prep_name,
                                                'classifier': cname, 'count': n_det
                                            })

            # =====================================================
            # PHASE 4 : Rapport détaillé
            # =====================================================
            self.logs.append('--- RESULTATS DU BALAYAGE ---')
            self.logs.append('  Combinaisons testees: {}'.format(total_tested))
            self.logs.append('  Combinaisons avec detection: {} ({:.1f}%)'.format(
                total_detected, (100.0 * total_detected / total_tested) if total_tested > 0 else 0))
            self.logs.append('')

            # Détections par prétraitement
            self.logs.append('  Detections par pretraitement:')
            for pname, count in sorted(detect_by_preprocess.items(), key=lambda x: -x[1]):
                bar = '#' * min(count, 40)
                self.logs.append('    {:<20s}: {:>4d}  {}'.format(pname, count, bar))

            self.logs.append('')

            # Top 10 combinaisons de paramètres les plus productives
            self.logs.append('  Top parametres (combinaisons les plus productives):')
            sorted_params = sorted(detect_by_params.items(), key=lambda x: -x[1])[:10]
            for param_key, count in sorted_params:
                self.logs.append('    {}: {} detection(s)'.format(param_key, count))

            self.logs.append('')

            # Meilleur résultat
            if best['bbox']:
                bx, by, bw, bh = best['bbox']
                self.logs.append('  *** MEILLEURE DETECTION ***')
                self.logs.append('  Classifieur: {}'.format(best['classifier']))
                self.logs.append('  Pretraitement: {}'.format(best['preprocess']))
                self.logs.append('  Parametres: scaleFactor={}, minNeighbors={}, minSize=({},{})'.format(
                    best['sf'], best['mn'], best['ms'], best['ms']))
                self.logs.append('  BBox: x={}, y={}, w={}, h={}'.format(bx, by, bw, bh))
                self.logs.append('  Aire: {} px'.format(best['area']))
                self.logs.append('  Nb detections dans cette config: {}'.format(best['count']))

                # Sauvegarder la meilleure détection annotée
                overlay = frame_bgr.copy()
                cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (0, 255, 0), 2)
                label = '{} ({}x{})'.format(best['classifier'], bw, bh)
                cv2.putText(overlay, label, (bx, max(0, by - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                info = 'sf={} mn={} ms={} prep={}'.format(best['sf'], best['mn'], best['ms'], best['preprocess'])
                cv2.putText(overlay, info, (5, h_img - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
                self._save_step(overlay, 'best_detection', 'bgr')
            else:
                self.logs.append('  AUCUNE DETECTION sur {} combinaisons.'.format(total_tested))
                self.logs.append('')
                self.logs.append('  Causes possibles:')
                self.logs.append('    1. Modele XML non adapte a l\'objet cible (ex: entraine sur "STOP" vs "ARRET")')
                self.logs.append('    2. Objet trop petit ou trop grand par rapport a minSize')
                self.logs.append('    3. Angle, eclairage ou occlusion too severe')
                self.logs.append('    4. Image de basse qualite / floue')
                self.logs.append('    5. Fichier .xml corrompu ou vide')
                self.logs.append('')
                self.logs.append('  Recommandations:')
                self.logs.append('    - Essayer un autre modele .xml pre-entraine')
                self.logs.append('    - Verifier que l\'objet est bien visible dans l\'image source')
                self.logs.append('    - Tester avec une image web contenant clairement l\'objet cible')
                self.logs.append('    - Considerer l\'entrainement d\'un modele custom')

            self.logs.append('')
            self.logs.append('=' * 60)
            self.logs.append('   FIN DU DIAGNOSTIC')
            self.logs.append('=' * 60)

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

    def _filter_image(self, frame, diagnostic_mode=False):
        """
        Applique un filtrage à l'image pour réduire le bruit et améliorer la détection.
        Si diagnostic_mode est True, sauvegarde les étapes de filtrage pour l'affichage web.
        """
        # Appliquer un flou gaussien pour réduire le bruit
        img_filter = cv2.GaussianBlur(frame, (5, 5), 0)
        if diagnostic_mode:
            self._save_step(img_filter, '1_gaussian_blur', 'bgr')

        # Convertir en niveaux de gris
        gray_filtered = cv2.cvtColor(img_filter, cv2.COLOR_BGR2GRAY)
        if diagnostic_mode:
            self._save_step(gray_filtered, '2_gray_filtered', 'gray')

        return gray_filtered


    def _detect_objects(self, gray_filtered, frame_bgr, diagnostic_mode=False):
        """
        Parcourt tous les classifieurs chargés et accumule les détections.
        Dessine les bbox + labels directement sur frame_bgr (pour l'annotation).
        
        :param gray_filtered: Image en niveaux de gris filtrée.
        :param frame_bgr: Image BGR originale (sera annotée en place).
        :param diagnostic_mode: Si True, sauvegarde après chaque classifieur.
        :return: Liste de dicts [{'object': nom, 'detected': True, 'detection_box': (x,y,w,h)}, ...]
        """
        detections = []

        for name, classifier in self.classifiers.items():
            self.logs.append('')
            self.logs.append('--- Classifieur: {} ---'.format(name))

            if classifier.empty():
                self.logs.append('  ATTENTION: classifieur vide, ignore.')
                continue

            results = classifier.detectMultiScale(
                gray_filtered,
                scaleFactor=self.scaleFactor,
                minNeighbors=self.minNeighbors
            )

            # test de détection
            if len(results) == 0:
                self.logs.append('  Aucune detection.')
                continue

            self.logs.append('  {} detection(s) trouvee(s):'.format(len(results)))

            for i, (x, y, w, h) in enumerate(results):
                self.logs.append('    #{}: pos=({},{}) taille={}x{} aire={}'.format(
                    i + 1, x, y, w, h, w * h))

                # Dessiner le rectangle et le label sur l'image
                cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(frame_bgr, "{}".format(name), (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                detections.append({
                    "object": name,
                    "detected": True,
                    "detection_box": (x, y, w, h)
                })

            if diagnostic_mode:
                self._save_step(frame_bgr, '3_detection_{}'.format(name), 'bgr')

        return detections

    
    def _save_step(self, img, name, mode):
        """
        Sauvegarde toutes les images pour l'affichage web.
        cv2.imwrite() attend du BGR, donc on convertit tout vers BGR avant sauvegarde.

        mode:
        'bgr'   -> image BGR OpenCV (deja en BGR, pas de conversion)
        'gray'  -> image 1 canal (converti vers BGR 3 canaux)
        'hsv'   -> image HSV (convertie vers BGR)
        'RGB'   -> image RGB (convertie vers BGR)

        """
        print("Saving step: {} ({})".format(name, mode))

        base = 'Diag_Haar_{}_{}'.format(name, uuid.uuid4().hex[:6])
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
