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


class StepState(Enum):
    """États pour la machine step-by-step (mode avancé)."""
    IDLE = 0
    MOVING = 1  # Robot en mouvement
    WAITING_APPROVAL = 2  # Attend validation utilisateur
    SEARCHING_LINE = 3  # Cherche la ligne en tournant
    LINE_LOST = 4  # Ligne perdue
    STOPPED = 5  # Arrêt complet
    # NOUVEAUX ÉTATS pour mode Step-by-Step avancé
    SEARCH_SPIN = 10  # Rotation par paliers de 10°
    SEARCH_CAPTURE = 11  # Capture et analyse d'image
    APPROACH_LINE = 12  # Avance vers la ligne détectée
    RECENTER = 13  # Recentrage sur la ligne avec turn(angle)

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


class StepByStepStateMachine:
    """
    Machine à états pour le mode avancé avec avancement étape par étape.
    
    Le robot avance, s'arrête pour que l'image soit nette, attend la validation
    de l'utilisateur, puis recalcule et continue.
    
    Si la ligne est perdue, le robot la cherche en tournant sur lui-même.
    
    Mode Step-by-Step Avancé:
    - Recherche de ligne par rotation de 10° avec capture d'image entre chaque rotation
    - Approche de la ligne avec calcul de distance proportionnelle
    - Recentrage automatique avec turn(angle)
    - Contrôle utilisateur avec bouton d'autorisation
    - Feedback visuel sur l'écran avant chaque action
    """
    
    def __init__(self, robot, camera, pid_controller, line_detector):
        """
        Initialise la machine à états step-by-step.
        
        Args:
            robot: Instance du robot Zumi
            camera: Instance de la caméra
            pid_controller: Instance du contrôleur PID
            line_detector: Détecteur de ligne
        """
        self.robot = robot
        self.camera = camera
        self.pid_controller = pid_controller
        self.line_detector = line_detector
        
        self.state = StepState.IDLE
        self.running = False
        self.approved_to_move = False  # Validation utilisateur
        
        # Paramètres configurables
        self.step_duration = 0.5  # Durée d'un pas en secondes
        self.search_rotation_angle = 10  # Angle de rotation pour chercher (degrés)
        self.max_search_attempts = 36  # 36 * 10° = 360° (un tour complet)
        self.line_lost_threshold = 10  # Nombre de frames sans ligne avant de chercher
        self.approach_speed = 15  # Vitesse d'approche vers la ligne
        self.approach_duration_per_pixel = 0.002  # Durée d'avance par pixel de distance (2ms/px)
        self.recenter_tolerance = 20  # Tolérance d'offset pour considérer centré (pixels)
        
        # Variables d'état
        self.line_lost_count = 0
        self.search_attempts = 0
        self.step_count = 0
        self.last_line_offset = None
        self.last_line_distance = None  # Distance verticale à la ligne (en pixels)
        self.movement_start_time = None
        self.frames_to_skip_after_rotation = 0  # Compteur pour skip des frames après rotation
        self.startup_grace_period = 10  # Frames à ignorer au démarrage pour stabilisation caméra
        self.current_action_message = ""  # Message d'action en cours pour l'utilisateur
        self.recenter_attempts = 0  # Compteur de tentatives de recentrage
        self.max_recenter_attempts = 3  # Maximum de tentatives de recentrage
        
    def start(self):
        """Démarre la machine à états."""
        print("[STEP_MACHINE] Démarrage - État: WAITING_APPROVAL")
        self._display_message("Pret a demarrer")
        self.state = StepState.WAITING_APPROVAL
        self.running = True
        self.approved_to_move = False
        self.pid_controller.reset()
        
        # S'assurer que le PID est en mode avance (pas rotation)
        # pour permettre au robot de suivre la ligne
        self.pid_controller.update_params(rotation_mode=False)
        print("[STEP_MACHINE] PID configuré en mode avance (rotation_mode=False)")
        
        self.step_count = 0
        self.line_lost_count = 0
        self.search_attempts = 0
        self.recenter_attempts = 0
        self.startup_grace_period = 10  # Réinitialiser la période de grâce au démarrage
        print("[STEP_MACHINE] Période de grâce: 10 frames (~0.5s) pour stabilisation caméra")
        
    def stop(self):
        """Arrête la machine à états."""
        print("[STEP_MACHINE] Arrêt demandé")
        self._display_message("Arret")
        self.running = False
        self.robot.stop()
        self.state = StepState.STOPPED
        self.approved_to_move = False
        
    def reset(self):
        """Réinitialise la machine à états."""
        self.stop()
        self.pid_controller.reset()
        self.step_count = 0
        self.line_lost_count = 0
        self.search_attempts = 0
        self.recenter_attempts = 0
        self.last_line_offset = None
        self.last_line_distance = None
        self.frames_to_skip_after_rotation = 0
        self.startup_grace_period = 10
        self.state = StepState.IDLE
        self._display_message("Reset OK")
        
    def approve_next_step(self):
        """Autorise le prochain mouvement (appelé par l'interface)."""
        print("[STEP_MACHINE] Prochaine étape approuvée par l'utilisateur")
        self.approved_to_move = True
        
    def _display_message(self, message):
        """Affiche un message sur l'écran du robot."""
        self.current_action_message = message
        print("[STEP_MACHINE] Message: {}".format(message))
        if hasattr(self.robot, 'display_text'):
            try:
                self.robot.display_text(message)
            except Exception as e:
                print("[STEP_MACHINE] Erreur affichage: {}".format(e))
    
    def _calculate_line_distance(self, frame):
        """
        Calcule la distance verticale approximative à la ligne.
        
        Retourne la position Y moyenne des pointillés détectés (plus bas = plus proche).
        Plus le nombre est grand, plus le robot est loin de la ligne.
        
        Returns:
            int: Distance en pixels depuis le haut de la zone de détection (ou None)
        """
        # On doit accéder aux données internes du détecteur
        # Pour l'instant, on utilise une heuristique simple basée sur l'offset
        # Si l'offset est petit, la ligne est proche et centrée
        # On pourrait améliorer cela en modifiant le détecteur pour retourner aussi la position Y
        
        # Heuristique: distance inversement proportionnelle à la taille de l'offset
        # Plus l'offset est petit = ligne bien visible et proche
        # Pour l'instant, retourner une distance fixe basée sur la hauteur de l'image
        
        height = frame.shape[0]
        # Distance par défaut: 30% de la hauteur de l'image
        default_distance = int(height * 0.3)
        
        return default_distance
        
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
            if self.state == StepState.WAITING_APPROVAL:
                return self._handle_waiting_approval(frame)
                
            elif self.state == StepState.MOVING:
                return self._handle_moving(frame)
                
            elif self.state == StepState.SEARCHING_LINE:
                return self._handle_searching_line(frame)
            
            elif self.state == StepState.SEARCH_SPIN:
                return self._handle_search_spin(frame)
            
            elif self.state == StepState.SEARCH_CAPTURE:
                return self._handle_search_capture(frame)
            
            elif self.state == StepState.APPROACH_LINE:
                return self._handle_approach_line(frame)
            
            elif self.state == StepState.RECENTER:
                return self._handle_recenter(frame)
                
            elif self.state == StepState.LINE_LOST:
                return self._handle_line_lost(frame)
                
            elif self.state == StepState.STOPPED:
                return self._handle_stopped()
                
        except Exception as e:
            print("[STEP_MACHINE ERROR] {}".format(e))
            import traceback
            traceback.print_exc()
            self.robot.stop()
            self.state = StepState.STOPPED
            return {'state': 'ERROR', 'error': str(e)}
        
        return {'state': self.state.name}
    
    def _handle_waiting_approval(self, frame):
        """Gère l'état d'attente de validation."""
        # Vérifier que la ligne est toujours visible
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        # Période de grâce au démarrage - ne pas compter les frames perdues
        if self.startup_grace_period > 0:
            self.startup_grace_period -= 1
            print("[STEP_MACHINE] Période de grâce: {} frames restantes (line_offset={})".format(
                self.startup_grace_period, line_offset))
            # Pendant la période de grâce, si on détecte la ligne, on la garde
            if line_offset is not None:
                self.line_lost_count = 0
                self.last_line_offset = line_offset
            # On ne passe PAS en mode recherche pendant la période de grâce
            self._display_message("Initialisation...")
            return {
                'state': self.state.name,
                'line_offset': line_offset,
                'waiting_approval': True,
                'grace_period': self.startup_grace_period,
                'step': self.step_count
            }
        
        if line_offset is None:
            self.line_lost_count += 1
            print("[STEP_MACHINE] Ligne non détectée ({}/{} avant recherche)".format(
                self.line_lost_count, self.line_lost_threshold))
            if self.line_lost_count >= self.line_lost_threshold:
                print("[STEP_MACHINE] Ligne perdue - Passage en mode recherche (SEARCH_SPIN)")
                self._display_message("Recherche ligne...")
                self.state = StepState.SEARCH_SPIN
                self.search_attempts = 0
                self.frames_to_skip_after_rotation = 0
                # Afficher l'action à venir
                self._display_message("Tournera 10deg")
                return {'state': self.state.name, 'line_offset': None}
        else:
            self.line_lost_count = 0
            self.last_line_offset = line_offset
            self.last_line_distance = self._calculate_line_distance(frame)
        
        # Attendre l'approbation
        if self.approved_to_move:
            print("[STEP_MACHINE] Début du mouvement (étape {})".format(self.step_count + 1))
            self.approved_to_move = False
            self.state = StepState.MOVING
            self.movement_start_time = time.time()
            self.step_count += 1
            self._display_message("Avance...")
            return {'state': self.state.name, 'line_offset': line_offset, 'step': self.step_count}
        
        # Pas encore approuvé, rester en attente
        self._display_message("Appuyez bouton")
        return {
            'state': self.state.name,
            'line_offset': line_offset,
            'waiting_approval': True,
            'step': self.step_count,
            'message': self.current_action_message
        }
    
    def _handle_moving(self, frame):
        """Gère l'état de mouvement."""
        # Détecter la ligne
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        if line_offset is None:
            # Ligne perdue pendant le mouvement
            self.robot.stop()
            self.line_lost_count += 1
            
            if self.line_lost_count >= self.line_lost_threshold:
                print("[STEP_MACHINE] Ligne perdue pendant le mouvement")
                self.state = StepState.SEARCHING_LINE
                self.search_attempts = 0
                self.frames_to_skip_after_rotation = 0  # Reset du compteur
                return {'state': self.state.name, 'line_offset': None}
            
            # Continuer avec la dernière valeur connue si disponible
            if self.last_line_offset is not None:
                line_offset = self.last_line_offset
            else:
                # Pas de valeur connue, arrêter
                self.state = StepState.WAITING_APPROVAL
                return {'state': self.state.name, 'line_offset': None}
        else:
            self.line_lost_count = 0
            self.last_line_offset = line_offset
        
        # Calculer et appliquer la commande PID
        left_speed, right_speed = self.pid_controller.compute(line_offset)
        self.robot.control_motors(left_speed, right_speed)
        
        # Vérifier si la durée du pas est écoulée
        elapsed = time.time() - self.movement_start_time
        if elapsed >= self.step_duration:
            print("[STEP_MACHINE] Fin du mouvement - Arrêt pour stabilisation")
            self.robot.stop()
            self.state = StepState.WAITING_APPROVAL
            time.sleep(0.3)  # Pause pour que l'image se stabilise
            return {
                'state': self.state.name,
                'line_offset': line_offset,
                'left_speed': left_speed,
                'right_speed': right_speed,
                'step_completed': True,
                'step': self.step_count
            }
        
        return {
            'state': self.state.name,
            'line_offset': line_offset,
            'left_speed': left_speed,
            'right_speed': right_speed,
            'elapsed': elapsed,
            'step': self.step_count
        }
    
    
    def _handle_search_spin(self, frame):
        """
        Gère l'état de rotation par paliers de 10° pendant la recherche.
        Attend l'approbation utilisateur avant de tourner.
        """
        # Attendre l'approbation de l'utilisateur
        if not self.approved_to_move:
            self._display_message("Tourner 10deg? Appuyez")
            return {
                'state': self.state.name,
                'waiting_approval': True,
                'search_attempts': self.search_attempts
            }
        
        # Reset de l'approbation
        self.approved_to_move = False
        
        # Vérifier si on a dépassé le nombre maximal de tentatives
        if self.search_attempts >= self.max_search_attempts:
            print("[STEP_MACHINE] Ligne non trouvée après {} tentatives - Arrêt".format(self.max_search_attempts))
            self._display_message("Ligne perdue!")
            self.robot.stop()
            self.state = StepState.LINE_LOST
            return {
                'state': self.state.name,
                'search_failed': True
            }
        
        # Effectuer la rotation de 10°
        self.search_attempts += 1
        print("[STEP_MACHINE] Rotation de {}° (tentative {}/{})".format(
            self.search_rotation_angle, self.search_attempts, self.max_search_attempts))
        
        self._display_message("Tourne {}deg...".format(self.search_rotation_angle))
        
        # Utiliser la méthode turn() du robot
        angle = self.search_rotation_angle  # Toujours tourner dans le même sens (gauche)
        if hasattr(self.robot, 'turn'):
            self.robot.turn(angle)
        else:
            # Rotation manuelle si turn() n'existe pas
            speed = 10
            duration = abs(angle) / 90.0 * 0.3
            self.robot.control_motors(speed, -speed)
            time.sleep(duration)
            self.robot.stop()
        
        # Petite pause pour stabilisation
        time.sleep(0.2)
        
        # Passer à l'état de capture d'image
        print("[STEP_MACHINE] Rotation terminée - Passage à SEARCH_CAPTURE")
        self.state = StepState.SEARCH_CAPTURE
        self.frames_to_skip_after_rotation = 3  # Skip 3 frames pour stabilisation
        
        return {
            'state': self.state.name,
            'rotation_completed': True,
            'angle': angle,
            'search_attempts': self.search_attempts
        }
    
    def _handle_search_capture(self, frame):
        """
        Gère l'état de capture et analyse d'image après rotation.
        Détecte si la ligne est visible dans l'image capturée.
        """
        # Période de stabilisation après rotation
        if self.frames_to_skip_after_rotation > 0:
            print("[STEP_MACHINE] Stabilisation... (frames restantes: {})".format(
                self.frames_to_skip_after_rotation))
            self.frames_to_skip_after_rotation -= 1
            self._display_message("Stabilisation...")
            return {
                'state': self.state.name,
                'waiting_stabilization': True,
                'frames_remaining': self.frames_to_skip_after_rotation
            }
        
        # Capturer et analyser l'image
        print("[STEP_MACHINE] Capture et analyse de l'image...")
        self._display_message("Analyse image...")
        
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        print("[STEP_MACHINE] Résultat détection: line_offset={}".format(line_offset))
        
        if line_offset is not None:
            # Ligne retrouvée !
            print("[STEP_MACHINE] *** LIGNE RETROUVÉE *** offset={}".format(line_offset))
            self.robot.stop()
            self.line_lost_count = 0
            self.last_line_offset = line_offset
            self.last_line_distance = self._calculate_line_distance(frame)
            
            # Passer à l'état APPROACH_LINE pour s'approcher de la ligne
            print("[STEP_MACHINE] Transition vers APPROACH_LINE")
            self._display_message("Ligne trouvee!")
            time.sleep(0.5)  # Pause pour que l'utilisateur voie le message
            self.state = StepState.APPROACH_LINE
            
            return {
                'state': self.state.name,
                'line_found': True,
                'line_offset': line_offset,
                'search_attempts': self.search_attempts
            }
        else:
            # Ligne non trouvée, retourner à SEARCH_SPIN pour tourner encore
            print("[STEP_MACHINE] Ligne non trouvée - Retour à SEARCH_SPIN")
            self.state = StepState.SEARCH_SPIN
            
            return {
                'state': self.state.name,
                'line_offset': None,
                'continuing_search': True,
                'search_attempts': self.search_attempts
            }
    
    def _handle_approach_line(self, frame):
        """
        Gère l'état d'approche de la ligne détectée.
        Calcule la distance et avance proportionnellement.
        Attend l'approbation utilisateur avant d'avancer.
        """
        # Vérifier si on doit d'abord se recentrer
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        if line_offset is None:
            # Ligne perdue pendant l'approche
            print("[STEP_MACHINE] Ligne perdue pendant l'approche - Retour à SEARCH_SPIN")
            self._display_message("Ligne perdue!")
            self.state = StepState.SEARCH_SPIN
            self.search_attempts = 0
            return {
                'state': self.state.name,
                'line_lost_during_approach': True
            }
        
        self.last_line_offset = line_offset
        
        # Si l'offset est trop grand, passer d'abord par RECENTER
        if abs(line_offset) > self.recenter_tolerance:
            print("[STEP_MACHINE] Offset trop grand ({}px) - Passage à RECENTER".format(line_offset))
            self._display_message("Recentrage...")
            self.state = StepState.RECENTER
            self.recenter_attempts = 0
            return {
                'state': self.state.name,
                'line_offset': line_offset,
                'needs_recenter': True
            }
        
        # Attendre l'approbation de l'utilisateur
        if not self.approved_to_move:
            distance = self.last_line_distance if self.last_line_distance else 100
            self._display_message("Avancer {}px? Appuyez".format(distance))
            return {
                'state': self.state.name,
                'waiting_approval': True,
                'line_offset': line_offset,
                'distance': distance
            }
        
        # Reset de l'approbation
        self.approved_to_move = False
        
        # Calculer la distance à parcourir
        distance = self.last_line_distance if self.last_line_distance else 100
        approach_duration = distance * self.approach_duration_per_pixel
        
        print("[STEP_MACHINE] Approche de la ligne - Distance: {}px, Durée: {:.2f}s".format(
            distance, approach_duration))
        self._display_message("Avance {}px...".format(distance))
        
        # Avancer tout droit (sans PID, juste avancer vers la ligne)
        self.robot.control_motors(self.approach_speed, self.approach_speed)
        time.sleep(approach_duration)
        self.robot.stop()
        
        # Pause pour stabilisation
        time.sleep(0.3)
        
        # Après avoir avancé, vérifier si la ligne est toujours visible
        print("[STEP_MACHINE] Vérification après approche...")
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        if line_offset is None:
            # Ligne perdue après approche
            print("[STEP_MACHINE] Ligne perdue après approche - Retour à SEARCH_SPIN")
            self._display_message("Ligne perdue!")
            self.state = StepState.SEARCH_SPIN
            self.search_attempts = 0
            return {
                'state': self.state.name,
                'line_lost_after_approach': True
            }
        
        # Ligne toujours visible, passer à RECENTER pour se recentrer
        print("[STEP_MACHINE] Approche terminée - Passage à RECENTER")
        self.state = StepState.RECENTER
        self.recenter_attempts = 0
        
        return {
            'state': self.state.name,
            'approach_completed': True,
            'distance_traveled': distance,
            'line_offset': line_offset
        }
    
    def _handle_recenter(self, frame):
        """
        Gère l'état de recentrage sur la ligne.
        Utilise turn(angle) pour aligner le robot avec la ligne.
        """
        # Vérifier que la ligne est toujours visible
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        if line_offset is None:
            # Ligne perdue pendant le recentrage
            print("[STEP_MACHINE] Ligne perdue pendant le recentrage - Retour à SEARCH_SPIN")
            self._display_message("Ligne perdue!")
            self.state = StepState.SEARCH_SPIN
            self.search_attempts = 0
            return {
                'state': self.state.name,
                'line_lost_during_recenter': True
            }
        
        self.last_line_offset = line_offset
        
        # Vérifier si on est suffisamment centré
        if abs(line_offset) <= self.recenter_tolerance:
            print("[STEP_MACHINE] Robot bien centré (offset={}px) - Transition vers WAITING_APPROVAL".format(line_offset))
            self._display_message("Bien centre!")
            time.sleep(0.3)
            self.state = StepState.WAITING_APPROVAL
            self.recenter_attempts = 0
            return {
                'state': self.state.name,
                'centered': True,
                'line_offset': line_offset
            }
        
        # Vérifier si on a dépassé le nombre maximal de tentatives de recentrage
        if self.recenter_attempts >= self.max_recenter_attempts:
            print("[STEP_MACHINE] Trop de tentatives de recentrage ({}) - Transition vers WAITING_APPROVAL".format(
                self.recenter_attempts))
            self._display_message("Recentrage OK")
            time.sleep(0.3)
            self.state = StepState.WAITING_APPROVAL
            self.recenter_attempts = 0
            return {
                'state': self.state.name,
                'recenter_max_attempts': True,
                'line_offset': line_offset
            }
        
        # Attendre l'approbation de l'utilisateur
        if not self.approved_to_move:
            # Calculer l'angle de correction basé sur l'offset
            # Heuristique: 1 pixel = ~0.1 degré (à ajuster selon votre configuration)
            correction_angle = int(line_offset * 0.15)  # Plus agressif: 0.15 deg/px
            self._display_message("Tourner {}deg? Appuyez".format(correction_angle))
            return {
                'state': self.state.name,
                'waiting_approval': True,
                'line_offset': line_offset,
                'correction_angle': correction_angle
            }
        
        # Reset de l'approbation
        self.approved_to_move = False
        self.recenter_attempts += 1
        
        # Calculer l'angle de correction
        correction_angle = int(line_offset * 0.15)
        
        print("[STEP_MACHINE] Recentrage - Offset: {}px, Angle: {}° (tentative {}/{})".format(
            line_offset, correction_angle, self.recenter_attempts, self.max_recenter_attempts))
        
        self._display_message("Recentre {}deg...".format(correction_angle))
        
        # Effectuer la rotation de correction
        if hasattr(self.robot, 'turn'):
            self.robot.turn(correction_angle)
        else:
            # Rotation manuelle
            direction = 1 if correction_angle > 0 else -1
            speed = 10
            duration = abs(correction_angle) / 90.0 * 0.3
            self.robot.control_motors(direction * speed, -direction * speed)
            time.sleep(duration)
            self.robot.stop()
        
        # Pause pour stabilisation
        time.sleep(0.3)
        
        # Rester dans l'état RECENTER pour vérifier le résultat au prochain cycle
        print("[STEP_MACHINE] Recentrage effectué - Vérification au prochain cycle")
        
        return {
            'state': self.state.name,
            'recenter_attempt': self.recenter_attempts,
            'correction_angle': correction_angle,
            'line_offset': line_offset
        }
    
    def _handle_searching_line(self, frame):
        """
        Handler de compatibilité pour SEARCHING_LINE.
        Redirige vers SEARCH_SPIN pour utiliser le nouveau flux.
        """
        print("[STEP_MACHINE] SEARCHING_LINE détecté - Redirection vers SEARCH_SPIN")
        self.state = StepState.SEARCH_SPIN
        self.search_attempts = 0
        return self._handle_search_spin(frame)
        """Gère l'état de ligne perdue définitivement."""
        print("[STEP_MACHINE] Ligne perdue - En attente d'intervention manuelle")
        self.robot.stop()
        
        # Vérifier quand même si la ligne réapparaît
        line_result = self.line_detector.process(frame.copy())
        line_offset = line_result.get('value')
        
        if line_offset is not None:
            print("[STEP_MACHINE] Ligne détectée à nouveau!")
            self.line_lost_count = 0
            self.last_line_offset = line_offset
            self.search_attempts = 0
            self.state = StepState.WAITING_APPROVAL
            return {
                'state': self.state.name,
                'line_offset': line_offset,
                'line_recovered': True
            }
        
        return {
            'state': self.state.name,
            'line_offset': None,
            'line_lost': True
        }
    
    def _handle_stopped(self):
        """Gère l'état d'arrêt."""
        self.robot.stop()
        return {
            'state': self.state.name,
            'stopped': True,
            'steps_completed': self.step_count
        }
    
    def get_state(self):
        """Retourne l'état actuel."""
        return self.state
    
    def is_running(self):
        """Vérifie si la machine est en cours d'exécution."""
        return self.running
    
    def is_waiting_approval(self):
        """Vérifie si la machine attend une approbation."""
        return self.state == StepState.WAITING_APPROVAL
