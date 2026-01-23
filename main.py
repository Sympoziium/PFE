#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py
# ------------------
# Point d'entree principal pour exécuter le programme du robot
# Import pour le module de vision
from core.camera.picam2 import PiCam2
from core.vision.vision_pipeline import VisionPipeline
from core.vision.detectors.Luminosité import LuminosityDetector

# Import pour le serveur web (Flask)
from interface.flask_server import app, attach_pipeline

import threading

camera = PiCam2()
detector = LuminosityDetector()
vision_pipeline = VisionPipeline(camera=camera)

# On ajoute le détecteur au pipeline de vision
vision_pipeline.add_detectors(detector)
# vision_pipeline.start()


attach_pipeline(vision_pipeline)

# Démarrer le serveur Flask dans un thread séparé
server_thread = threading.Thread(
    target=app.run,
    kwargs={'host': '0.0.0.0', 'port': 5000, 'threaded': True, 'use_reloader': False, 'debug': False}
)
server_thread.daemon = True
server_thread.start()
print("Flask server démarré")



testing = True
while testing:
    server_thread.join()  # Le serveur Flask gère les requêtes en arrière-plan


    # results = vision_pipeline.step()
    # print("Résultats de la détection de luminosité :", results)
    # cmd = input("Appuyez sur Espace pour arrêter...")  # Pause pour chaque étape
    # if cmd == " ":
    #     testing = False