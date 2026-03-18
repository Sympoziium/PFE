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

import os, uuid, time
from .detector_base import BaseDetector
import cv2
import numpy as np

try:
    from flask import url_for
except ImportError:          # url_for n'est utilisé que par le diagnostic
    url_for = None

class HaarDetector(BaseDetector):
    def __init__(self):
        """
        Initialise le détecteur générique basé sur des classifieurs de Haar.
        On peut y charger plusieurs fichiers .xml via add_classifier().
        
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        self.name = "HaarDetector"
        self.classifiers = {}      # {nom: cv2.CascadeClassifier}
        self.cascade_paths = {}    # {nom: chemin_xml}
        self.CAPTURE_DIR = None
        self.DIAGNOSTIC_DIR = None
        self.debug = False  # Flag de debug pour les fonctions d'annotation et de diagnostic
        # Diagnostique et logs des messages
        self.logs = []
        self.steps = []
        
    @property
    def classes(self):
        """Retourne la liste des noms de classes (les noms des classifieurs chargés)."""
        return list(self.classifiers.keys())
        
    def add_classifier(self, name, cascade_path, scaleFactor=1.1, minNeighbors=5):
        """Ajoute un classifieur .xml à la liste.
        
        :param name: Nom identifiant le classifieur (ex: 'stop_sign').
        :param cascade_path: Chemin vers le fichier .xml du classifieur.
        :param scaleFactor: Facteur de réduction d'image à chaque échelle.
        :param minNeighbors: Nombre minimum de voisins pour qu'une détection soit retenue.
        """
        try:
            if not os.path.exists(cascade_path):
                print("ATTENTION: fichier cascade introuvable: {}".format(cascade_path))
            self.cascade_paths[name] = cascade_path
            classifier = cv2.CascadeClassifier(cascade_path)
            if classifier.empty():
                print("ATTENTION: le classifieur '{}' est vide (fichier invalide?)".format(name))
            self.classifiers[name] = {
                'classifier': classifier,
                'scaleFactor': scaleFactor,
                'minNeighbors': minNeighbors
            }
            if self.debug:
                print("Classifieur '{}' chargé depuis: {}".format(name, cascade_path))
        except Exception as e:
            print("Erreur lors de l'ajout du classifieur {}: {}".format(name, str(e)))

    def remove_classifier(self, name):
        """Supprime un classifieur par nom."""
        if name in self.classifiers:
            try:
                del self.classifiers[name]
                del self.cascade_paths[name]
                if self.debug:
                    print("Classifieur '{}' supprimé.".format(name))
            except Exception as e:
                print("Erreur lors de la suppression du classifieur {}: {}".format(name, str(e)))

    def get_classifier_attributes(self, name):
        """Retourne les attributs d'un classifieur donné (ex: scaleFactor, minNeighbors)."""
        clf_entry = self.classifiers.get(name)
        if clf_entry:
            return {
                'scaleFactor': clf_entry['scaleFactor'],
                'minNeighbors': clf_entry['minNeighbors'],
                'cascade_path': self.cascade_paths.get(name, '')
            }
        else:
            if self.debug:
                print("Classifieur '{}' non trouvé.".format(name))
            return None

    def get_classifier_name_list(self):
        """Retourne la liste des classifieurs chargés."""
        return list(self.classifiers.keys())

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        try:
            if not isinstance(capture_dir, str):
                raise ValueError("Le chemin du dossier de capture doit être une chaîne de caractères.")
            self.CAPTURE_DIR = capture_dir
        except Exception as e:
            print("Erreur lors de l'attachement du dossier de capture: {}".format(str(e)))


    # cette méthode est appelé pour faire la détection, elle lie une image enregistré
    # pour de la détection single shot ces good, mais pour le pasive, on devrais lui passer une frame
    # sa ferais réduire la latence en évitant de devoir charger une image du disque
    def process(self, frame, filename=None):
        """
        Analyse une image avec tous les classifieurs chargés.
        Retourne un payload standardisé **sans annotation** sur l'image.

        :param frame: Image BGR (numpy array).
        :param filename: Nom du fichier image capturé.
        :return: dict standardisé {Object_detected, detections, logs}.
        """
        # Réinitialisation des logs
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
            classifier_names = list(self.classifiers.keys())
            self.logs.append('=== DETECTION HAAR CASCADE ===')
            self.logs.append('Image: {}x{}'.format(frame_bgr.shape[1], frame_bgr.shape[0]))
            self.logs.append('Classifieurs charges: {}'.format(', '.join(classifier_names) if classifier_names else 'aucun'))
            if classifier_names:
                self.logs.append('Config: scaleFactor={}, minNeighbors={}'.format(
                    self.classifiers[classifier_names[0]]['scaleFactor'],
                    self.classifiers[classifier_names[0]]['minNeighbors']))

            if not self.classifiers:
                self.logs.append('ERREUR: aucun classifieur charge. Utilisez add_classifier().')
                self.logs.append('=== FIN DETECTION ===')
                return {
                    'Object_detected': False,
                    'detections': [],
                    'logs': self.logs,
                }

            # Filtrage + conversion en niveaux de gris
            gray = self._filter_image(frame_bgr)

            # Appliquer tous les classifieurs et accumuler les détections
            detections = self._detect_objects(gray, frame_bgr)

            # Résumé dans les logs
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

            return {
                'Object_detected': len(detections) > 0,
                'detections': detections,
                'logs': self.logs,
            }

        except Exception as e:
            self.logs.append('ERREUR: {}'.format(str(e)))
            return {'error': 'process failed', 'details': str(e), 'logs': self.logs}

    def process_passive(self, frame_bgr):
        """Détection passive optimisée pour le live feed.

        Retourne le format standardisé (sans overlay ni logs).

        :param frame_bgr: Image BGR (format OpenCV natif) à analyser.
        :return: dict {Object_detected, detections, timestamp}.
        """
        if frame_bgr is None or not self.classifiers:
            return {'Object_detected': False, 'detections': [], 'timestamp': time.time()}

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

        detections = []
        for name, clf_entry in self.classifiers.items():
            clf = clf_entry['classifier']
            if clf.empty():
                continue
            try:
                results = clf.detectMultiScale(
                    gray,
                    scaleFactor=clf_entry['scaleFactor'],
                    minNeighbors=clf_entry['minNeighbors'],
                    minSize=(20, 20)
                )
                if len(results) > 0:
                    x, y, w_box, h_box = [int(v) for v in results[0]]  # on prend la première détection pour la réactivité
                    detections.append({
                        'object': name,
                        'detection_box': (x, y, w_box, h_box)
                    })
            except Exception as e:
                print("Erreur lors de la détection passive avec le classifieur '{}': {}".format(name, str(e)))
                continue
        return {
            'Object_detected': len(detections) > 0,
            'detections': detections,
            'timestamp': time.time()
        }

# il faudrais revoir la méthode de diagnostique pour qu'elle soit mieux adapté aux modèles actuel. on veux pouvoir tester nos modèles déployer
    def diagnostique_detecteur(self, filename):
        """
        Diagnostic détaillé du classificateur Haar:
        0. Parse du XML pour extraire la taille de fenêtre d'entraînement
        1. Validation des modèles chargés (fichier, taille, fenêtre training)
        2. Analyse de l'image source (résolution, contraste, luminosité)
        3. Redimensionnement si l'image dépasse 400px (perf Pi Zero)
        4. Test rapide avec les paramètres de l'auteur du modèle
        5. Prétraitements: brut, GaussianBlur, CLAHE (3 variantes)
        6. Balayage de paramètres réduit (~81 combos au lieu de 1050+)
        7. Rapport: meilleur résultat, stats, recommandations
        
        :param filename: Nom du fichier image capturé.
        :return: dict standardisé avec les étapes intermédiaires.
        """
        self.steps = []
        self.logs = []
        t_start = time.time()

        if not filename:
            return {'error': 'no captured image available. Please capture an image first.'}

        img_path = os.path.join(self.CAPTURE_DIR, filename)
        if not os.path.exists(img_path):
            return {'error': 'last captured image not found on server'}

        self.DIAGNOSTIC_DIR = os.path.join(self.CAPTURE_DIR, 'diagnostics')
        os.makedirs(self.DIAGNOSTIC_DIR, exist_ok=True)

        try:
            frame_bgr_orig = cv2.imread(img_path, cv2.IMREAD_COLOR)
            if frame_bgr_orig is None:
                return {'error': 'failed to read captured image'}

            h_orig, w_orig = frame_bgr_orig.shape[:2]
            classifier_names = list(self.classifiers.keys())

            # =====================================================
            # PHASE 0 : Parse des fichiers XML pour metadata
            # =====================================================
            training_sizes = {}  # {cname: (w, h) ou None}
            for cname in classifier_names:
                cpath = self.cascade_paths.get(cname, '')
                training_sizes[cname] = self._parse_cascade_xml(cpath)

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
                clf_entry = self.classifiers.get(cname)
                # clf_entry est un dict {'classifier': ..., 'scaleFactor': ..., 'minNeighbors': ...}
                clf = clf_entry['classifier'] if isinstance(clf_entry, dict) else clf_entry
                exists = os.path.exists(cpath)
                fsize = os.path.getsize(cpath) if exists else 0
                empty = clf.empty() if clf else True
                status = 'OK' if (exists and not empty) else 'PROBLEME'
                tsize = training_sizes.get(cname)

                self.logs.append('  [{}] Classifieur: {}'.format(status, cname))
                self.logs.append('       Fichier: {}'.format(os.path.basename(cpath)))
                self.logs.append('       Existe: {}  |  Taille: {} Ko  |  Vide: {}'.format(
                    exists, round(fsize / 1024.0, 1) if exists else 0, empty))

                if tsize:
                    tw, th = tsize
                    ratio = float(tw) / float(th) if th > 0 else 0
                    self.logs.append('       Fenetre entrainement: {}x{} px (ratio w/h = {:.2f})'.format(tw, th, ratio))
                    if ratio < 0.8 or ratio > 1.25:
                        self.logs.append('       -> INFO: Fenetre NON carree. Le modele attend des objets {}.'
                            .format('plus hauts que larges' if ratio < 1 else 'plus larges que hauts'))
                        self.logs.append('          Le minSize du sweep sera ajuste pour respecter ce ratio.')
                else:
                    self.logs.append('       Fenetre entrainement: non trouvee dans le XML')

                if empty:
                    self.logs.append('       -> ATTENTION: Ce classifieur ne detectera rien!')

            # --- 1b. Analyse de l'image source ---
            self.logs.append('')
            self.logs.append('--- ANALYSE DE L\'IMAGE SOURCE ---')
            self.logs.append('  Resolution originale: {}x{} pixels'.format(w_orig, h_orig))
            self.logs.append('  Canaux: {}'.format(frame_bgr_orig.shape[2] if len(frame_bgr_orig.shape) > 2 else 1))

            gray_raw_orig = cv2.cvtColor(frame_bgr_orig, cv2.COLOR_BGR2GRAY)
            mean_val = float(np.mean(gray_raw_orig))
            std_val = float(np.std(gray_raw_orig))
            min_val = int(np.min(gray_raw_orig))
            max_val = int(np.max(gray_raw_orig))
            self.logs.append('  Luminosite moyenne: {:.1f}/255'.format(mean_val))
            self.logs.append('  Ecart-type (contraste): {:.1f}'.format(std_val))
            self.logs.append('  Plage intensite: [{}, {}]'.format(min_val, max_val))

            if mean_val < 50:
                self.logs.append('  -> ATTENTION: Image tres sombre, detection difficile')
            elif mean_val > 210:
                self.logs.append('  -> ATTENTION: Image tres claire/surexposee')
            if std_val < 30:
                self.logs.append('  -> ATTENTION: Faible contraste, la cascade pourrait avoir du mal')

            # Sauvegarder l'image source originale
            self._save_step(frame_bgr_orig, '0_image_source', 'bgr')

            # =====================================================
            # PHASE 2 : Redimensionnement pour performance
            # =====================================================
            MAX_DIAG_WIDTH = 400
            if w_orig > MAX_DIAG_WIDTH:
                scale = float(MAX_DIAG_WIDTH) / float(w_orig)
                new_w = MAX_DIAG_WIDTH
                new_h = int(h_orig * scale)
                frame_bgr = cv2.resize(frame_bgr_orig, (new_w, new_h), interpolation=cv2.INTER_AREA)
                self.logs.append('')
                self.logs.append('  -> Image redimensionnee pour diagnostic: {}x{} (facteur {:.2f})'.format(
                    new_w, new_h, scale))
                self.logs.append('     (La Haar cascade est multi-echelle, la haute resolution')
                self.logs.append('      n\'ameliore pas la detection mais ralentit enormement)')
            else:
                frame_bgr = frame_bgr_orig
                new_w, new_h = w_orig, h_orig

            h_img, w_img = frame_bgr.shape[:2]
            gray_raw = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)

            # =====================================================
            # PHASE 3 : Test rapide (parametres de l'auteur)
            # =====================================================
            self.logs.append('')
            self.logs.append('--- TEST RAPIDE (parametres nominaux) ---')
            self.logs.append('  But: verifier si le modele detecte QUOI QUE CE SOIT')
            self.logs.append('  Parametres: scaleFactor=1.05, minNeighbors=3, minSize=(5,5)')
            self.logs.append('  (Ce sont les parametres les plus permissifs de l\'auteur)')

            gray_blur_quick = cv2.GaussianBlur(gray_raw, (5, 5), 0)
            quick_found = False
            for cname, clf in self.classifiers.items():
                if clf['classifier'].empty():
                    continue
                try:
                    qresults = clf['classifier'].detectMultiScale(
                        gray_blur_quick,
                        scaleFactor=1.05, ## on hardcode les param pour augmenter les detections du test rapide
                        minNeighbors=3,
                        minSize=(5, 5)
                    )
                    n_q = len(qresults)
                except Exception:
                    n_q = 0

                if n_q > 0:
                    quick_found = True
                    self.logs.append('  [{}] {} detection(s) -> Le modele FONCTIONNE sur cette image'.format(cname, n_q))
                    for qi, (qx, qy, qw, qh) in enumerate(qresults):
                        self.logs.append('    #{}: pos=({},{}) taille={}x{}'.format(qi + 1, qx, qy, qw, qh))
                    # Sauvegarder le résultat du quick test
                    overlay_q = frame_bgr.copy()
                    for (qx, qy, qw, qh) in qresults:
                        cv2.rectangle(overlay_q, (qx, qy), (qx + qw, qy + qh), (255, 0, 255), 2)
                    self._save_step(overlay_q, '2_quick_test_{}'.format(cname), 'bgr')
                else:
                    self.logs.append('  [{}] 0 detection -> Ce modele ne detecte rien meme en mode permissif'.format(cname))

            if not quick_found:
                self.logs.append('')
                self.logs.append('  CONCLUSION: Aucun modele ne detecte quoi que ce soit.')
                self.logs.append('  Le balayage de parametres va quand meme etre lance, mais il')
                self.logs.append('  est probable que le modele ne soit pas adapte a cette image.')
                self.logs.append('  Verifiez:')
                self.logs.append('    - Le panneau est-il bien visible et non occulte?')
                self.logs.append('    - Le modele a-t-il ete entraine sur le bon type d\'objet?')
                self.logs.append('      (ex: panneau "STOP" americain vs "ARRET" quebecois)')
                self.logs.append('    - La qualite/resolution de l\'image est-elle suffisante?')

            t_phase3 = time.time()
            self.logs.append('  [Temps phase 1-3: {:.1f}s]'.format(t_phase3 - t_start))

            # =====================================================
            # PHASE 4 : Prétraitements (3 variantes pour Pi Zero)
            # =====================================================
            self.logs.append('')
            self.logs.append('--- PRETRAITEMENTS ---')

            preprocess_variants = []

            # 4a. Gray brut
            preprocess_variants.append(('gray_brut', gray_raw))
            self._save_step(gray_raw, '3a_gray_brut', 'gray')
            self.logs.append('  1. Gray brut (aucun filtrage)')

            # 4b. Gaussian blur + gray (comme l'auteur du modèle)
            preprocess_variants.append(('gauss_blur_5x5', gray_blur_quick))
            self._save_step(gray_blur_quick, '3b_gaussian_blur', 'gray')
            self.logs.append('  2. GaussianBlur(5,5) + gray (comme l\'auteur)')

            # 4c. CLAHE (meilleur que equalizeHist en général)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray_raw)
            preprocess_variants.append(('CLAHE_2.0', gray_clahe))
            self._save_step(gray_clahe, '3c_CLAHE', 'gray')
            self.logs.append('  3. CLAHE (clipLimit=2.0, grid=8x8)')

            # =====================================================
            # PHASE 5 : Analyse adaptative
            # Si le quick test a détecté : test rapide par prétraitement
            # Si rien détecté : balayage complet (mode recherche)
            # =====================================================
            best = {'bbox': None, 'area': 0, 'sf': None, 'mn': None, 'ms': None,
                    'preprocess': None, 'classifier': None, 'count': 0}

            t_sweep_start = time.time()

            if quick_found:
                # ----- MODE RAPIDE : le modèle fonctionne, comparer les prétraitements -----
                self.logs.append('')
                self.logs.append('--- COMPARAISON DES PRETRAITEMENTS (mode rapide) ---')
                self.logs.append('  Le quick test a detecte, pas besoin de balayage exhaustif.')
                self.logs.append('  On teste chaque pretraitement avec les params par defaut.')
                self.logs.append('')

                for prep_name, gray_img in preprocess_variants:
                    for cname, clf in self.classifiers.items():
                        if clf['classifier'].empty():
                            continue
                        try:
                            results = clf['classifier'].detectMultiScale(
                                gray_img,
                                scaleFactor=clf['scaleFactor'],
                                minNeighbors=clf['minNeighbors'],
                                minSize=(5, 5)
                            )
                            n_det = len(results) if results is not None else 0
                        except Exception:
                            n_det = 0

                        if n_det > 0:
                            self.logs.append('  [{}] {}: {} detection(s)'.format(cname, prep_name, n_det))
                            for (rx, ry, rw, rh) in results:
                                a = int(rw) * int(rh)
                                self.logs.append('    -> pos=({},{}) taille={}x{} aire={}'.format(
                                    int(rx), int(ry), int(rw), int(rh), a))
                                if a > best['area']:
                                    best.update({
                                        'bbox': (int(rx), int(ry), int(rw), int(rh)), 'area': a,
                                        'sf': clf['scaleFactor'], 'mn': clf['minNeighbors'],
                                        'ms': '(5,5)',
                                        'preprocess': prep_name,
                                        'classifier': cname, 'count': n_det
                                    })
                        else:
                            self.logs.append('  [{}] {}: 0 detection'.format(cname, prep_name))
            else:
                # ----- MODE RECHERCHE : rien détecté, balayage complet -----
                self.logs.append('')
                self.logs.append('--- BALAYAGE DE PARAMETRES (mode recherche) ---')
                self.logs.append('  Aucune detection au quick test, recherche exhaustive...')

                scale_factors = [1.05, 1.1, 1.2]
                min_neighbors_list = [3, 5, 8]

                # Construire la liste de minSizes avec ratio d'entraînement
                base_sizes = [15, 30, 50]
                min_size_list = [(bs, bs) for bs in base_sizes]

                # Ajuster les minSizes pour respecter le ratio d'entraînement si disponible
                for cname, tsize in training_sizes.items():
                    if tsize:
                        tw, th = tsize
                        ratio = float(tw) / float(th) if th > 0 else 1.0
                        if ratio < 0.8 or ratio > 1.25:
                            for bs in base_sizes:
                                adjusted_w = max(5, int(bs * ratio))
                                pair = (adjusted_w, bs)
                                if pair not in min_size_list:
                                    min_size_list.append(pair)
                                    self.logs.append('  + minSize ajuste au ratio training: ({},{})'.format(adjusted_w, bs))

                total_combos = len(preprocess_variants) * len(scale_factors) * len(min_neighbors_list) * len(min_size_list) * len(classifier_names)
                self.logs.append('  Combinaisons a tester: {}'.format(total_combos))
                self.logs.append('')

                total_tested = 0
                total_detected = 0
                detect_by_preprocess = {}

                for prep_name, gray_img in preprocess_variants:
                    detect_by_preprocess[prep_name] = 0
                    for cname, clf in self.classifiers.items():
                        if clf['classifier'].empty():
                            continue
                        for sf in scale_factors:
                            for mn in min_neighbors_list:
                                for ms_w, ms_h in min_size_list:
                                    total_tested += 1
                                    try:
                                        results = clf['classifier'].detectMultiScale(
                                            gray_img,
                                            scaleFactor=sf,
                                            minNeighbors=mn,
                                            minSize=(ms_w, ms_h)
                                        )
                                        n_det = len(results) if results is not None else 0
                                    except Exception:
                                        n_det = 0

                                    if n_det > 0:
                                        total_detected += 1
                                        detect_by_preprocess[prep_name] = detect_by_preprocess.get(prep_name, 0) + 1
                                        for (rx, ry, rw, rh) in results:
                                            a = int(rw) * int(rh)
                                            if a > best['area']:
                                                best.update({
                                                    'bbox': (int(rx), int(ry), int(rw), int(rh)), 'area': a,
                                                    'sf': sf, 'mn': mn,
                                                    'ms': '({},{})'.format(ms_w, ms_h),
                                                    'preprocess': prep_name,
                                                    'classifier': cname, 'count': n_det
                                                })

                self.logs.append('  Combinaisons testees: {}'.format(total_tested))
                self.logs.append('  Avec detection: {} ({:.1f}%)'.format(
                    total_detected, (100.0 * total_detected / total_tested) if total_tested > 0 else 0))
                self.logs.append('')
                self.logs.append('  Detections par pretraitement:')
                for pname, count in sorted(detect_by_preprocess.items(), key=lambda x: -x[1]):
                    bar = '#' * min(count, 40)
                    self.logs.append('    {:<20s}: {:>4d}  {}'.format(pname, count, bar))

            t_sweep_end = time.time()

            # =====================================================
            # PHASE 6 : Rapport final
            # =====================================================
            self.logs.append('')
            self.logs.append('--- RAPPORT FINAL ---')
            self.logs.append('  Temps analyse: {:.1f}s'.format(t_sweep_end - t_sweep_start))

            if best['bbox']:
                bx, by, bw, bh = best['bbox']

                # Si l'image a été redimensionnée, remettre les coordonnées à l'échelle originale
                if w_orig > MAX_DIAG_WIDTH:
                    inv_scale = float(w_orig) / float(MAX_DIAG_WIDTH)
                    bx_orig = int(bx * inv_scale)
                    by_orig = int(by * inv_scale)
                    bw_orig = int(bw * inv_scale)
                    bh_orig = int(bh * inv_scale)
                else:
                    bx_orig, by_orig, bw_orig, bh_orig = int(bx), int(by), int(bw), int(bh)

                self.logs.append('')
                self.logs.append('  *** MEILLEURE DETECTION ***')
                self.logs.append('  Classifieur: {}'.format(best['classifier']))
                self.logs.append('  Pretraitement: {}'.format(best['preprocess']))
                self.logs.append('  Parametres: scaleFactor={}, minNeighbors={}, minSize={}'.format(best['sf'], best['mn'], best['ms']))
                self.logs.append('  BBox: x={}, y={}, w={}, h={}'.format(bx_orig, by_orig, bw_orig, bh_orig))
                self.logs.append('  Aire: {} px'.format(best['area']))

                # Sauvegarder la meilleure détection annotée sur l'image ORIGINALE
                overlay = frame_bgr_orig.copy()
                cv2.rectangle(overlay, (bx_orig, by_orig),
                    (bx_orig + bw_orig, by_orig + bh_orig), (0, 255, 0), 2)
                label = '{} ({}x{})'.format(best['classifier'], bw_orig, bh_orig)
                cv2.putText(overlay, label, (bx_orig, max(0, by_orig - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                self._save_step(overlay, 'best_detection', 'bgr')

                # Recommandations post-détection
                self.logs.append('')
                self.logs.append('  Recommandation: utilisez ces parametres dans process():')
                self.logs.append('    add_classifier("{}", "chemin/vers/{}.xml", scaleFactor={}, minNeighbors={})'.format(
                    best['classifier'], best['classifier'], best['sf'], best['mn']))
            else:
                self.logs.append('')
                self.logs.append('  AUCUNE DETECTION.')
                self.logs.append('')
                self.logs.append('  Causes possibles:')
                self.logs.append('    1. Modele XML non adapte a l\'objet cible')
                self.logs.append('       (ex: entraine sur "STOP" americain vs "ARRET" quebecois)')
                self.logs.append('    2. Objet absent, trop petit, ou hors champ')
                self.logs.append('    3. Angle de vue, eclairage ou occlusion trop severe')
                self.logs.append('    4. Image floue ou de basse qualite')
                self.logs.append('')
                self.logs.append('  Recommandations:')
                self.logs.append('    1. Tester avec une image web d\'un panneau "STOP" americain')
                self.logs.append('    2. Essayer un autre modele .xml (opencv/data/haarcascades)')
                self.logs.append('    3. Entrainer un modele custom avec opencv_traincascade')

            t_total = time.time() - t_start
            self.logs.append('')
            self.logs.append('  Temps total du diagnostic: {:.1f}s'.format(t_total))
            self.logs.append('')
            self.logs.append('=' * 60)
            self.logs.append('   FIN DU DIAGNOSTIC')
            self.logs.append('=' * 60)

            source_url = url_for('static', filename='captured_images/{}'.format(filename))
            return {
                'Object_detected': best['bbox'] is not None,
                'detection_box': (bx_orig, by_orig, bw_orig, bh_orig) if best['bbox'] else None,
                'confidence': 1.0 if best['bbox'] else 0.0,
                'area': (bw_orig * bh_orig) if best['bbox'] else None,
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

    def _parse_cascade_xml(self, xml_path):
        """Parse un fichier cascade XML pour extraire la taille de la fenêtre d'entraînement.
        
        Le header du fichier XML contient une balise <size> avec la taille WxH
        utilisée lors de l'entraînement (ex: '25 45' pour une fenêtre 25x45).
        Cette info est cruciale pour choisir un minSize approprié.
        
        :param xml_path: Chemin vers le fichier .xml
        :return: tuple (width, height) ou None si non trouvé
        """
        if not xml_path or not os.path.exists(xml_path):
            return None
        try:
            # Lecture légère: on ne parse que les 50 premières lignes (le header)
            with open(xml_path, 'r') as f:
                lines = []
                for i, line in enumerate(f):
                    lines.append(line)
                    if i > 50:
                        break
                content = ''.join(lines)

            # Chercher <size> ou <width>/<height> dans le header
            # Format typique OpenCV: <size>25 45</size>  ou  <width>25</width><height>45</height>
            import re
            # Pattern 1: <size>W H</size>
            m = re.search(r'<size>\s*(\d+)\s+(\d+)\s*</size>', content)
            if m:
                return (int(m.group(1)), int(m.group(2)))

            # Pattern 2: <width>W</width> et <height>H</height> (dans le premier stageParams ou header)
            mw = re.search(r'<width>\s*(\d+)\s*</width>', content)
            mh = re.search(r'<height>\s*(\d+)\s*</height>', content)
            if mw and mh:
                return (int(mw.group(1)), int(mh.group(1)))

        except Exception:
            pass
        return None

    def _filter_image(self, frame, diagnostic_mode=False):
        """
        Applique un filtrage à l'image pour réduire le bruit et améliorer la détection.
        Si diagnostic_mode est True, sauvegarde les étapes de filtrage pour l'affichage web.
        """
        # Convertir en niveaux de gris
        gray_filtered = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if diagnostic_mode:
            self._save_step(gray_filtered, '2_gray_filtered', 'gray')

        return gray_filtered


    def _detect_objects(self, gray_filtered, frame_bgr, diagnostic_mode=False):
        """
        Parcourt tous les classifieurs chargés et accumule les détections.
        Ne dessine plus sur l'image — l'annotation est centralisée.

        :param gray_filtered: Image en niveaux de gris filtrée.
        :param frame_bgr:     Image BGR originale (PAS modifiée).
        :param diagnostic_mode: Si True, sauvegarde après chaque classifieur.
        :return: Liste de dicts [{'object': nom, 'detection_box': (x,y,w,h)}, ...]
        """
        detections = []

        for name, classifier in self.classifiers.items():
            self.logs.append('')
            self.logs.append('--- Classifieur: {} ---'.format(name))

            if classifier['classifier'].empty():
                self.logs.append('  ATTENTION: classifieur vide, ignore.')
                continue

            classifier_params = self.get_classifier_attributes(name)
            self.logs.append('  Parametres: nom={}, scaleFactor={}, minNeighbors={}, minSize={}'.format(
                name, classifier_params['scaleFactor'], classifier_params['minNeighbors'], '(5,5)'))

            results = classifier['classifier'].detectMultiScale(
                gray_filtered,
                scaleFactor=classifier_params['scaleFactor'],
                minNeighbors=classifier_params['minNeighbors'],
                minSize=(20, 20)
            )

            if len(results) == 0:
                self.logs.append('  Aucune detection.')
                continue

            self.logs.append('  {} detection(s) trouvee(s):'.format(len(results)))

            for i, (x, y, w, h) in enumerate(results):
                # Cast numpy -> Python int pour serialisation JSON
                x, y, w, h = int(x), int(y), int(w), int(h)
                self.logs.append('    #{}: pos=({},{}) taille={}x{} aire={}'.format(
                    i + 1, x, y, w, h, w * h))
                detections.append({
                    'object': name,
                    'detection_box': (x, y, w, h)
                })

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
