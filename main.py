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
from core.vision.detectors.Line_detector import LineFollowerControl

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
is_calibrating = False

follower = LineFollowerControl(kp=0.5, base_speed=20)

def control_loop():
    global is_calibrating
    vision_pipeline.start()
    
    while True:


        results = vision_pipeline.step()
        
        line_val = None
        for res in results:
            if res.get("detector") == "line":
                line_val = res.get("value")
        print(line_val)
        
        # 4. Logique de suivi
        if line_val is not None:
            l_speed, r_speed = follower.compute_commands(line_val)
            print('L = ', l_speed, 'R = ', r_speed)

            if (3 < abs(line_val) < 25):
                           
                zumi.turn(-line_val, duration=1.5, max_speed=25, accuracy=1)
                #zumi.control_motors(r_speed, l_speed)
        else:
            zumi.stop()

        time.sleep(0.05)





# ----------------------------------------------------------------------------
#                           Démarrage du serveur
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    # Démarrage du watchdog des moteurs dans un thread séparé
    watchdog_thread = threading.Thread(target=ctrl.motor_watchdog)
    watchdog_thread.daemon = True # S'assure qu'il s'arrête avec le script
    watchdog_thread.start()

    # 2. DÉMARRAGE DE L'ASSERVISSEMENT 
    # On lance la boucle de contrôle en arrière-plan
    control_thread = threading.Thread(target=control_loop)
    control_thread.daemon = True
    control_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)

    print("Flask server arrêté")
    # Lorsque le serveur Flask s'arrête, on arrête aussi le programme principal
    exit(0)