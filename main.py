#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py
# ------------------
# Point d'entree principal pour exécuter le programme du robot
# pour se connecter au serveur flask après qu'il soit partit
# entrer l'ip du zumi sur le réseau local dans le web browser
# ex: http://192.168.68.73:5000/


# IMPORT ZUMI LIBRARY
import sys
sys.path.append("/usr/local/lib/python3.5/dist-packages")  # chemin du package zumi
from zumi.util.camera import Camera
from zumi.zumi import Zumi


from core.vision.vision_pipeline import VisionPipeline
from core.vision.detectors.Luminosity import LuminosityDetector

# Import pour le serveur web (Flask)
from interface.flask_server import app
from interface import controller as controller_module
import threading

# try:
#     camera = PiCam2()
# except Exception as e:
#     print("Erreur lors de l'initialisation de la caméra PiCam2: {}".format(e))
#     print("Utilisation de la caméra par défaut.")
#     camera = Camera()  # Utiliser cette ligne pour tester sur le vrai robot Zumi

# Le zumi n'a pas la librairie picamera2 d'installée par défaut, on utilise la caméra par défaut
camera = Camera() 
zumi = Zumi()
detector = LuminosityDetector()
vision_pipeline = VisionPipeline(camera=camera)
# Contrôleur backend
ctrl = controller_module.controller(app, zumi)


# On ajoute le détecteur au pipeline de vision
vision_pipeline.add_detectors(detector)
# vision_pipeline.start()
ctrl.attach_pipeline_vision(vision_pipeline)    


# Démarrer le serveur Flask dans un thread séparé
# server_thread = threading.Thread(
#     target=app.run,
#     kwargs={'host': '0.0.0.0', 'port': 5000, 'threaded': True, 'use_reloader': False, 'debug': False}
# )
# server_thread.daemon = True
# server_thread.start()

if __name__ == '__main__':
    watchdog_thread = threading.Thread(target=motor_watchdog)
    watchdog_thread.daemon = True # S'assure qu'il s'arrête avec le script
    watchdog_thread.start()

    print("Programme is running") # Vous pouvez garder votre print
    app.run(host='0.0.0.0', port=5000, threaded=True)

    print("Flask server démarré")
    # Lorsque le serveur Flask s'arrête, on arrête aussi le programme principal
    exit(0)