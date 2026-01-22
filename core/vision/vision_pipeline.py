# vision_pipeline.py
# ------------------
# ce module défini la logique de détection de la vision
# ------------------
# Cette classe assure la gestion du pipeline de vision
# - gérer la boucle de vision
# - appeler la caméra
# - appeler les algorithmes
# - agréger les résultats
# - fournir une API simple pour interagir avec le pipeline de vision
# ------------------

import time


class VisionPipeline:
    def __init__(self, camera, detectors=None, fps=30):
        self.camera = camera
        self.detectors = detectors if detectors is not None else []
        self.periode = 1.0 / fps
        self.running = False

    def start(self):
        """ appeler pour démarrer le pipeline de vision """
        try:
            self.camera.start_camera()
            self.running = True
        except Exception as e:
            print(f"Erreur lors du démarrage du pipeline de vision: {e}")
            raise e
        
    def stop(self):
        """ appeler pour arrêter le pipeline de vision """
        try:
            self.camera.close()
            self.running = False
        except Exception as e:
            print(f"Erreur lors de l'arrêt du pipeline de vision: {e}")
            raise e
        
    def add_detectors(self, detectors):
        """ ajouter un détecteur au pipeline de vision """
        self.detectors.append(detectors)

    def step(self):
        """ effectuer un cycle du pipeline de vision """
        if not self.running:
            raise RuntimeError("Le pipeline de vision n'est pas en cours d'exécution.")
        
        start_time = time.time()
        
        try:
            frame = self.camera.capture()
        except Exception as e:
            print(f"Erreur lors de la capture d'une image: {e}")
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
                print(f"Erreur lors du traitement de l'image par le détecteur {detectors}: {e}")
                raise e
        
        # On fait un délais pour respecter le fps souhaité
        elapsed_time = time.time() - start_time
        sleep_time = self.periode - elapsed_time
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        return results

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
        
        try:
            frame = self.camera.capture()
            return frame
        except Exception as e:
            print(f"Erreur lors de la capture d'une image brute: {e}")
            raise e

    def get_detectors(self):
        """ obtenir la liste des détecteurs ajoutés au pipeline de vision """
        return self.detectors
    
    def get_camera(self):
        """ obtenir la caméra utilisée dans le pipeline de vision """
        return self.camera
    
    def run_camera(self):
        """ fonction pour exécuter la boucle de capture de la caméra dans un thread séparé """
        if not self.running:
            raise RuntimeError("Le pipeline de vision n'est pas en cours d'exécution.")
        
        while self.running:
            try:
                time.sleep(0.05)  # Petite pause pour éviter une boucle trop rapide
            except Exception as e:
                print(f"Erreur dans la boucle de la caméra: {e}")
                raise e
        