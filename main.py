#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py

# import essentiels
import os
import signal
import threading
import time
from core.robot.robot_zumi import RobotZumi

# ═════════════════════════════════════════════════════════════════════
#  Fonctions de bootstrap avec affichage de progression
# ═════════════════════════════════════════════════════════════════════

def draw_progress_bar(screen, percent):
    """
    Affiche une barre de chargement sur l'écran OLED du Zumi.
    
    Args:
        screen: Objet Screen du Zumi
        percent: Pourcentage de progression (0-100)
    """
    # Paramètres de la barre
    bar_x = 5
    bar_y = 35
    bar_width = 118
    bar_height = 12
    
    # Contour de la barre (rectangle vide)
    screen.draw_rect(bar_x, bar_y, bar_width, bar_height, thickness=1, fill_in=False)
    
    # Barre remplie proportionnelle au % (rectangle rempli partiel)
    filled_width = int((bar_width * percent) / 100.0)
    if filled_width > 0:
        screen.draw_rect(bar_x + 1, bar_y + 1, filled_width - 2, bar_height - 2, fill_in=True)

def bootstrap():
    """
    Fonction de bootstrap qui initialise tous les composants du Zumi
    avec affichage de progression sur l'écran OLED.
    
    Returns:
        Tuple (zumi, ctrl, vision_pipeline, control_manager)
    """
    
    # Étape 1 : Initialiser le robot
    print("[BOOT] Initialisation du robot...")
    zumi = RobotZumi()
    draw_progress_bar(zumi.screen, 5)
    time.sleep(0.2)
    
    # Étape 2 : Créer les détecteurs
    print("[BOOT] Chargement des détecteurs... (10-30%)")
    
    from core.vision.detectors.Stop_detector_zumi import StopDetectorZumi
    from core.vision.detectors.Stop_detector_cv import StopDetectorCV
    from core.vision.detectors.Haar_classifier import HaarDetector
    from core.vision.detectors.Line_detector import LineDetector
    stop_detector = StopDetectorZumi()
    draw_progress_bar(zumi.screen, 15)
    
    line_detector = LineDetector(white_threshold=180, min_area=50, offset_ratio=0.3)
    draw_progress_bar(zumi.screen, 20)
    
    haar_classifier = HaarDetector()
    draw_progress_bar(zumi.screen, 25)
    
    stop_detector_HSV = StopDetectorCV()
    draw_progress_bar(zumi.screen, 30)
    
    # Étape 3 : Charger les modèles Haar
    print("[BOOT] Chargement des modèles Haar...")
    MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'vision', 'detectors', 'models')
    
    haar_classifier.add_classifier('stop_sign', os.path.join(MODELS_DIR, 'LBP_Stop_Sign.xml'), scaleFactor=1.03, minNeighbors=3)
    draw_progress_bar(zumi.screen, 40)
    
    haar_classifier.add_classifier('Pieton', os.path.join(MODELS_DIR, 'LBP_Pieton.xml'), scaleFactor=1.03, minNeighbors=5)
    draw_progress_bar(zumi.screen, 50)
    
    haar_classifier.add_classifier('Camion_Pompier', os.path.join(MODELS_DIR, 'LBP_Camion_Beta.xml'), scaleFactor=1.05, minNeighbors=12)
    draw_progress_bar(zumi.screen, 60)
    
    # Étape 4 : Créer le pipeline de vision
    print("[BOOT] Initialisation du pipeline de vision...")
    from core.vision.vision_pipeline import VisionPipeline
    vision_pipeline = VisionPipeline(camera=zumi.camera)
    vision_pipeline.add_detectors(line_detector)
    vision_pipeline.add_detectors(stop_detector)
    vision_pipeline.add_detectors(stop_detector_HSV)
    vision_pipeline.add_detectors(haar_classifier)
    vision_pipeline.add_passive_detectors(haar_classifier)
    vision_pipeline.add_passive_detectors(line_detector)
    draw_progress_bar(zumi.screen, 70)
    
    # Étape 5 : Créer les contrôleurs
    print("[BOOT] Initialisation des contrôleurs...")
    from core.control.line_following_pid import PIDController
    from core.control.line_following_state_machine import LineFollowingStateMachine, State
    from core.control.control_manager import ControlManager
    pid_controller = PIDController(
        kp=0.2, 
        ki=0.0, 
        kd=0.1, 
        base_speed=15, 
        max_correction=25,
        rotation_mode=True,
        deadband=1,
        rotation_scale=0.2,
        auto_reset_threshold=80
    )
    draw_progress_bar(zumi.screen, 75)
    
    state_machine = LineFollowingStateMachine(
        robot=zumi,
        vision_pipeline=vision_pipeline,
        pid_controller=pid_controller,
        stop_condition_detector=stop_detector
    )
    
    state_machine.set_rotation_angle(90)
    draw_progress_bar(zumi.screen, 80)
    
    # Étape 6 : Initialiser Flask et routes
    print("[BOOT] Initialisation du serveur Flask...")
    from interface import server_controller as flask_controller
    from interface import flask_router as routes
    ctrl = flask_controller.controller(zumi, debug=True)
    routes.register_routes(ctrl)
    ctrl.attach_pipeline_vision(vision_pipeline)
    draw_progress_bar(zumi.screen, 90)
    
    # Étape 7 : Attacher le ControlManager
    print("[BOOT] Initialisation du ControlManager...")
    control_manager = ControlManager(robot=zumi, vision_pipeline=vision_pipeline)
    control_manager.register_pid(pid_controller)
    control_manager.register_state_machine(state_machine)

    from core.control.line_follower_controller import LineFollowerController
    line_follower_ctrl = LineFollowerController()
    control_manager.register_controller(line_follower_ctrl)
    
    ctrl.attach_control_manager(control_manager)
    ctrl.state_machine = state_machine
    draw_progress_bar(zumi.screen, 95)
    
    # Étape 8 : Affichage final
    print("[BOOT] Bootstrap complet!")
    zumi.clear_screen()
    zumi.display_text("READY!")
    time.sleep(0.5)
    zumi.clear_screen()
    
    return zumi, ctrl, vision_pipeline, control_manager


if __name__ == '__main__':
    # Lance le bootstrap avec affichage de progression
    print("\n" + "="*60)
    print("  DÉMARRAGE DU ZUMI - AFFICHAGE EN DIRECT SUR L'OLED")
    print("="*60 + "\n")
    
    zumi, ctrl, vision_pipeline, control_manager = bootstrap()
    
    # Nettoyage propre sur Ctrl+C / kill : libère le socket pour ne pas
    # avoir à relancer zumi_prepare.sh fast entre deux tests.
    def _shutdown(sig, frame):
        print("\n🛑 Arrêt propre...")
        zumi.clear_screen()
        os._exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

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