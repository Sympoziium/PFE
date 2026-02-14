#!/usr/bin/env python
# -*- coding: utf-8 -*-
# main.py

from core.robot.robot_zumi import RobotZumi
from core.vision.vision_pipeline import VisionPipeline
from core.vision.detectors.Luminosity import LuminosityDetector
from core.vision.detectors.Stop_detector_zumi import StopDetectorZumi
from core.vision.detectors.Line_detector import LineDetector
from core.robot.pid_controller import PIDController
from core.robot.line_following_state_machine import LineFollowingStateMachine, State

from interface import server_controller as controller_module
from interface import flask_router as routes

import os
import threading
import time

# Initialisation
zumi = RobotZumi()
Lum_detector = LuminosityDetector()
stop_detector = StopDetectorZumi()
line_detector = LineDetector(white_threshold=180, min_area=50, offset_ratio=0.3)

vision_pipeline = VisionPipeline(camera=zumi.camera)
vision_pipeline.add_detectors(Lum_detector)
vision_pipeline.add_detectors(stop_detector)
vision_pipeline.add_detectors(line_detector)

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
ctrl = controller_module.controller(zumi)
routes.register_routes(ctrl)
ctrl.attach_pipeline_vision(vision_pipeline)

# Attacher la state machine au contrôleur pour l'interface web
ctrl.state_machine = state_machine

zumi.clear_screen()

def control_loop():
    vision_pipeline.start()
    
    while True:
        try:
            results = vision_pipeline.step()
            
            # Stocker l'offset pour le PID
            line_val = None
            for res in results:
                if res.get("detector") == "line":
                    line_val = res.get("value")
            
            vision_pipeline.last_line_offset = line_val
            
            # Exécuter la machine à états si active
            if state_machine.is_running():
                frame = vision_pipeline.get_last_frame()
                if frame is not None:
                    state_info = state_machine.step(frame)
                    if state_info.get('state') == 'COMPLETED':
                        print("[MAIN] Séquence terminée!")
            
            if line_val is not None:
                print("Offset ligne: {}".format(line_val))
                
        except Exception as e:
            print("Erreur dans control_loop: {}".format(e))
            import traceback
            traceback.print_exc()
            time.sleep(0.1)

if __name__ == '__main__':
    watchdog_thread = threading.Thread(target=ctrl.motor_watchdog)
    watchdog_thread.daemon = True
    watchdog_thread.start()
    
    control_thread = threading.Thread(target=control_loop)
    control_thread.daemon = True
    control_thread.start()

    print("Flask server démarré")
    ctrl.app.run(host='0.0.0.0', port=5000, threaded=True)
    exit(0)