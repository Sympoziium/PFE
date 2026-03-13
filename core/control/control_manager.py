#!/usr/bin/env python
# -*- coding: utf-8 -*-
# control_manager.py
# ------------------
"""
Orchestrateur de contrôle du robot.

Responsabilités :
- Gère la boucle de contrôle principale (vision -> détection -> action moteur).
- Maintient un registre de contrôleurs dédiés (PID ligne, state machines, etc.).
- S'assure qu'un seul mode de contrôle pilote les moteurs à la fois.
- Expose une API interne utilisée par le serveur web (server_controller).

Architecture :
    ControlManager (orchestrateur)
    ├── PIDController               (asservissement PID)
    ├── LineFollowingStateMachine    (séquence arrêt/photo/rotation)
    └── StepByStepStateMachine      (mode pas-à-pas avancé)

Seul le mode actif a le droit d'envoyer des commandes moteur.
"""

import threading
import time


# ---------------------------------------------------------------------------
#  Constantes – modes de contrôle
# ---------------------------------------------------------------------------

MODE_IDLE = 'idle'
MODE_PID = 'pid'
MODE_STATE_MACHINE = 'state_machine'
MODE_STEP_BY_STEP = 'step_by_step'


class ControlManager:
    """
    Orchestrateur de contrôle du robot.

    Usage typique (dans main.py) ::

        ctrl_mgr = ControlManager(robot, vision_pipeline)
        ctrl_mgr.register_pid(pid_controller)
        ctrl_mgr.register_state_machine(state_machine)
        ctrl_mgr.start()            # lance la boucle de contrôle
        ...
        ctrl_mgr.activate(MODE_PID)  # active le suivi PID
    """

    def __init__(self, robot, vision_pipeline):
        """
        Args:
            robot:            Instance de RobotBase (ex. RobotZumi).
            vision_pipeline:  Instance de VisionPipeline.
        """
        self.robot = robot
        self.vision_pipeline = vision_pipeline

        # Mode de contrôle actif
        self._mode = MODE_IDLE
        self._mode_lock = threading.Lock()

        # Contrôleurs enregistrés
        self._pid_controller = None
        self._state_machine = None          # LineFollowingStateMachine
        self._step_machine = None           # StepByStepStateMachine
        self._line_detector = None          # Référence au détecteur de ligne

        # Boucle de contrôle
        self._thread = None
        self._running = False

        # Données partagées (mises à jour par la boucle, lues par le serveur)
        self._data_lock = threading.Lock()
        self.last_line_offset = None
        self.last_correction = 0
        self.last_left_speed = 0
        self.last_right_speed = 0

    # ------------------------------------------------------------------
    #  Enregistrement des contrôleurs
    # ------------------------------------------------------------------

    def register_pid(self, pid_controller):
        """Enregistre le contrôleur PID partagé."""
        self._pid_controller = pid_controller

    def register_state_machine(self, state_machine):
        """Enregistre la machine à états de suivi de ligne (arrêt/photo/rotation)."""
        self._state_machine = state_machine

    def register_step_machine(self, step_machine):
        """Enregistre la machine à états pas-à-pas."""
        self._step_machine = step_machine

    def register_line_detector(self, line_detector):
        """Enregistre la référence au détecteur de ligne (pour l'offset)."""
        self._line_detector = line_detector

    # ------------------------------------------------------------------
    #  Accès aux contrôleurs
    # ------------------------------------------------------------------

    @property
    def pid_controller(self):
        return self._pid_controller

    @property
    def state_machine(self):
        return self._state_machine

    @property
    def step_machine(self):
        return self._step_machine

    @property
    def mode(self):
        with self._mode_lock:
            return self._mode

    # ------------------------------------------------------------------
    #  Démarrage de la vision (sans boucle de contrôle)
    # ------------------------------------------------------------------

    def start_vision(self):
        """Démarre le pipeline de vision (caméra) sans lancer la boucle de contrôle.

        La boucle de contrôle ne démarre que via ``activate(mode)`` et
        s'arrête automatiquement via ``deactivate()``.  Cela évite de
        consommer du CPU tant qu'aucun mode n'est actif.
        """
        self.vision_pipeline.start()

    # ------------------------------------------------------------------
    #  Boucle de contrôle (démarre/s'arrête avec activate/deactivate)
    # ------------------------------------------------------------------

    def _start_loop(self):
        """Démarre le thread de la boucle de contrôle (usage interne)."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._control_loop, name="ControlLoop", daemon=True)
        self._thread.start()

    def _stop_loop(self):
        """Arrête le thread de la boucle de contrôle (usage interne)."""
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

    def stop(self):
        """Arrête tout : boucle de contrôle + modes actifs."""
        self.deactivate()
        self._stop_loop()

    def _control_loop(self):
        """
        Boucle de contrôle.

        Tourne uniquement tant qu'un mode est actif (``_running == True``).
        Quand le mode retombe en IDLE, la boucle se termine d'elle-même.
        """
        print("[ControlManager] Boucle de contrôle démarrée.")
        while self._running:
            try:
                current_mode = self.mode

                # Si on retombe en IDLE, la boucle n'a plus de raison de tourner
                if current_mode == MODE_IDLE:
                    break

                # --- Lecture du buffer partagé (sans capturer la caméra) ---
                # La capture est déjà faite par video_feed() qui alimente le buffer.
                frame = self.vision_pipeline.get_last_frame()
                if frame is None:
                    time.sleep(0.03)
                    continue

                # Pour MODE_PID : détecter la ligne depuis le buffer et stocker l'offset
                line_val = None
                if current_mode == MODE_PID:
                    line_val = self._detect_line_from_frame(frame)
                    with self._data_lock:
                        self.last_line_offset = line_val
                    # Rétro-compatibilité : le pid_loop du server_controller lit cet attribut
                    self.vision_pipeline.last_line_offset = line_val

                # --- Dispatch du mode actif ---
                if current_mode == MODE_PID:
                    self._tick_pid(line_val)

                elif current_mode == MODE_STATE_MACHINE:
                    self._tick_state_machine()

                elif current_mode == MODE_STEP_BY_STEP:
                    self._tick_step_machine()

            except Exception as e:
                print("[ControlManager] Erreur dans la boucle de contrôle: {}".format(e))
                import traceback
                traceback.print_exc()
                time.sleep(0.1)

        self._running = False
        self._thread = None
        print("[ControlManager] Boucle de contrôle arrêtée.")

    # ------------------------------------------------------------------
    #  Tick – exécution d'un cycle pour chaque mode
    # ------------------------------------------------------------------

    def _tick_pid(self, line_offset):
        """Un cycle de contrôle PID direct (mode ``pid``)."""
        if self._pid_controller is None:
            return

        if line_offset is None:
            self.robot.stop()
            return

        if self._pid_controller.rotation_mode:
            # Mode rotation : calcule un angle et appelle turn()
            angle = self._pid_controller.compute_rotation_angle(line_offset)
            if angle is not None:
                self.robot.turn(angle)
                with self._data_lock:
                    self.last_correction = angle
                    self.last_left_speed = 0
                    self.last_right_speed = 0
            else:
                self.robot.stop()
                with self._data_lock:
                    self.last_correction = 0
                    self.last_left_speed = 0
                    self.last_right_speed = 0
            time.sleep(0.15)
        else:
            # Mode avance : calcule les vitesses gauche/droite
            left, right = self._pid_controller.compute(line_offset)
            self.robot.control_motors(left, right)
            with self._data_lock:
                hist = self._pid_controller.correction_history
                self.last_correction = hist[-1] if hist else 0
                self.last_left_speed = left
                self.last_right_speed = right
            time.sleep(0.05)

    def _tick_state_machine(self):
        """Un cycle de la machine à états de suivi de ligne."""
        if self._state_machine is None or not self._state_machine.is_running():
            return

        # Lire depuis le buffer partagé (peuplé par video_feed)
        frame = self.vision_pipeline.get_last_frame()
        if frame is None:
            return

        state_info = self._state_machine.step(frame)
        if state_info.get('state') == 'COMPLETED':
            print("[ControlManager] Séquence LineFollowing terminée.")
            with self._mode_lock:
                self._mode = MODE_IDLE

    def _tick_step_machine(self):
        """Un cycle de la machine à états pas-à-pas."""
        if self._step_machine is None or not self._step_machine.is_running():
            return

        # Lire depuis le buffer partagé (peuplé par video_feed)
        frame = self.vision_pipeline.get_last_frame()
        if frame is None:
            return

        result = self._step_machine.step(frame)

        with self._data_lock:
            self.last_line_offset = result.get('line_offset', self.last_line_offset)
            self.last_left_speed = result.get('left_speed', 0)
            self.last_right_speed = result.get('right_speed', 0)

    def _detect_line_from_frame(self, frame):
        """Extrait l'offset de ligne depuis une frame pré-capturée (sans appel caméra).
        
        Cherche le premier détecteur nommé 'line' dans le pipeline et appelle
        process_frame() avec la frame fournie.
        """
        for i, det in enumerate(self.vision_pipeline.detectors):
            if getattr(det, 'name', '') == 'line':
                try:
                    result = self.vision_pipeline.process_frame(frame.copy(), i)
                    if result:
                        return result.get('line_offset')
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------
    #  Activation / désactivation des modes
    # ------------------------------------------------------------------

    def activate(self, mode):
        """
        Active un mode de contrôle.

        Si un autre mode est déjà actif, il est d'abord désactivé proprement.

        Args:
            mode: Une des constantes MODE_* (str).

        Raises:
            ValueError: Si le mode demandé nécessite un contrôleur non enregistré.
        """
        if mode == self.mode:
            return

        # Vérifications
        if mode == MODE_PID and self._pid_controller is None:
            raise ValueError("Aucun PIDController enregistré.")
        if mode == MODE_STATE_MACHINE and self._state_machine is None:
            raise ValueError("Aucune LineFollowingStateMachine enregistrée.")
        if mode == MODE_STEP_BY_STEP:
            if self._step_machine is None:
                self._create_step_machine()

        # Désactiver le mode courant (arrête la boucle si elle tourne)
        self.deactivate()

        # Activer le nouveau mode
        with self._mode_lock:
            self._mode = mode

        if mode == MODE_PID:
            self._pid_controller.reset()
            print("[ControlManager] Mode PID activé ({})".format(
                "rotation" if self._pid_controller.rotation_mode else "avance"))

        elif mode == MODE_STATE_MACHINE:
            self._state_machine.start()
            print("[ControlManager] Mode LineFollowingStateMachine activé.")

        elif mode == MODE_STEP_BY_STEP:
            self._step_machine.start()
            print("[ControlManager] Mode StepByStep activé.")

        # Lancer la boucle de contrôle (si pas déjà en cours)
        self._start_loop()

    def deactivate(self):
        """Désactive le mode courant, arrête la boucle de contrôle et les moteurs."""
        with self._mode_lock:
            prev_mode = self._mode
            self._mode = MODE_IDLE

        if prev_mode == MODE_PID:
            pass  # Pas d'état interne à nettoyer

        elif prev_mode == MODE_STATE_MACHINE:
            if self._state_machine and self._state_machine.is_running():
                self._state_machine.stop()

        elif prev_mode == MODE_STEP_BY_STEP:
            if self._step_machine and self._step_machine.is_running():
                self._step_machine.stop()

        # Arrêter la boucle de contrôle (le thread se termine car mode == IDLE)
        self._stop_loop()

        self.robot.stop()

        with self._data_lock:
            self.last_correction = 0
            self.last_left_speed = 0
            self.last_right_speed = 0

        if prev_mode != MODE_IDLE:
            print("[ControlManager] Mode '{}' désactivé.".format(prev_mode))

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def _create_step_machine(self):
        """Crée la StepByStepStateMachine à la demande."""
        from core.control.line_following_state_machine import StepByStepStateMachine

        self._step_machine = StepByStepStateMachine(
            robot=self.robot,
            vision_pipeline=self.vision_pipeline,
            pid_controller=self._pid_controller,
        )

    def get_status(self):
        """
        Retourne un dict résumant l'état courant du contrôle.

        Utile pour les routes HTTP de monitoring.
        """
        with self._data_lock:
            data = {
                'mode': self.mode,
                'running': self._running,
                'line_offset': self.last_line_offset,
                'correction': self.last_correction,
                'left_speed': self.last_left_speed,
                'right_speed': self.last_right_speed,
            }

        # Infos spécifiques au mode actif
        if self.mode == MODE_PID and self._pid_controller:
            data['pid_params'] = self._pid_controller.get_params()
            data['pid_debug'] = self._pid_controller.get_debug_info()

        elif self.mode == MODE_STATE_MACHINE and self._state_machine:
            data['state'] = self._state_machine.get_state().name
            data['photos_taken'] = len(self._state_machine.photos_taken)
            data['rotation_count'] = self._state_machine.rotation_count

        elif self.mode == MODE_STEP_BY_STEP and self._step_machine:
            data['state'] = self._step_machine.get_state().name
            data['step_count'] = self._step_machine.step_count
            data['waiting_approval'] = self._step_machine.is_waiting_approval()

        return data
