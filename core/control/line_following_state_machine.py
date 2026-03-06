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
    def __init__(self, robot, vision_pipeline, pid_controller, stop_condition_detector=None):
        """
        Initialise la machine à états.
        
        Args:
            robot: Instance du robot Zumi
            vision_pipeline: Instance du VisionPipeline (caméra + détecteurs)
            pid_controller: Instance du contrôleur PID
            stop_condition_detector: Détecteur optionnel pour détecter un marqueur d'arrêt
        """
        self.robot = robot
        self.vision_pipeline = vision_pipeline
        self.pid_controller = pid_controller
        self.stop_condition_detector = stop_condition_detector
        
        self.state = State.IDLE
        self.running = False
        
        # Trouver l'index du détecteur de ligne dans le pipeline
        self._line_detector_index = self._find_line_detector_index()
        
        # Paramètres configurables
        self.rotation_angle = 90  # Degrés
        self.stop_marker_detected_count = 0
        self.stop_marker_threshold = 3  # Nombre de détections consécutives nécessaires
        
        # Historique
        self.photos_taken = []
        self.rotation_count = 0
        
    def _find_line_detector_index(self):
        """Trouve l'index du détecteur de ligne dans le pipeline."""
        for i, det in enumerate(self.vision_pipeline.detectors):
            if getattr(det, 'name', '') == 'line':
                return i
        return None
    
    def _run_line_detection(self, frame):
        """Exécute la détection de ligne via le pipeline et retourne line_offset."""
        if self._line_detector_index is None:
            return None
        result = self.vision_pipeline.process_frame(frame.copy(), self._line_detector_index)
        if result is None:
            return None
        return result.get('line_offset')
        
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
        line_offset = self._run_line_detection(frame)
        
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
        
        photo_dir = self.vision_pipeline.CAPTURE_DIR
        if photo_dir is None:
            print("[STATE_MACHINE WARNING] Aucun répertoire de sauvegarde défini")
            self.state = State.ROTATING
            return {'state': self.state.name, 'photo_taken': False}
        
        os.makedirs(photo_dir, exist_ok=True)
        
        # Générer un nom de fichier unique
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        filename = "photo_{}_rot{}.jpg".format(timestamp, self.rotation_count)
        filepath = os.path.join(photo_dir, filename)
        
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
    
    def __init__(self, robot, vision_pipeline, pid_controller):
        """
        Initialise la machine à états step-by-step.
        
        Args:
            robot: Instance du robot Zumi
            vision_pipeline: Instance du VisionPipeline (caméra + détecteurs)
            pid_controller: Instance du contrôleur PID
        """
        self.robot = robot
        self.vision_pipeline = vision_pipeline
        self.pid_controller = pid_controller
        
        # Trouver l'index du détecteur de ligne dans le pipeline
        self._line_detector_index = self._find_line_detector_index()
        
        self.state = StepState.IDLE
        self.running = False
        self.approved_to_move = False  # Validation utilisateur
        
        # Paramètres configurables
        self.step_duration = 0.5  # Durée d'un pas en secondes
        self.search_rotation_angle = 10  # Angle de rotation pour chercher (degrés)
        self.max_search_attempts = 36  # 36 * 10° = 360° (un tour complet)
        self.line_lost_threshold = 15  # Nombre de frames sans ligne avant de chercher (~0.75s à 20Hz)
        self.approach_distance_cm = 10  # Distance fixe d'approche en cm
        self.approach_duration = 0.5  # Durée d'avance pour 10 cm (à ajuster selon robot)
        self.low_error_threshold = 20  # Seuil d'erreur faible pour avancer tout droit (pixels)
        self.recenter_tolerance = 20  # Tolérance d'offset pour considérer centré (pixels)
        self.straight_speed = 20  # Vitesse pour avancer tout droit (sans PID)
        
        # Variables d'état
        self.line_lost_count = 0
        self.search_attempts = 0
        self.step_count = 0
        self.last_line_offset = None
        self.movement_start_time = None
        self.frames_to_skip_after_rotation = 0  # Compteur pour skip des frames après rotation
        self.startup_grace_period = 15  # Frames à ignorer au démarrage pour stabilisation caméra (augmenté)
        self.current_action_message = ""  # Message d'action en cours pour l'utilisateur
        self.recenter_attempts = 0  # Compteur de tentatives de recentrage
        self.max_recenter_attempts = 3  # Maximum de tentatives de recentrage
        self.auto_recenter = False  # Flag pour recentrage automatique sans attente d'approbation
    
    def _find_line_detector_index(self):
        """Trouve l'index du détecteur de ligne dans le pipeline."""
        for i, det in enumerate(self.vision_pipeline.detectors):
            if getattr(det, 'name', '') == 'line':
                return i
        return None
    
    def _run_line_detection(self, frame):
        """Exécute la détection de ligne via le pipeline et retourne line_offset."""
        if self._line_detector_index is None:
            return None
        result = self.vision_pipeline.process_frame(frame.copy(), self._line_detector_index)
        if result is None:
            return None
        return result.get('line_offset')
        
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
        self.auto_recenter = False
        self.startup_grace_period = 15  # Réinitialiser la période de grâce au démarrage
        print("[STEP_MACHINE] Période de grâce: 15 frames (~0.75s) pour stabilisation caméra")
        
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
        self.frames_to_skip_after_rotation = 0
        self.startup_grace_period = 15
        self.auto_recenter = False
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
    
    def _should_use_pid_advance(self, error):
        """
        Détermine si le robot doit avancer avec correction PID.
        
        Args:
            error: Erreur de position par rapport à la ligne (offset)
        
        Returns:
            bool: True si l'erreur est faible et qu'on peut avancer avec PID
        """
        result = abs(error) <= self.low_error_threshold
        print("[STEP_MACHINE] _should_use_pid_advance: error={}, seuil={}, résultat={}".format(
            error, self.low_error_threshold, result))
        return result
        
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
        line_offset = self._run_line_detection(frame)
        
        # LOG DÉTAILLÉ pour diagnostic
        print("[STEP_MACHINE DEBUG] line_offset = {} (type: {})".format(
            line_offset, type(line_offset).__name__ if line_offset is not None else "NoneType"))
        
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
            print("[STEP_MACHINE WARNING] Ligne non détectée en WAITING_APPROVAL ({}/{} avant recherche)".format(
                self.line_lost_count, self.line_lost_threshold))
            # Passage immédiat en mode recherche après quelques frames perdues
            if self.line_lost_count >= 5:  # Seuil réduit à 5 frames (~0.25s) au lieu de 15
                print("[STEP_MACHINE] Ligne non détectée - Passage en mode RECENTER pour rotation")
                self._display_message("Recherche ligne...")
                # Passer en RECENTER automatique pour tourner sur place et retrouver la ligne
                self.state = StepState.RECENTER
                self.recenter_attempts = 0
                self.auto_recenter = True  # Mode automatique
                return {'state': self.state.name, 'line_offset': None, 'searching': True}
            # Si on n'a pas encore dépassé le seuil, continuer à chercher la ligne
            self._display_message("Recherche...")
            return {
                'state': self.state.name,
                'line_offset': None,
                'waiting_approval': True,
                'line_lost_count': self.line_lost_count,
                'step': self.step_count
            }
        else:
            self.line_lost_count = 0
            self.last_line_offset = line_offset
            print("[STEP_MACHINE] Ligne détectée avec offset={} en WAITING_APPROVAL".format(line_offset))
        
        # Attendre l'approbation
        if self.approved_to_move:
            print("[STEP_MACHINE] Début du mouvement (étape {})".format(self.step_count + 1))
            
            # Reset des compteurs de ligne perdue pour éviter une détection prématurée
            self.line_lost_count = 0
            
            # DÉCISION: Si l'offset est trop grand, aller à RECENTER pour s'aligner d'abord
            if abs(line_offset) > self.low_error_threshold:
                print("[STEP_MACHINE] Offset {} > seuil {} - Passage à RECENTER automatique pour alignement".format(
                    abs(line_offset), self.low_error_threshold))
                self._display_message("Alignement auto...")
                # NE PAS reset approved_to_move ici, on le passe à auto_recenter
                self.approved_to_move = False
                self.auto_recenter = True  # Activer le recentrage automatique
                self.state = StepState.RECENTER
                self.recenter_attempts = 0
                return {
                    'state': self.state.name,
                    'line_offset': line_offset,
                    'needs_recenter': True,
                    'auto_recenter': True,
                    'step': self.step_count
                }
            
            # Sinon, avancer normalement avec PID
            print("[STEP_MACHINE] Passage à MOVING - Avance avec ligne_offset={}".format(line_offset))
            self.approved_to_move = False  # Reset pour la prochaine fois
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
        """Gère l'état de mouvement - Avance tout droit sans PID."""
        # Détecter la ligne pour vérifier qu'elle est toujours visible
        line_offset = self._run_line_detection(frame)
        
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
            
            # Pas de valeur connue, arrêter
            self.robot.stop()
            self.state = StepState.WAITING_APPROVAL
            return {'state': self.state.name, 'line_offset': None}
        else:
            self.line_lost_count = 0
            self.last_line_offset = line_offset
        
        # Avancer tout droit à vitesse constante (sans PID)
        print("[STEP_MACHINE] Avance tout droit à vitesse {}px/s (offset détecté: {})".format(
            self.straight_speed, line_offset))
        self.robot.control_motors(self.straight_speed, self.straight_speed)
        
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
                'left_speed': self.straight_speed,
                'right_speed': self.straight_speed,
                'step_completed': True,
                'step': self.step_count
            }
        
        return {
            'state': self.state.name,
            'line_offset': line_offset,
            'left_speed': self.straight_speed,
            'right_speed': self.straight_speed,
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
        
        line_offset = self._run_line_detection(frame)
        
        print("[STEP_MACHINE] Résultat détection: line_offset={}".format(line_offset))
        
        if line_offset is not None:
            # Ligne retrouvée !
            print("[STEP_MACHINE] *** LIGNE RETROUVÉE *** offset={}".format(line_offset))
            self.robot.stop()
            self.line_lost_count = 0
            self.last_line_offset = line_offset
            
            # TOUJOURS se recentrer après avoir trouvé la ligne en mode recherche
            # pour garantir un bon alignement avant de continuer
            print("[STEP_MACHINE] Ligne trouvée avec offset={} - Passage à RECENTER automatique".format(line_offset))
            self._display_message("Alignement auto...")
            self.state = StepState.RECENTER
            self.recenter_attempts = 0
            # Marquer que c'est un recentrage automatique (pas d'attente d'approbation)
            self.auto_recenter = True
            return {
                'state': self.state.name,
                'line_found': True,
                'line_offset': line_offset,
                'auto_recenter': True
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
        Avance par pas de 10 cm en utilisant la régulation PID si l'erreur est faible.
        Attend l'approbation utilisateur avant d'avancer.
        """
        # Vérifier que la ligne est toujours visible
        line_offset = self._run_line_detection(frame)
        
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
        
        print("[STEP_MACHINE] APPROACH_LINE - offset={}, approbation={}".format(
            line_offset, self.approved_to_move))
        
        # Vérifier si l'erreur est faible (<= 10 pixels)
        if self._should_use_pid_advance(line_offset):
            # Erreur faible: avancer avec régulation PID (mode Rotation/Tuning)
            # Attendre l'approbation de l'utilisateur
            if not self.approved_to_move:
                self._display_message("Avancer {}cm (PID)? Appuyez".format(self.approach_distance_cm))
                return {
                    'state': self.state.name,
                    'waiting_approval': True,
                    'line_offset': line_offset,
                    'use_pid': True
                }
            
            # Reset de l'approbation
            self.approved_to_move = False
            
            print("[STEP_MACHINE] Approche avec PID - Erreur faible: {}px".format(line_offset))
            self._display_message("Avance {}cm PID...".format(self.approach_distance_cm))
            
            # Configurer le PID en mode avance (rotation_mode=False)
            self.pid_controller.update_params(rotation_mode=False)
            
            # Avancer avec correction PID pendant la durée définie
            start_time = time.time()
            while (time.time() - start_time) < self.approach_duration:
                # Capturer une nouvelle frame
                print("_handle_approach_line: Capture frame pour PID cycle d'approche")
                frame_current = self.vision_pipeline.get_last_frame()
                print("_handle_approach_line: after get_last_frame, frame_current: {}".format(len(frame_current) is None))
                line_offset_current = self._run_line_detection(frame_current)
                
                if line_offset_current is None:
                    # Ligne perdue, arrêter
                    print("[STEP_MACHINE] Ligne perdue pendant l'avance PID")
                    self.robot.stop()
                    break
                
                # Calculer les vitesses avec PID
                left_speed, right_speed = self.pid_controller.compute(line_offset_current)
                self.robot.control_motors(left_speed, right_speed)
                
                time.sleep(0.05)  # 20 Hz
            
            # Arrêter les moteurs
            self.robot.stop()
            time.sleep(0.3)  # Stabilisation
            
        else:
            # Erreur importante: passer d'abord par RECENTER
            print("[STEP_MACHINE] Offset trop grand ({}px) - Passage à RECENTER".format(line_offset))
            self._display_message("Recentrage...")
            self.state = StepState.RECENTER
            self.recenter_attempts = 0
            return {
                'state': self.state.name,
                'line_offset': line_offset,
                'needs_recenter': True
            }
        
        # Après avoir avancé, vérifier si la ligne est toujours visible
        print("[STEP_MACHINE] Vérification après approche...")
        frame_check = self.vision_pipeline.get_last_frame()
        
        line_offset_check = self._run_line_detection(frame_check)
        
        if line_offset_check is None:
            # Ligne perdue après approche
            print("[STEP_MACHINE] Ligne perdue après approche - Retour à SEARCH_SPIN")
            self._display_message("Ligne perdue!")
            self.state = StepState.SEARCH_SPIN
            self.search_attempts = 0
            return {
                'state': self.state.name,
                'line_lost_after_approach': True
            }
        
        # Ligne toujours visible, retourner à WAITING_APPROVAL pour continuer
        print("[STEP_MACHINE] Approche terminée - Retour à WAITING_APPROVAL")
        self._display_message("Approche OK!")
        time.sleep(0.3)
        self.state = StepState.WAITING_APPROVAL
        
        return {
            'state': self.state.name,
            'approach_completed': True,
            'distance_traveled_cm': self.approach_distance_cm,
            'line_offset': line_offset_check
        }
    
    def _handle_recenter(self, frame):
        """
        Gère l'état de recentrage sur la ligne.
        Utilise le PID en mode rotation pour aligner le robot avec la ligne de manière fluide.
        Si la ligne n'est pas visible, tourne lentement pour la retrouver.
        """
        # Vérifier que la ligne est visible
        line_offset = self._run_line_detection(frame)
        
        if line_offset is None:
            # Ligne non visible - tourner lentement pour la retrouver
            print("[STEP_MACHINE] Ligne non visible en RECENTER - Rotation lente pour recherche")
            
            # Vérifier si on a trop tourné
            if self.recenter_attempts >= self.max_recenter_attempts * 3:  # Plus de tentatives en mode recherche
                print("[STEP_MACHINE] Trop de tentatives sans trouver la ligne - Passage à SEARCH_SPIN")
                self._display_message("Ligne perdue!")
                # Remettre le PID en mode avance
                self.pid_controller.update_params(rotation_mode=False)
                self.state = StepState.SEARCH_SPIN
                self.search_attempts = 0
                return {
                    'state': self.state.name,
                    'line_lost_during_recenter': True
                }
            
            # Attendre l'approbation de l'utilisateur (sauf si auto_recenter)
            if not self.approved_to_move and not self.auto_recenter:
                self._display_message("Tourner? Appuyez")
                return {
                    'state': self.state.name,
                    'waiting_approval': True,
                    'line_offset': None,
                    'searching': True
                }
            
            # Reset de l'approbation
            self.approved_to_move = False
            self.recenter_attempts += 1
            
            print("[STEP_MACHINE] Rotation lente pour retrouver ligne (tentative {})".format(self.recenter_attempts))
            self._display_message("Tourne lent...")
            
            # Tourner lentement sur place (mode rotation PID avec offset simulé pour tourner)
            # Tourner à gauche de quelques degrés
            slow_rotation_speed = 8
            rotation_duration = 0.3  # 300ms de rotation lente
            
            self.robot.control_motors(-slow_rotation_speed, slow_rotation_speed)
            time.sleep(rotation_duration)
            self.robot.stop()
            time.sleep(0.2)  # Stabilisation
            
            # Rester en RECENTER pour vérifier au prochain cycle
            return {
                'state': self.state.name,
                'searching_line': True,
                'recenter_attempt': self.recenter_attempts
            }
        
        # Ligne visible - procéder au recentrage normal
        self.last_line_offset = line_offset
        
        # Vérifier si on est suffisamment centré
        if abs(line_offset) <= self.recenter_tolerance:
            print("[STEP_MACHINE] Robot bien centré (offset={}px) - Transition vers WAITING_APPROVAL".format(line_offset))
            self._display_message("Bien centre!")
            # Remettre le PID en mode avance
            self.pid_controller.update_params(rotation_mode=False)
            self.robot.stop()
            time.sleep(0.3)
            self.state = StepState.WAITING_APPROVAL
            self.recenter_attempts = 0
            self.auto_recenter = False  # Reset du flag auto
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
            # Remettre le PID en mode avance
            self.pid_controller.update_params(rotation_mode=False)
            self.robot.stop()
            time.sleep(0.3)
            self.state = StepState.WAITING_APPROVAL
            self.recenter_attempts = 0
            self.auto_recenter = False  # Reset du flag auto
            return {
                'state': self.state.name,
                'recenter_max_attempts': True,
                'line_offset': line_offset
            }
        
        # Attendre l'approbation de l'utilisateur (sauf si recentrage automatique)
        if not self.approved_to_move and not self.auto_recenter:
            self._display_message("Centrer? Appuyez")
            return {
                'state': self.state.name,
                'waiting_approval': True,
                'line_offset': line_offset
            }
        
        # Reset de l'approbation
        self.approved_to_move = False
        self.recenter_attempts += 1
        
        print("[STEP_MACHINE] Recentrage PID - Offset: {}px (tentative {}/{})".format(
            line_offset, self.recenter_attempts, self.max_recenter_attempts))
        
        self._display_message("Centrage PID...")
        
        # Activer le PID en mode rotation
        self.pid_controller.update_params(rotation_mode=True)
        
        # Effectuer UNE SEULE correction PID au lieu d'une boucle
        # La boucle while peut causer des problèmes car elle bloque le cycle normal
        left_speed, right_speed = self.pid_controller.compute(line_offset)
        print("[STEP_MACHINE] Correction PID: left={}, right={}".format(left_speed, right_speed))
        self.robot.control_motors(left_speed, right_speed)
        
        # Laisser le robot tourner un court instant
        time.sleep(0.1)
        self.robot.stop()
        
        # Rester dans l'état RECENTER pour vérifier le résultat au prochain cycle
        print("[STEP_MACHINE] Correction PID appliquée - Vérification au prochain cycle")
        
        return {
            'state': self.state.name,
            'recenter_attempt': self.recenter_attempts,
            'line_offset': line_offset,
            'correction_applied': True
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
    
    def _handle_line_lost(self, frame):
        """Gère l'état de ligne perdue définitivement."""
        print("[STEP_MACHINE] Ligne perdue - En attente d'intervention manuelle")
        self.robot.stop()
        
        # Vérifier quand même si la ligne réapparaît
        line_offset = self._run_line_detection(frame)
        
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
