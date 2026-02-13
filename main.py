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
from core.vision.detectors.Stop_detector_zumi import StopDetectorZumi
from core.vision.detectors.Stop_detector_cv import StopDetectorCV
from core.vision.detectors.Stop_detector_matt import StopDetectorMatt
from core.vision.detectors.Haar_classifier import HaarDetector
from core.vision.detectors.Line_detector import LineDetector

# Import pour le serveur web (Flask)
from interface import server_controller as controller_module
from interface import flask_router as routes

# Import utilitaire
import os
import threading


# ----------------------------------------------------------------------------
#                           Initialisation
# ----------------------------------------------------------------------------

# Initialisation du robot Zumi
zumi = RobotZumi()

# Initialisation du pipeline de vision
Lum_detector = LuminosityDetector()
stop_detector = StopDetectorZumi()
stop_detector_cv = StopDetectorCV(min_area=400, aspect_tol=0.4, poly_min=6, poly_max=10)
stop_detector_matt = StopDetectorMatt(min_area=400, min_score=0.35)
haar_classifier = HaarDetector()
vision_pipeline = VisionPipeline(camera=zumi.camera)
line_detector = LineDetector()

# Dossier contenant les modèles .xml pour les classificateurs de Haar       
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')

# config du classificateur de Haar pour l'ajout de détecteurs
haar_classifier.add_classifier('stop_sign', os.path.join(MODELS_DIR, 'stop_sign_classifier_2.xml'))

# On ajoute le détecteur au pipeline de vision
vision_pipeline.add_detectors(Lum_detector)
vision_pipeline.add_detectors(stop_detector)
vision_pipeline.add_detectors(stop_detector_cv)
vision_pipeline.add_detectors(stop_detector_matt)
vision_pipeline.add_detectors(haar_classifier)
vision_pipeline.add_detectors(line_detector)
# Initialisation du contrôleur (serveur Flask)
ctrl = controller_module.controller(zumi)
routes.register_routes(ctrl) # on enregistre les routes sur l'instance Flask du contrôleur (build du serveur)
# On attache le pipeline de vision au contrôleur
ctrl.attach_pipeline_vision(vision_pipeline)  

zumi.clear_screen()

# zumi.celebrate_reaction() # réaction de célébration au démarrage ATTENTION LE ROBOT BOUGE

import time
def control_loop():
    vision_pipeline.start()

    while True:

        # 1. On récupère l'image actuelle du pipeline
        frame = vision_pipeline.get_last_frame()
        
        if frame is not None:
            # 2. On fait passer l'image dans les détecteurs
            # Comme ils dessinent sur 'frame', l'objet est modifié ici
            results = []
            for detector in vision_pipeline.get_detectors():
                try:
                    res = detector.process(frame)
                    results.append(res)
                except Exception as e:
                    print("Erreur détecteur: {}".format(e))

            # 3. CRUCIAL : On renvoie l'image annotée au pipeline pour Flask
            vision_pipeline.update_last_frame(frame)

            # 4. Logique d'affichage console pour le debug
            line_val = None
            for res in results:
                if res.get("detector") == "line":
                    line_val = res.get("value")
            if line_val is not None:
                print("Offset ligne: {}".format(line_val))
        
        time.sleep(0.05)
        
        time.sleep(0.05)


# ----------------------------------------------------------------------------
#                           Démarrage du serveur
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    # Démarrage du watchdog des moteurs dans un thread séparé
    watchdog_thread = threading.Thread(target=ctrl.motor_watchdog)
    watchdog_thread.daemon = True # S'assure qu'il s'arrête avec le script
    watchdog_thread.start()

    
    control_thread = threading.Thread(target=control_loop)
    control_thread.daemon = True
    control_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)

    print("Flask server arrêté")
    # Lorsque le serveur Flask s'arrête, on arrête aussi le programme principal
    exit(0)


