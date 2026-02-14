#!/usr/bin/env python
# -*- coding: utf-8 -*-
# line_following_state_machine.py
# ------------------
"""Machine à états pour le suivi de ligne avec arrêt et actions."""

import time
import os
from enum import Enum

class State(Enum):
    """États possibles de la machine."""
    IDLE = 0
    FOLLOWING_LINE = 1
    STOPPED_AT_MARKER = 2
    TAKING_PHOTO = 3
    ROTATING = 4
    COMPLETED = 5
    ERROR = 6

class LineFollowingStateMachine:
    def __init__(self, robot, camera, pid_controller, line_detector, stop_condition_detector=None):
        """
        Initialise la machine à états.
        
        Args:
            robot: Instance du robot Zumi
            camera: Instance de la caméra
            pid_controller: Instance du contrôleur PID
            line_detector: Détecteur de ligne
            stop_condition_detector: Détecteur optionnel pour détecter un marqueur d'arrêt
        """
        self.robot = robot
        self.camera = camera
        self.pid_controller = pid_controller
        self.line_detector = line_detector
        self.stop_condition_detector = stop_condition_detector
        
        self.state = State.IDLE
        self.running = False
        
        # Paramètres configurables
        self.rotation_angle = 90  # Degrés
        self.photo_save_dir = None
        self.stop_marker_detected_count = 0
        self.stop_marker_threshold = 3  # Nombre de détections consécutives nécessaires
        
        # Historique
        self.photos_taken = []
        self.rotation_count = 0
        
    def set_photo_directory(self, directory):
        """Définit le répertoire de sauvegarde des photos."""
        self.photo_save_dir = directory
        os.makedirs(directory, exist_ok=True)
        
    def set_rotation_angle(self, angle):
        """Définit l'angle de rotation en degrés."""
        self.rotation_angle = angle
        
    def start(self):
        """Démarre la machine à états en mode suivi de ligne."""
        print("[STATE_MACHINE] Démarrage - État: FOLLOWING_LINE")
        self.state = State.FOLLOWING_LINE
        self.running = True
        self.pid_controller.reset()
        
    def stop(self):
        """Arrête la machine à états."""
        print("[STATE_MACHINE] Arrêt demandé")
        self.running = False
        self.robot.stop()
        self.state = State.IDLE
        
    def reset(self):
        """Réinitialise la machine à états."""
        self.stop()
        self.stop_marker_detected_count = 0
        self.photos_taken = []
        self.rotation_count = 0
        self.pid_controller.reset()
        
    def step(self, frame):
        """
        Exécute un cycle de la machine à états.
        
        Args:
            frame: Image actuelle de la caméra
            
        Returns:
            dict: État actuel et informations de debug
        """
        if not self.running:
            return {'state': self.state.name, 'active': False}
        
        try:
            if self.state == State.FOLLOWING_LINE:
                return self._handle_following_line(frame)
                
            elif self.state == State.STOPPED_AT_MARKER:
                return self._handle_stopped_at_marker(frame)
                
            elif self.state == State.TAKING_PHOTO:
                return self._handle_taking_photo(frame)
                
            elif self.state == State.ROTATING:
                return self._handle_rotating(frame)
                
            elif self.state == State.COMPLETED:
                return self._handle_completed()
                
            elif self.state == State.ERROR:
                return self._handle_error()
                
        except Exception as e:
            print("[STATE_MACHINE ERROR] {}".format(e))
            import traceback
            traceback.print_exc()
            self.state = State.ERROR
            return {'state': 'ERROR', 'error': str(e)}
        
        return {'state': self.state.name}
    
    def _handle_following_line(self, frame):
        """Gère l'état de suivi de ligne."""
        # 1. Détecter la ligne
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        # 2. Vérifier si un marqueur d'arrêt est détecté (optionnel)
        stop_detected = False
        if self.stop_condition_detector:
            stop_result = self.stop_condition_detector.process(frame.copy())
            stop_detected = stop_result.get('Object_detected', False)
            
            if stop_detected:
                self.stop_marker_detected_count += 1
            else:
                self.stop_marker_detected_count = 0
            
            # Si détecté N fois consécutivement, on s'arrête
            if self.stop_marker_detected_count >= self.stop_marker_threshold:
                print("[STATE_MACHINE] Marqueur d'arrêt détecté - Transition vers STOPPED_AT_MARKER")
                self.robot.stop()
                self.state = State.STOPPED_AT_MARKER
                time.sleep(0.5)  # Pause pour stabilisation
                return {'state': self.state.name, 'line_offset': line_offset, 'stop_detected': True}
        
        # 3. Si pas de ligne détectée, arrêter
        if line_offset is None:
            self.robot.stop()
            return {'state': self.state.name, 'line_offset': None, 'motors_stopped': True}
        
        # 4. Calculer et appliquer la commande PID
        left_speed, right_speed = self.pid_controller.compute(line_offset)
        self.robot.control_motors(left_speed, right_speed)
        
        return {
            'state': self.state.name,
            'line_offset': line_offset,
            'left_speed': left_speed,
            'right_speed': right_speed,
            'stop_marker_count': self.stop_marker_detected_count
        }
    
    def _handle_stopped_at_marker(self, frame):
        """Gère l'état d'arrêt au marqueur."""
        print("[STATE_MACHINE] Arrêté au marqueur - Transition vers TAKING_PHOTO")
        self.state = State.TAKING_PHOTO
        return {'state': self.state.name}
    
    def _handle_taking_photo(self, frame):
        """Gère la prise de photo."""
        print("[STATE_MACHINE] Prise de photo...")
        
        if self.photo_save_dir is None:
            print("[STATE_MACHINE WARNING] Aucun répertoire de sauvegarde défini")
            self.state = State.ROTATING
            return {'state': self.state.name, 'photo_taken': False}
        
        # Générer un nom de fichier unique
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = "photo_{}_rot{}.jpg".format(timestamp, self.rotation_count)
        filepath = os.path.join(self.photo_save_dir, filename)
        
        # Sauvegarder la photo
        import cv2
        success = cv2.imwrite(filepath, frame)
        
        if success:
            print("[STATE_MACHINE] Photo sauvegardée: {}".format(filepath))
            self.photos_taken.append(filepath)
        else:
            print("[STATE_MACHINE ERROR] Échec de sauvegarde de la photo")
        
        # Transition vers rotation
        self.state = State.ROTATING
        return {'state': self.state.name, 'photo_taken': success, 'photo_path': filepath if success else None}
    
    def _handle_rotating(self, frame):
        """Gère la rotation du robot."""
        print("[STATE_MACHINE] Rotation de {} degrés...".format(self.rotation_angle))
        
        # Utiliser le gyroscope du Zumi pour une rotation précise
        try:
            # Méthode 1: Utiliser turn() si disponible
            if hasattr(self.robot, 'turn'):
                self.robot.turn(self.rotation_angle)
            # Méthode 2: Utiliser turn_left() ou turn_right()
            elif hasattr(self.robot, 'turn_left') and hasattr(self.robot, 'turn_right'):
                if self.rotation_angle > 0:
                    self.robot.turn_left(abs(self.rotation_angle))
                else:
                    self.robot.turn_right(abs(self.rotation_angle))
            # Méthode 3: Rotation manuelle avec gyro
            else:
                self._rotate_with_gyro(self.rotation_angle)
            
            self.rotation_count += 1
            print("[STATE_MACHINE] Rotation terminée")
            
        except Exception as e:
            print("[STATE_MACHINE ERROR] Erreur lors de la rotation: {}".format(e))
        
        # Après rotation, retourner au suivi de ligne ou terminer
        # Option 1: Continuer à suivre la ligne
        print("[STATE_MACHINE] Reprise du suivi de ligne")
        self.state = State.FOLLOWING_LINE
        self.stop_marker_detected_count = 0  # Reset du compteur
        
        # Option 2: Terminer (décommenter pour utiliser)
        # self.state = State.COMPLETED
        
        return {'state': self.state.name, 'rotation_completed': True, 'angle': self.rotation_angle}
    
    def _rotate_with_gyro(self, angle):
        """Effectue une rotation précise en utilisant le gyroscope."""
        # Cette méthode nécessite l'accès au gyroscope du Zumi
        # Implémentation basique si turn() n'est pas disponible
        
        # Récupérer l'angle initial
        if hasattr(self.robot, 'read_z_angle'):
            initial_angle = self.robot.read_z_angle()
            target_angle = initial_angle + angle
            
            # Rotation avec feedback du gyro
            direction = 1 if angle > 0 else -1
            speed = 15  # Vitesse de rotation
            
            while abs(self.robot.read_z_angle() - target_angle) > 2:  # Tolérance de 2 degrés
                self.robot.control_motors(direction * speed, -direction * speed)
                time.sleep(0.02)
            
            self.robot.stop()
            time.sleep(0.2)  # Stabilisation
        else:
            # Fallback: rotation basée sur le temps (moins précise)
            duration = abs(angle) / 90.0 * 0.5  # Approximation
            direction = 1 if angle > 0 else -1
            speed = 15
            
            self.robot.control_motors(direction * speed, -direction * speed)
            time.sleep(duration)
            self.robot.stop()
    
    def _handle_completed(self):
        """Gère l'état de fin."""
        print("[STATE_MACHINE] Séquence terminée")
        self.robot.stop()
        self.running = False
        return {
            'state': self.state.name,
            'photos_taken': len(self.photos_taken),
            'rotations_completed': self.rotation_count
        }
    
    def _handle_error(self):
        """Gère l'état d'erreur."""
        print("[STATE_MACHINE] État d'erreur - Arrêt")
        self.robot.stop()
        self.running = False
        return {'state': self.state.name}
    
    def get_state(self):
        """Retourne l'état actuel."""
        return self.state
    
    def is_running(self):
        """Vérifie si la machine est en cours d'exécution."""
        return self.running