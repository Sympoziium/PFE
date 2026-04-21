#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py

# import essentiels
import os
import signal
import threading
import time
import logging
import builtins

# -----------------------------------------------------------------------------
# Gestion des profils de verbosité (désactive les logs de Flask/Werkzeug)
# -----------------------------------------------------------------------------
VERBOSITY_LEVEL = "verbose"  # Options: "silent", "prints_only", "verbose"

_original_print = builtins.print

def _verbosity_print(*args, **kwargs):
    if VERBOSITY_LEVEL == "verbose":
        _original_print(*args, **kwargs)
        return

    # Convert args to text
    out_text = " ".join(str(a) for a in args)

    # Messages essentiels conservés dans tous les modes (Boot et Profilage Système)
    is_essential = any(tag in out_text for tag in [
        "[Zumi] CPU", "[RAM]", "[Timestamp]", "[BOOT]", "[Battery]",
        "DÉMARRAGE DU ZUMI", "Flask server", "Arrêt propre", "[Exception]"
    ])

    if VERBOSITY_LEVEL == "silent":
        if is_essential:
            _original_print(*args, **kwargs)
    elif VERBOSITY_LEVEL == "prints_only":
        # Masquer les messages typiquement étiquetés débug en mode intermédiaire
        if "[Debug]" not in out_text and "[Sampling]" not in out_text:
            _original_print(*args, **kwargs)

# Remplacer print globalement
builtins.print = _verbosity_print

# Désactiver les logs de requêtes du serveur Flask (Werkzeug)
werkzeug_log = logging.getLogger('werkzeug')
if VERBOSITY_LEVEL == "verbose":
    werkzeug_log.setLevel(logging.INFO)
else:
    werkzeug_log.setLevel(logging.ERROR)
# -----------------------------------------------------------------------------

from core.control.controlers.ml_controller import MLController
from core.robot.robot_zumi import RobotZumi
from core.vision import vision_pipeline
from core.vision.vision_adapter import VisionAdapter # nécessaire pour le bootstrap

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
    
    from core.vision.detectors.Stop_detector_cv import StopDetectorCV
    from core.vision.detectors.Haar_classifier import HaarDetector
    from core.vision.detectors.Line_detector import LineDetector

    line_detector = LineDetector(white_threshold=180, min_area=65, offset_ratio=0.65)
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
    vision_pipeline.add_detectors(stop_detector_HSV)
    vision_pipeline.add_detectors(haar_classifier)
    vision_pipeline.add_passive_detectors(haar_classifier)
    vision_pipeline.add_passive_detectors(line_detector)  # Le line_detector est utilisé à la fois en actif (PID) et passif (MLP)
    draw_progress_bar(zumi.screen, 70)
    
    # Étape 6 : Initialiser Flask et routes
    print("[BOOT] Initialisation du serveur Flask...")
    from interface import server_controller as flask_controller
    from interface import flask_router as routes
    
    # Activer le debug dans le contrôleur seulement en mode 'verbose'
    is_debug = (VERBOSITY_LEVEL == "verbose")
    ctrl = flask_controller.controller(zumi, debug=is_debug)
    
    routes.register_routes(ctrl)
    ctrl.attach_pipeline_vision(vision_pipeline)
    draw_progress_bar(zumi.screen, 90)
    
    # Étape 7 : Attacher le ControlManager
    print("[BOOT] Initialisation du ControlManager...")
    from core.control.control_manager import ControlManager
    control_manager = ControlManager(robot=zumi, vision_pipeline=vision_pipeline)

    from core.control.legacy.line_follower_controller import LineFollowerController
    from core.control.controlers.manual_controller import ManualController
    from core.control.controlers.ml_controller import MLController
    from core.control.controlers.pid_ir_controller import PIDIRController

    # instance de controlleur de suivi de ligne (legacy, vision-based)
    # line_follower_ctrl = LineFollowerController()
    # control_manager.register_controller(line_follower_ctrl.name, line_follower_ctrl)

    # instance de controlleur PID IR (suivi de ligne par capteurs IR bottom)
    pid_ir_ctrl = PIDIRController()
    control_manager.register_controller(pid_ir_ctrl.name, pid_ir_ctrl)

    # instance de controlleur manuel (contrôle direct depuis l'interface web)
    manual_ctrl = ManualController()
    control_manager.register_controller(manual_ctrl.name, manual_ctrl)

    # instance de controlleur ML (contrôle par apprentissage par imitation avec un modèle MLP)
    from core.vision.vision_adapter import VisionAdapter

    # ⚠️ IMPORTANT: La liste des classes DOIT correspondre exactement à celle utilisée lors de l'entraînement!
    classes = ['stop_sign', 'Pieton', 'Camion_Pompier']  # 3 classes pour 20 dims input
    adapter = VisionAdapter(320, 240, classes) # Initialisation nécessaire pour le MLController (ATTENTION LA TAILLE DE L'IMAGE EST ARDCODÉ ICI ON DEVRAIT REENDRE SA DYNAMIQUE en fonction du profil de caméra de détection passive)
    MLP_MODELS_DIR = os.path.join(os.path.dirname(__file__), 'core', 'control', 'controlers', 'models')
    MLP_model_path = os.path.join(MLP_MODELS_DIR, 'zumi_mlp.tflite')

    # Validation: vérifier que les dimensions correspondent
    print(f"[BOOT] ML Controller:")
    print(f"  - Classes utilisées: {classes}")

    ml_ctrl = MLController(vision_adapter=adapter, model_path=MLP_model_path)
    control_manager.register_controller(ml_ctrl.name, ml_ctrl)

    # Instance de contrôleur FSM circuit (navigation autonome avec gestion des virages)
    from core.control.controlers.circuit_fsm_controller import CircuitFSMController
    circuit_fsm_ctrl = CircuitFSMController()
    control_manager.register_controller(circuit_fsm_ctrl.name, circuit_fsm_ctrl)

    ctrl.attach_control_manager(control_manager)
    draw_progress_bar(zumi.screen, 95)
    
    # Étape 8 : Affichage final
    print("[BOOT] Bootstrap complet!")
    zumi.clear_screen()
    # zumi.display_text("READY!") broken
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

    watchdog_thread = threading.Thread(target=ctrl.Log_watchdog)
    watchdog_thread.daemon = True
    watchdog_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)
    exit(0)
