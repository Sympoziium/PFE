# main.py
# ------------------
# Point d'entrée principal pour exécuter le programme du robot

# Import pour le module de vision
from core.camera.picam2 import PiCam2
from core.vision.vision_pipeline import VisionPipeline
from core.vision.detecteurs.Luminosité import LuminosityDetector

camera = PiCam2()
detector = LuminosityDetector()

vision_pipeline = VisionPipeline(camera=camera)

# On ajoute le détecteur au pipeline de vision
vision_pipeline.add_detectors(detector)
vision_pipeline.start()

if __name__ == "__main__":

    results = vision_pipeline.step()
    print("Résultats de la détection de luminosité :", results)
