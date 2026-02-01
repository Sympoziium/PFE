#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py
# ------------------
# Point d'entree principal pour exécuter le programme du robot
# pour se connecter au serveur flask après qu'il soit partit
# entrer l'ip du zumi sur le réseau local dans le web browser
# ex: http://192.168.68.73:5000/

# ----------------------------------------------------------------------------
#                               Imports
# ----------------------------------------------------------------------------

# Import de l'implémentation du robot Zumi
from core.robot.robot_zumi import RobotZumi

# Import du pipeline de vision et des détecteurs
from core.vision.vision_pipeline import VisionPipeline
from core.vision.detectors.Luminosity import LuminosityDetector
from core.vision.detectors.Line_detector import LineDetector

# Import pour le serveur web (Flask)
from interface import server_controller as controller_module
from interface import flask_router as routes

# Import utilitaire
import threading
import time 

# ----------------------------------------------------------------------------
#                           Initialisation
# ----------------------------------------------------------------------------

# Initialisation du robot Zumi
zumi = RobotZumi()

# Initialisation du pipeline de vision
detector = LuminosityDetector()
vision_pipeline = VisionPipeline(camera=zumi.camera)
line_detector = LineDetector()

# On ajoute le détecteur au pipeline de vision
vision_pipeline.add_detectors(detector)
vision_pipeline.add_detectors(line_detector)
# Initialisation du contrôleur (serveur Flask)
ctrl = controller_module.controller(zumi)
routes.register_routes(ctrl) # on enregistre les routes sur l'instance Flask du contrôleur (build du serveur)
# On attache le pipeline de vision au contrôleur
ctrl.attach_pipeline_vision(vision_pipeline)  

zumi.clear_screen()

# zumi.celebrate_reaction() # réaction de célébration au démarrage ATTENTION LE ROBOT BOUGE


def debug_vision():
    vision_pipeline.start()
    while vision_pipeline.is_running():
        try:
            results = vision_pipeline.step()
            # On affiche les résultats dans le terminal
            print("Résultats vision: {}".format(results))
        except Exception as e:
            print("Erreur dans la boucle debug: {}".format(e))
        time.sleep(0.1) # 10 fois par seconde suffit pour le debug

# Lance cela dans un thread pour ne pas bloquer Flask
threading.Thread(target=debug_vision, daemon=True).start()






# ----------------------------------------------------------------------------
#                           Démarrage du serveur
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    # Démarrage du watchdog des moteurs dans un thread séparé
    watchdog_thread = threading.Thread(target=ctrl.motor_watchdog)
    watchdog_thread.daemon = True # S'assure qu'il s'arrête avec le script
    watchdog_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)

    print("Flask server arrêté")
    # Lorsque le serveur Flask s'arrête, on arrête aussi le programme principal
    exit(0)