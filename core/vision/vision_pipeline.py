#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vision_pipeline.py
# ------------------
"""
ce module défini la logique de détection de la vision
------------------
Cette classe assure la gestion du pipeline de vision
- gérer la boucle de vision
- appeler la caméra
- appeler les algorithmes
- agréger les résultats
- fournir une API simple pour interagir avec le pipeline de vision
------------------
"""
import threading
import time
import cv2
import os
import uuid
import gc


class VisionPipeline:
    def __init__(self, camera, detectors=None, debug=False):
        self.camera = camera
        self.detectors = detectors if detectors is not None else []
        self.running = False
        self.last_captured_image_url = None
        self.CAPTURE_DIR = None
        self.debug = debug
        # Buffer de la dernière image et protection de concurrence
        self._lock = threading.Lock()
        self._last_frame = None
        # threads pour la détection passive
        self._passive_thread = None         # instance du thread
        self._passive_running = False       # Flag pour contrôler l'exécution du thread
        self._detection_rate = 5          # nombre de frames du livefeed entre chaque détection passive (ex: 5 → une détection toutes les 5 frames)
        self._passive_pause_event = threading.Event() # Event pour contrôler la pause du thread de détection passive
        self._passive_pause_event.clear()     # pause par défaut
        self._detection_trigger = threading.Event()  # signal "frame prête"

        # Buffer résultat détection passive (thread-safe)
        self._passive_detectors = []         # Liste des détecteurs à utiliser pour la détection passive (peut être différente de ceux du pipeline principal)
        self._last_detection_result = None
        self._result_lock = threading.Lock()

        # --- Hard Positive Mining ---
        self._mining_enabled = False          # Flag pour activer/désactiver le mining
        self._mining_dir = None               # Dossier temporaire pour stocker les crops (créé au besoin)
        self._mining_counts = {}              # {object_name: int} — compteur de crops par objet
        self._mining_lock = threading.Lock()  # Protection pour les compteurs

    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir
        # mise à jour pour chaque détecteur
        for detector in self.detectors:
            detector.attach_capture_dir(capture_dir)

    def start(self):
        """ appeler pour démarrer le pipeline de vision """
        if self.running:
            return
        try:
            self.camera.start_camera()
            self.running = True
        except Exception as e:
            if self.debug:
                print("Erreur lors du demarrage du pipeline de vision: {}".format(e))

    def step(self):
        """
        Exécute un cycle complet du pipeline de vision :
        1. Capture une image depuis la caméra
        2. Met à jour le buffer interne (last_frame)
        3. Passe l'image à chaque détecteur enregistré
        4. Retourne la liste agrégée des résultats

        Returns:
            list[dict]: Liste de résultats, un par détecteur.
                        Chaque dict contient au minimum la clé 'detector'.
                        En cas d'erreur de capture, retourne une liste vide.
        """
        if not self.running:
            return []

        # 1. Capture
        try:
            frame = self.camera.capture()
        except Exception as e:
            if self.debug:
                print("[VisionPipeline.step] Erreur capture: {}".format(e))
            return []

        if frame is None:
            return []

        # 2. Mise à jour du buffer (thread-safe)
        self.update_last_frame(frame)

        # 3. Exécution des détecteurs
        results = []
        for detector in self.detectors:
            try:
                detection = detector.process(frame.copy())
                if detection is not None:
                    results.append(detection)
            except Exception as e:
                if self.debug:
                    print("[VisionPipeline.step] Erreur détecteur {}: {}".format(detector, e))

        return results

    def stop(self):
        """ appeler pour arrêter le pipeline de vision """
        # Signaler l'arrêt AVANT de fermer la caméra
        # pour que le générateur vidéo s'arrête proprement
        self.running = False
        time.sleep(0.15)  # Laisser le générateur vidéo terminer son cycle
        try:
            self.camera.close()
            time.sleep(0.1)  # Laisser un peu de temps pour que la caméra se libère complètement
        except Exception as e:
            if self.debug:
                print("Erreur lors de l'arret du pipeline de vision: {}".format(e))
        
    def add_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self.detectors.append(detectors)
        self.detectors[-1].debug = self.debug  # Propager le mode debug au détecteur ajouté

    def add_passive_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self._passive_detectors.append(detectors)

    def set_passive_detectors(self, detectors):
        """Remplace la liste des détecteurs passifs (thread-safe).

        Utilisé pour changer dynamiquement les détecteurs selon le mode:
        - Onglet Contrôle: Line detector seulement
        - Onglet Vision: Haar classifiers seulement
        """
        was_paused = not self._passive_pause_event.is_set()
        if not was_paused and self._passive_running:
            self.pause_passive_detection()
        self._passive_detectors = list(detectors)
        if not was_paused and self._passive_running:
            self.resume_passive_detection()

    def process_frame(self, frame, detector_index=0, filename=None):
        """ traiter un frame spécifique avec un détecteur spécifique """

        if detector_index < 0 or detector_index >= len(self.detectors):
            raise IndexError("Index de détecteur invalide.")

        start_time = time.time() # pour mesurer le temps de traitement

        detector = self.detectors[detector_index]

        try:
            # Vérifier si le détecteur accepte le paramètre filename
            import inspect
            sig = inspect.signature(detector.process)
            if 'filename' in sig.parameters:
                # Nouveau détecteur: supporte filename
                detection = detector.process(frame, filename=filename)
            else:
                # Ancien détecteur: ne supporte que frame
                detection = detector.process(frame)

            elapsed_time = time.time() - start_time
            detection["Processing time"] = elapsed_time

            return detection

        except Exception as e:
            if self.debug:
                print("Erreur lors du traitement de l'image par le detecteur {}: {}".format(detector, e))
            
    def is_running(self):
        """ vérifier si le pipeline de vision est en cours d'exécution """
        return self.running

    def capture_frame(self):
        """ capturer une image brute de la caméra """
        if not self.running:
            raise RuntimeError("Le pipeline de vision n'est pas en cours d'exécution.")
        
        with self._lock:
            try:
                # Capture directe depuis la caméra (utilisé quand aucun flux ne tourne)
                return self.camera.capture()
            except Exception as e:
                if self.debug:
                    print("Erreur lors de la capture d'une image brute: {}".format(e)) 

    def update_last_frame(self, frame):
        """Met à jour le buffer de la dernière image capturée (thread-safe)."""
        if frame is None:
            return
        with self._lock:
            # stocker une copie pour éviter les mutations concurrentes
            try:
                self._last_frame = frame.copy()
            except Exception:
                # si frame n'est pas un numpy array, on stocke tel quel
                self._last_frame = frame

    def get_last_frame(self):
        """Retourne une copie de la dernière image si disponible, sinon None (thread-safe)."""
        with self._lock:
            if self._last_frame is None:
                return None
            try:
                return self._last_frame.copy()
            except Exception:
                return self._last_frame

    def change_camera_resolution(self, width, height):
        """
        Remplace l'instance caméra par une nouvelle à la résolution demandée.

        La caméra DOIT être arrêtée avant d'appeler cette méthode (le
        contrôleur s'en charge). On ferme l'ancienne instance de caméra puis
        on en crée une nouvelle avec les dimensions voulues.

        :param width:  Largeur en pixels (ex: 176, 320, 640).
        :param height: Hauteur en pixels (ex: 144, 240, 480).
        """
        # Fermer l'ancienne caméra proprement
        if self.camera is not None:
            try:
                self.camera.close()
            except Exception as e:
                if self.debug:
                    print("[VisionPipeline] Erreur fermeture caméra: {}".format(e))
        
        # Laisser du temps pour que la caméra se libère complètement
        # (surtout important sur Pi Zero avec peu de ressources GPU)
        time.sleep(0.3)
        
        # Garbage collection explicite pour forcer la libération des ressources
        gc.collect()
        time.sleep(0.1)

        # Créer une nouvelle instance de caméra à la résolution demandée
        # On utilise le même type de caméra que l'instance originale
        try:
            self.camera.reconfigure(width, height)
            if self.debug:
              print("[VisionPipeline] Résolution caméra changée: {}x{}".format(width, height))
        except Exception as e:
            if self.debug:
              print("[VisionPipeline] ERREUR reconfiguration caméra: {}".format(e))
            raise

# ----------------------------------------
#        Annotation centralisée
# ----------------------------------------
    @staticmethod
    def annotate_frame(frame, detections, box_color=(0, 255, 0), text_color=(0, 255, 0),
                       thickness=2, font_scale=0.5, previous_distance=None, approximate_distance=True, debug=False):
        """
        Dessine les bounding boxes et labels sur une **copie** de l'image.

        :param frame:      Image BGR originale (ne sera PAS modifiée).
        :param detections:  Liste de dicts [{object, detection_box, ...}, ...].
        :param box_color:   Couleur BGR du rectangle (défaut vert).
        :param text_color:  Couleur BGR du texte (défaut vert).
        :param thickness:   Épaisseur du trait.
        :param font_scale:  Échelle de la police.
        :param previous_distance: Distance calculée précédemment (optionnel, pour affichage stable).
        :param approximate_distance: Si True, calcule et affiche une estimation de la distance de l'objet. pour libérer l'overhead du CPU
        :return: Copie de l'image annotée (BGR).
        """
        annotated = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX
        frame_h, frame_w = frame.shape[:2]

        for det in detections:
            bbox = det.get('detection_box')
            if not bbox or len(bbox) != 4:
                continue
            x, y, w, h = [int(v) for v in bbox]
            label = det.get('object', 'Objet')
            # detection box de l'objet
            cv2.rectangle(annotated, (x, y), (x + w, y + h), box_color, thickness)
            label_y = max(y - 6, 14)
            # nom de l'objet
            cv2.putText(annotated, label, (x, label_y), font, font_scale,
                        text_color, 1, cv2.LINE_AA)
            # distance approximative
            # Attention: l'implémentation ne devrais pas être faite ici si on souhaite utiliser la distance calculé dans le contrôle du robot.
            # on l'a fait ici pour tester vite fais, mais cette fonction ne sert qu'â annoter l'image, pas à faire des calculs de détection ou de contrôle.
            if approximate_distance is True:
                distance_cm = VisionPipeline.approximate_object_distance(det.get('detection_box'), frame_h, label, debug=debug)
            else :
                distance_cm = previous_distance

            cv2.putText(annotated, "{:.1f} cm".format(distance_cm) if distance_cm else "N/A", (x, y + h + 15), font, font_scale,
                        text_color, 1, cv2.LINE_AA)
        return annotated, distance_cm
    
    @staticmethod
    def annotate_detection_result(frame, detector, detection_result, approximate_distance=True, previous_distance=None, debug=False):
        """
        Annote une frame avec les résultats de détection d'n'importe quel détecteur.
        Gère les cas spéciaux (comme LineDetector) et les détecteurs standard.
        
        Args:
            frame: Image BGR originale (copie sera faite si nécessaire)
            detector: Objet détecteur (pour accéder à ses méthodes d'annotation)
            detection_result: dict retourné par detector.process()
            approximate_distance: Si True, calcule distance pour objets bbox
            previous_distance: Distance calculée précédemment (optionnel) pour affichage stable
            debug: Mode debug
            
        Returns:
            annotated: Image annotée
            distance_cm: Distance estimée (si applicatible)
        """
        if detection_result is None:
            return frame.copy(), None
        
        # Cas spécial: LineDetector (possède line_offset et annotate_detection)
        if 'line_offset' in detection_result and hasattr(detector, 'annotate_detection'):
            annotated = frame.copy()
            annotated = detector.annotate_detection(annotated)
            return annotated, None
        
        # Cas standard: autres détecteurs avec 'detections'
        detections = detection_result.get('detections', [])
        if detections:
            annotated, distance_cm = VisionPipeline.annotate_frame(
                frame, 
                detections,
                approximate_distance=approximate_distance,
                previous_distance=previous_distance,
                debug=debug
            )
            return annotated, distance_cm
        
        # Aucune détection
        return frame.copy(), None
    
    @staticmethod
    def approximate_object_distance(detection_box, frame_h, label, debug=False):
        """
        calculer une estimation de la distance d'un objet à partir de sa taille apparente dans l'image
        en utilisant une formule de type : D = (H * f) / h
        où H = hauteur réelle de l'objet, f = focale en pixels, h = hauteur apparente de l'objet en pixels (normalisée pour différentes résolutions)
        retourne la distance estimée en cm ou None si le calcul est impossible
        """
        facteur_M = {
        '160x128': 3.679,
        '176x144': 3.278,
        '320x240': 1.998,
        '640x480': 1.0
        }

        hauteur_reelle_cm = {
            'pieton': 4.5,
            'camion_pompier': 7.0,
            'stop_sign':   4.5,
            'stop_sign Moi':   4.5,
            'stop_sign Git':   4.5
        }

        # La distance focale en pixels à été calculée à partir d'images capturées à
        # 4 points de référence (15, 20, 30, 45 cm). Les résultats ont été régressés
        # pour obtenir une estimation de la focale en pixels pour chaque objet.
        # Ces valeurs sont donc spécifique à nos objets et doivent calculer pour tout
        # nouvel objet ajouté.

        f_pixels_par_objet = {
            'pieton':          573.6111,  # résultat des moyennes
            'camion_pompier':  627.6786,
            'stop_sign':       632.2222,
        }

        object_name = label.lower()
        object_height_pixels = detection_box[3]  # hauteur de la bbox en pixels

        # normalisation de la hauteur en pixels pour 480p
        if frame_h == 128:
            normalized_height = object_height_pixels * facteur_M['160x128']
        elif frame_h == 144:
            normalized_height = object_height_pixels * facteur_M['176x144']
        elif frame_h == 240:
            normalized_height = object_height_pixels * facteur_M['320x240']
        elif frame_h == 480:
            normalized_height = object_height_pixels * facteur_M['640x480']
        elif frame_h == 972:
            normalized_height = object_height_pixels * (facteur_M['640x480'] / 2.025)  # comme la référence est à 480p, on divise le facteur lorsqu'on dépasse cette résolution
        else:
            if debug:
                print("Résolution non reconnue pour la normalisation: hauteur image (approximate_object_distance) = {}".format(frame_h))
            normalized_height = object_height_pixels  # pas de normalisation
        
        if object_name in hauteur_reelle_cm:
            hauteur_réelle_obj_cm = hauteur_reelle_cm[object_name]
        else:
            if debug:
                print("Objet inconnu pour la distance: {}, utiliser une hauteur par défaut de 5 cm".format(object_name))
            hauteur_réelle_obj_cm = 5.0


        # Facteur correctif empirique : ratio entre la taille bbox observée et la taille réelle de l'objet dans l'image
        # < 1.0 : le détecteur sous-estime la taille (camion) → on amplifie h_pixel
        # > 1.0 : le détecteur sur-estime la taille (stop)   → on réduit h_pixel
        bbox_correction = {
            'pieton':         1.0,   # modèle propre, pas de correction nécessaire
            'camion_pompier': 0.88,  # détecte à l'intérieur → bbox trop petite
            'stop_sign':      1.15,  # crop trop large → bbox trop grande
        }

        # Dans le calcul :
        corrected_height = normalized_height * bbox_correction.get(object_name, 1.0)

        # formule de distance : D = (H * f) / h
        # où H = hauteur réelle de l'objet, f = focale en pixels, h = hauteur apparente de l'objet en pixels (normalisée)
        if corrected_height > 0:
            if object_name in f_pixels_par_objet:
                f_pixels = f_pixels_par_objet[object_name]
            else:
                if debug:
                    print("Objet inconnu pour la focale: {}, utiliser une focale par défaut de 600 pixels".format(object_name))
                f_pixels = 610.0 # valeur par défaut basée sur les moyennes des autres objets

            distance_cm = (hauteur_réelle_obj_cm * f_pixels) / corrected_height
            return distance_cm
        else:
            if debug:
                print("Hauteur de l'objet en pixels est nulle, impossible de calculer la distance.")
            return None

    def save_annotated_image(self, frame, detections, filename):
        """
        Annote une image puis la sauvegarde sur disque.

        :param frame:       Image BGR source.
        :param detections:  Liste de dicts [{object, detection_box}, ...].
        :param filename:    Nom de fichier de la capture originale.
        :return: (ann_filename, ann_url) ou (None, None) si rien à sauvegarder.
        """
        if not detections or not self.CAPTURE_DIR:
            return None, None

        annotated, _ = self.annotate_frame(frame, detections, debug=self.debug)

        base, ext = os.path.splitext(filename)
        ann_name = '{}_det_{}{}'.format(base, uuid.uuid4().hex[:6], ext or '.jpg')
        ann_path = os.path.join(self.CAPTURE_DIR, ann_name)
        cv2.imwrite(ann_path, annotated)

        # URL relative générée sans importer Flask ici
        ann_url = 'captured_images/{}'.format(ann_name)
        return ann_name, ann_url

    def get_detectors(self):
        """ obtenir la liste des détecteurs ajoutés au pipeline de vision """
        return self.detectors
    
    def get_passive_detectors(self):
        """ obtenir la liste des détecteurs passif ajoutés au pipeline de vision """
        return self._passive_detectors
    
    def get_camera(self):
        """ obtenir la caméra utilisée dans le pipeline de vision """
        return self.camera
    
    def get_current_detector_diagnostic(self, detector_index=0, filename=None):
        """ obtenir le diagnostic du détecteur courant """
        if not self.detectors:
            return {'error': 'Aucun détecteur disponible, ils sont attacher au VP dans le main'}

        if detector_index < 0 or detector_index >= len(self.detectors):
            return {'error': 'Index de détecteur invalide'}

        if filename is None:
            return {'error': "Aucun fichier d'image fourni pour le diagnostic"}

        detector = self.detectors[detector_index]
        try:
            diagnostic = detector.diagnostique_detecteur(filename)
            return diagnostic
        except Exception as e:
            if self.debug:
                print("Erreur lors de l'obtention du diagnostic du détecteur {}: {}".format(detector, e))
            import traceback
            if self.debug:
                traceback.print_exc()
            return {'error': "Erreur lors de l'obtention du diagnostic du détecteur", 'details': str(e)}

# ----------------------------------------
#        thread de détection passive
# ----------------------------------------
    def _passive_detection_loop(self):
        """
        Boucle de détection passive. Tourne dans un thread daemon.
        S'endort entre chaque détection pour ne pas saturer le CPU.
        Si le mining est activé, les crops des détections sont sauvegardés.
        """

        detector_index = 0
        nb_detectors = len(self._passive_detectors)

        while self._passive_running:
            # attend si le mode pause est activé
            self._passive_pause_event.wait()
    
            # Attendre le signal de la boucle video_feed
            triggered = self._detection_trigger.wait(timeout=1.0)
            if not triggered:
                continue  # timeout — vérifier _passive_running et recommencer
            self._detection_trigger.clear()  # consommer le signal

            # récupération de la dernière frame du livefeed
            frame = self.get_last_frame()
            if frame is None or nb_detectors == 0:
                continue

            # faire la détection avec le détecteur courant
            detector = self._passive_detectors[detector_index]
            try:
                detection_result = detector.process_passive(frame)
                with self._result_lock:
                    self._last_detection_result = detection_result
                    self._last_detection_result['Detector'] = str(detector)  
                    self._last_detection_result['Timestamp'] = time.time()

                # --- Hard Positive Mining: sauvegarder les crops ---
                if self._mining_enabled and detection_result.get('Object_detected'):
                    self._harvest_crops(frame, detection_result.get('detections', []))

            except Exception as e:
                if self.debug:
                    print("Erreur lors de la détection passive avec le détecteur {}: {}".format(detector, e))

            # passer au détecteur suivant pour la prochaine itération
            detector_index = (detector_index + 1) % nb_detectors

    def start_passive_detection(self):
        """Démarre le thread de détection passive avec l'intervalle spécifié."""
        if self._passive_thread and self._passive_thread.is_alive():
            return  # déjà actif
        self._passive_running = True
        self._passive_pause_event.set()
        self._passive_thread = threading.Thread(
            target=self._passive_detection_loop,
            name="PassiveDetection",
            daemon=True  # s'arrête automatiquement quand le programme principal se termine
        )
        self._passive_thread.start()
        if self.debug:
            print("[PassiveVision] Démarré avec {} détecteurs passifs".format(len(self._passive_detectors)))

    def stop_passive_detection(self):
        """Arrête le thread de détection passive."""
        self._passive_running = False
        self._passive_pause_event.set()  # s'assurer que le thread n'est pas bloqué en pause
        if self._passive_thread:
            self._passive_thread.join(timeout=2.0)  # attendre que le thread se termine proprement
        
        if self.debug:
            print("[PassiveVision] Arrêté")
    
    def pause_passive_detection(self):
        """Met en pause le thread de détection passive."""
        self._passive_pause_event.clear()
        if self.debug:
            print("[PassiveVision] En pause")
    
    def resume_passive_detection(self):
        """Reprend le thread de détection passive s'il était en pause."""
        self._passive_pause_event.set()
        if self.debug:
            print("[PassiveVision] Repris")

    def get_last_detection_result(self):
        """Retourne le dernier résultat de détection passive (thread-safe)."""
        with self._result_lock:
            return self._last_detection_result

    def set_passive_detection_FPS(self, detection_rate):
        """
        Définit la fréquence de détection passive en nombre de frames du livefeed.
        Ex: detection_rate=5 → une détection toutes les 5 frames produites.
        """
        self._detection_rate = max(1, int(detection_rate))


# ----------------------------------------
#        Hard Positive Mining
# ----------------------------------------
    def _ensure_mining_dir(self):
        """Crée le dossier temporaire de mining si nécessaire."""
        if self._mining_dir is None:
            base = self.CAPTURE_DIR or '/tmp'
            self._mining_dir = os.path.join(base, 'mining_crops')
        os.makedirs(self._mining_dir, exist_ok=True)

    def _harvest_crops(self, frame, detections):
        """
        Extrait les crops des détections et les sauvegarde sur disque.
        Appelé depuis le thread de détection passive — doit être rapide.

        :param frame:      Image BGR brute.
        :param detections: Liste de dicts [{object, detection_box}, ...].
        """
        self._ensure_mining_dir()
        h_img, w_img = frame.shape[:2]

        for det in detections:
            bbox = det.get('detection_box')
            obj_name = det.get('object', 'unknown')
            if not bbox or len(bbox) != 4:
                continue

            x, y, w, h = [int(v) for v in bbox]
            # Clamp aux limites de l'image
            x1 = max(0, x)
            y1 = max(0, y)
            x2 = min(w_img, x + w)
            y2 = min(h_img, y + h)
            if x2 <= x1 or y2 <= y1:
                continue

            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue

            # Nom de fichier : <objet>_<timestamp>_<uuid>.jpg
            safe_name = obj_name.replace(' ', '_').replace('/', '_')
            ts = time.strftime('%Y%m%d_%H%M%S')
            fname = '{}_{}_{}x{}_{}.jpg'.format(safe_name, ts, w, h, uuid.uuid4().hex[:6])
            fpath = os.path.join(self._mining_dir, fname)

            try:
                cv2.imwrite(fpath, crop)
                with self._mining_lock:
                    self._mining_counts[obj_name] = self._mining_counts.get(obj_name, 0) + 1
            except Exception as e:
                if self.debug:
                    print("[Mining] Erreur sauvegarde crop: {}".format(e))

    def enable_mining(self):
        """Active le mode hard positive mining."""
        self._ensure_mining_dir()
        self._mining_enabled = True
        if self.debug:
            print("[Mining] Activé — dossier: {}".format(self._mining_dir))

    def disable_mining(self):
        """Désactive le mode hard positive mining."""
        self._mining_enabled = False
        if self.debug:
            print("[Mining] Désactivé")

    def get_mining_stats(self):
        """Retourne les statistiques de mining (thread-safe)."""
        with self._mining_lock:
            total = sum(self._mining_counts.values())
            return {
                'enabled': self._mining_enabled,
                'total': total,
                'per_object': dict(self._mining_counts),
                'mining_dir': self._mining_dir,
            }

    def collect_mining_crops(self):
        """
        Liste tous les fichiers crop dans le dossier mining.

        :return: Liste de chemins absolus.
        """
        if not self._mining_dir or not os.path.isdir(self._mining_dir):
            return []
        files = []
        for f in sorted(os.listdir(self._mining_dir)):
            fp = os.path.join(self._mining_dir, f)
            if os.path.isfile(fp):
                files.append(fp)
        return files

    def clear_mining_crops(self):
        """Supprime tous les crops et remet les compteurs à zéro."""
        files = self.collect_mining_crops()
        for fp in files:
            try:
                os.remove(fp)
            except Exception:
                pass
        with self._mining_lock:
            self._mining_counts.clear()
        if self.debug:
            print("[Mining] {} crops supprimés".format(len(files)))