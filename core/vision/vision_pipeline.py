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


class VisionPipeline:
    def __init__(self, camera, detectors=None, fps=30):
        self.camera = camera
        self.detectors = detectors if detectors is not None else []
        self.periode = 1.0 / fps
        self.running = False
        self.last_captured_image_url = None
        self.CAPTURE_DIR = None
        # Buffer de la dernière image et protection de concurrence
        self._lock = threading.Lock()
        self._last_frame = None
        # Fonction optionnelle de capture haute résolution (injectée depuis l'extérieur)
        self._hires_capture_fn = None
        # threads pour la détection passive
        self._passive_thread = None         # instance du thread
        self._passive_running = False       # Flag pour contrôler l'exécution du thread
        self._passive_interval = 4.0        # Intervalle de 4 secondes entre chaque détection passive
        self._passive_pause_event = threading.Event() # Event pour contrôler la pause du thread de détection passive
        self._passive_pause_event.clear()     # pause par défaut

        # Buffer résultat détection passive (thread-safe)
        self._passive_detectors = []         # Liste des détecteurs à utiliser pour la détection passive (peut être différente de ceux du pipeline principal)
        self._last_detection_result = None
        self._result_lock = threading.Lock()


    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir
        # mise à jour pour chaque détecteur
        for detector in self.detectors:
            detector.attach_capture_dir(capture_dir)

    def start(self):
        """ appeler pour démarrer le pipeline de vision """
        try:
            self.camera.start_camera()
            self.running = True
        except Exception as e:
            print("Erreur lors du demarrage du pipeline de vision: {}".format(e))
            
        
    def stop(self):
        """ appeler pour arrêter le pipeline de vision """
        # Signaler l'arrêt AVANT de fermer la caméra
        # pour que le générateur vidéo s'arrête proprement
        self.running = False
        import time
        time.sleep(0.15)  # Laisser le générateur vidéo terminer son cycle
        try:
            self.camera.close()
        except Exception as e:
            print("Erreur lors de l'arret du pipeline de vision: {}".format(e))
        
    def add_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self.detectors.append(detectors)

    def add_passive_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self._passive_detectors.append(detectors)

    def process_frame(self, frame, detetor_index=0, filename=None):
        """ traiter un frame spécifique avec un détecteur spécifique """

        if detetor_index < 0 or detetor_index >= len(self.detectors):
            raise IndexError("Index de détecteur invalide.")

        start_time = time.time() # pour mesurer le temps de traitement

        detector = self.detectors[detetor_index]

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
            print("Erreur lors du traitement de l'image par le detecteur {}: {}".format(detector, e))
            
    def is_running(self):
        """ vérifier si le pipeline de vision est en cours d'exécution """
        return self.running
    
    def get_periode(self):
        """ obtenir la période entre chaque cycle de vision en secondes """
        return self.periode

    def capture_frame(self):
        """ capturer une image brute de la caméra """
        if not self.running:
            raise RuntimeError("Le pipeline de vision n'est pas en cours d'exécution.")
        
        with self._lock:
            try:
                # Capture directe depuis la caméra (utilisé quand aucun flux ne tourne)
                return self.camera.capture()
            except Exception as e:
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

    def set_hires_capture_fn(self, fn):
        """
        Injecte une fonction de capture haute résolution.
        
        La fonction doit avoir la signature : fn(width, height) -> np.ndarray (BGR)
        Elle sera appelée par capture_hires_frame() pour obtenir une image à
        résolution supérieure sans que le pipeline ait besoin de connaître les
        détails de la caméra sous-jacente (modularité).
        
        :param fn: callable(width: int, height: int) -> np.ndarray
        """
        self._hires_capture_fn = fn

    def capture_hires_frame(self, width=640, height=480):
        """
        Capture une image haute résolution via la fonction injectée.
        
        Si aucune fonction hires n'a été injectée, retombe sur la capture
        normale (get_last_frame ou capture_frame).
        
        Note : pendant la capture hires, le flux vidéo normal est brièvement
        interrompu (la caméra est fermée et rouverte). C'est normal.
        
        :param width: Largeur souhaitée pour la capture hires
        :param height: Hauteur souhaitée pour la capture hires
        :return: np.ndarray BGR ou None
        """
        if self._hires_capture_fn is not None:
            try:
                frame = self._hires_capture_fn(width, height)
                if frame is not None:
                    return frame
                print("[VisionPipeline] Hires capture returned None, falling back to normal")
            except Exception as e:
                print("[VisionPipeline] Hires capture failed: {}, falling back".format(e))
        
        # Fallback : capture normale
        frame = self.get_last_frame()
        if frame is not None:
            return frame
        if self.running:
            return self.capture_frame()
        return None

    def has_hires_capture(self):
        """Vérifie si la capture haute résolution est disponible."""
        return self._hires_capture_fn is not None

# ----------------------------------------
#        Annotation centralisée
# ----------------------------------------
    @staticmethod
    def annotate_frame(frame, detections, box_color=(0, 255, 0), text_color=(0, 255, 0),
                       thickness=2, font_scale=0.5):
        """
        Dessine les bounding boxes et labels sur une **copie** de l'image.

        :param frame:      Image BGR originale (ne sera PAS modifiée).
        :param detections:  Liste de dicts [{object, detection_box, ...}, ...].
        :param box_color:   Couleur BGR du rectangle (défaut vert).
        :param text_color:  Couleur BGR du texte (défaut vert).
        :param thickness:   Épaisseur du trait.
        :param font_scale:  Échelle de la police.
        :return: Copie de l'image annotée (BGR).
        """
        annotated = frame.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        for det in detections:
            bbox = det.get('detection_box')
            if not bbox or len(bbox) != 4:
                continue
            x, y, w, h = [int(v) for v in bbox]
            label = det.get('object', 'Objet')
            cv2.rectangle(annotated, (x, y), (x + w, y + h), box_color, thickness)
            label_y = max(y - 6, 14)
            cv2.putText(annotated, label, (x, label_y), font, font_scale,
                        text_color, 1, cv2.LINE_AA)
        return annotated

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

        annotated = self.annotate_frame(frame, detections)

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
            print("Erreur lors de l'obtention du diagnostic du détecteur {}: {}".format(detector, e))
            import traceback
            traceback.print_exc()
            return {'error': "Erreur lors de l'obtention du diagnostic du détecteur", 'details': str(e)}

# ----------------------------------------
#        thread de détection passive
# ----------------------------------------
    def _passive_detection_loop(self):
        """
        Boucle de détection passive. Tourne dans un thread daemon.
        S'endort entre chaque détection pour ne pas saturer le CPU.
        """
        # fait la liste des détecteurs assigné à la détection passive
        nb_detectors = len(self._passive_detectors)
        detector_index = 0
        while self._passive_running:
            # attend si le mode pause est activé
            self._passive_pause_event.wait()

            # récupération de la dernière frame du livefeed
            frame = self.get_last_frame()
            if frame is not None and nb_detectors > 0:
                # faire la détection avec le détecteur courant
                detector = self._passive_detectors[detector_index]
                try:
                    detection_result = detector.process_passive(frame)
                    with self._result_lock:
                        self._last_detection_result = detection_result
                except Exception as e:
                    print("Erreur lors de la détection passive avec le détecteur {}: {}".format(detector, e))

                # passer au détecteur suivant pour la prochaine itération
                detector_index = (detector_index + 1) % nb_detectors
        
            # Interval de détection passive
            time.sleep(self._passive_interval)

    def start_passive_detection(self, interval=4.0, detctor_index=0):
        """Démarre le thread de détection passive avec l'intervalle spécifié."""
        if self._passive_thread and self._passive_thread.is_alive():
            return  # déjà actif
        self._passive_interval = interval
        self._passive_running = True
        self._passive_pause_event.set()
        self._passive_thread = threading.Thread(
            target=self._passive_detection_loop,
            name="PassiveDetection",
            daemon=True  # s'arrête automatiquement quand le programme principal se termine
        )
        self._passive_thread.start()
        print("[PassiveVision] Démarré (intervalle: {}s)".format(interval))

    def stop_passive_detection(self):
        """Arrête le thread de détection passive."""
        self._passive_running = False
        self._passive_pause_event.set()  # s'assurer que le thread n'est pas bloqué en pause
        if self._passive_thread:
            self._passive_thread.join(timeout=2.0)  # attendre que le thread se termine proprement
        
        print("[PassiveVision] Arrêté")
    
    def pause_passive_detection(self):
        """Met en pause le thread de détection passive."""
        self._passive_pause_event.clear()
        print("[PassiveVision] En pause")
    
    def resume_passive_detection(self):
        """Reprend le thread de détection passive s'il était en pause."""
        self._passive_pause_event.set()
        print("[PassiveVision] Repris")

    def get_last_detection_result(self):
        """Retourne le dernier résultat de détection passive (thread-safe)."""
        with self._result_lock:
            return self._last_detection_result