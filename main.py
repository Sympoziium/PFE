#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py

from core.robot.robot_zumi import RobotZumi
from core.vision.vision_pipeline import VisionPipeline
from core.vision.detectors.Stop_detector_zumi import StopDetectorZumi
from core.vision.detectors.Stop_detector_cv import StopDetectorCV
from core.vision.detectors.Haar_classifier import HaarDetector
from core.vision.detectors.Line_detector import LineDetector
from core.control.pid_controller import PIDController
from core.control.line_following_state_machine import LineFollowingStateMachine, State
from core.control.control_manager import ControlManager

from interface import server_controller as flask_controller
from interface import flask_router as routes

import os
import threading
import time

# Initialisation
zumi = RobotZumi()
stop_detector = StopDetectorZumi()
line_detector = LineDetector(white_threshold=180, min_area=50, offset_ratio=0.3)
haar_classifier = HaarDetector()
stop_detector_HSV = StopDetectorCV()

# SUPPRIMÉ: capture_hires obsolète - utiliser set_resolution() à la place

# Dossier contenant les modèles .xml pour les classificateurs de Haar       
MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')

# config du classificateur de Haar pour l'ajout de détecteurs
# haar_classifier.add_classifier('stop_sign Git', os.path.join(MODELS_DIR, 'stop_sign_classifier_2.xml'), scaleFactor=1.05, minNeighbors=5)

haar_classifier.add_classifier('stop_sign', os.path.join(MODELS_DIR, 'LBP_Stop_Sign.xml'), scaleFactor=1.03, minNeighbors=3)

haar_classifier.add_classifier('Pieton', os.path.join(MODELS_DIR, 'LBP_Beta_Prime.xml'), scaleFactor=1.03, minNeighbors=2)

haar_classifier.add_classifier('Camion_Pompier', os.path.join(MODELS_DIR, 'LBP_Camion_Beta.xml'), scaleFactor=1.05, minNeighbors=12)



# On ajoute le détecteur au pipeline de vision
# vision_pipeline.add_detectors(Lum_detector)
vision_pipeline = VisionPipeline(camera=zumi.camera)
vision_pipeline.add_detectors(line_detector)
vision_pipeline.add_detectors(stop_detector)
vision_pipeline.add_detectors(stop_detector_HSV)
vision_pipeline.add_detectors(haar_classifier)

# Ajout des détecteurs pour la détection passive (live feed)
# vision_pipeline.add_passive_detectors(stop_detector_cv)
vision_pipeline.add_passive_detectors(haar_classifier)

# PID Controller optimisé pour précision
pid_controller = PIDController(
    kp=0.2, 
    ki=0.0, 
    kd=0.1, 
    base_speed=15, 
    max_correction=25,
    rotation_mode=True,
    deadband=1,
    rotation_scale=0.2,
    auto_reset_threshold=80  # Se réinitialise si erreur > 80 pixels
)
# Machine à états
state_machine = LineFollowingStateMachine(
    robot=zumi,
    camera=zumi.camera,
    pid_controller=pid_controller,
    line_detector=line_detector,
    stop_condition_detector=stop_detector  # Optionnel: détecteur de panneau stop
)

# Configuration
PHOTOS_DIR = os.path.join(os.path.dirname(__file__), 'photos_sequence')
state_machine.set_photo_directory(PHOTOS_DIR)
state_machine.set_rotation_angle(90)  # Rotation de 90 degrés

# Contrôleur Flask
ctrl = flask_controller.controller(zumi, debug=True)  # Passer debug=True pour activer les logs de debug et les annotations détaillées
routes.register_routes(ctrl)
ctrl.attach_pipeline_vision(vision_pipeline)

# ---------------------------------------------------------------------------
#  Orchestrateur de contrôle (ControlManager)
# ---------------------------------------------------------------------------
control_manager = ControlManager(robot=zumi, vision_pipeline=vision_pipeline)
control_manager.register_pid(pid_controller)
control_manager.register_state_machine(state_machine)
control_manager.register_line_detector(line_detector)

# Attacher le ControlManager au serveur web
# (le server_controller délèguera les actions PID/step/state_machine au manager)
ctrl.attach_control_manager(control_manager)

# Rétro-compatibilité : la state_machine reste accessible directement
ctrl.state_machine = state_machine

zumi.clear_screen()


if __name__ == '__main__':
    # Au boot : seul le serveur Flask démarre.
    # La caméra, les détecteurs et les contrôleurs ne s'activent
    # qu'à la demande depuis l'interface web (bouton Start Camera,
    # activation PID, etc.).

    watchdog_thread = threading.Thread(target=ctrl.motor_watchdog)
    watchdog_thread.daemon = True
    watchdog_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)
    exit(0)