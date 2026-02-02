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



class VisionPipeline:
    def __init__(self, camera, detectors=None, fps=30):
        self.camera = camera
        self.detectors = detectors if detectors is not None else []
        self.periode = 1.0 / fps
        self.running = False
        self.last_captured_image_url = None
        # Buffer de la dernière image et protection de concurrence
        self._lock = threading.Lock()
        self._last_frame = None

    def start(self):
        """ appeler pour démarrer le pipeline de vision """
        try:
            self.camera.start_camera()
            self.running = True
        except Exception as e:
            print("Erreur lors du demarrage du pipeline de vision: {}".format(e))
            raise e
        
    def stop(self):
        """ appeler pour arrêter le pipeline de vision """
        try:
            self.camera.close()
            self.running = False
        except Exception as e:
            print("Erreur lors de l'arret du pipeline de vision: {}".format(e))
            raise e
        
    def add_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self.detectors.append(detectors)

    def step(self):
        ## fonction désuette ?
        """ effectuer un cycle du pipeline de vision """
        if not self.running:
            raise RuntimeError("Le pipeline de vision n'est pas en cours d'exécution.")
        
        # with self.lock: # assurer la synchronisation des accès à la caméra
        start_time = time.time()
        
        try:
            frame = self.camera.capture()
        except Exception as e:
            print("Erreur lors de la capture d'une image: {}".format(e))
            raise e
        
        results = []

        # Appliquer chaque détecteur sur l'image capturée
        for detectors in self.detectors:
            try:
                result = detectors.process(frame)
                results.append(result) # ici on retourne le résultat sous forme brute
                                        # il faudra surement modifier pour log les données
                                        # et seulement retourner la décision finale

            except Exception as e:
                print("Erreur lors du traitement de l'image par le detecteur {}: {}".format(detectors, e))
                raise e
        
        # On fait un délais pour respecter le fps souhaité
        elapsed_time = time.time() - start_time
        sleep_time = self.periode - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        return results
    
    def process_frame(self, frame, detetor_index=0):
        """ traiter un frame spécifique avec un détecteur spécifique """

        # camera_was_running = False
        # if self.running:
        #     # arret temporaire de la caméra pour éviter les conflits
        #     camera_was_running = True
        #     self.stop()
        
        if detetor_index < 0 or detetor_index >= len(self.detectors):
            raise IndexError("Index de détecteur invalide.")
        
        start_time = time.time() # pour mesurer le temps de traitement

        detector = self.detectors[detetor_index]
        
        try:
            detection = detector.process(frame)
            elapsed_time = time.time() - start_time
            detection["Processing time"] = elapsed_time

            # if camera_was_running:
            #     self.start() # redémarrer la caméra si elle était en cours d'exécution

            return detection
        
        except Exception as e:
            print("Erreur lors du traitement de l'image par le detecteur {}: {}".format(detector, e))
            # if camera_was_running:
            #     self.start()
            raise e

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
                raise e

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

    def get_detectors(self):
        """ obtenir la liste des détecteurs ajoutés au pipeline de vision """
        return self.detectors
    
    def get_camera(self):
        """ obtenir la caméra utilisée dans le pipeline de vision """
        return self.camera
    
