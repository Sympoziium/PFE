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
    ├── (A mettre a jours avec la nouvelle arch)

Seul le mode actif a le droit d'envoyer des commandes moteur.
"""

import threading
import time
from core.control.IO_drivers.sensor_state import SensorState
from core.control.IO_drivers.motor_command import MotorCommand, CommandType
from core.control.IO_drivers.sensor_driver import SensorDriver
from core.control.IO_drivers.motor_driver import MotorDriver
from core.control.controlers.manual_controller import ManualController

class ControlManager:
    """
    Orchestrateur de contrôle du robot.

    Usage typique (dans main.py) ::

        ctrl_mgr = ControlManager(robot, vision_pipeline)
        ctrl_mgr.register_controller(pid_controller)
        ctrl_mgr.start()            # lance la boucle de contrôle
        ...
    """

    def __init__(self, robot, vision_pipeline):
        """
        Args:
            robot:            Instance de RobotBase (ex. RobotZumi).
            vision_pipeline:  Instance de VisionPipeline.
        """
        self.robot = robot
        self.vp = vision_pipeline

        # Contrôleurs enregistrés
        self._controllers = {}  # dict de tous les contrôleurs

        # Contrôleur actif (et instance de drivers)
        self._active_controller = None      # ControllerBase instance
        self._sensor_driver = None          # SensorDriver
        self._motor_driver = None           # MotorDriver

        # Boucle de contrôle
        self._thread = None
        self._running = False
        self._loop_delay = 0.05 # férquence de tic limité a 20Hz

        # Données partagées (mises à jour par la boucle, lues par le serveur)
        self._data_lock = threading.Lock()
        self.last_sensor_data = SensorState()
        self.last_motor_command = MotorCommand(CommandType.STOP, 0, 0)
        
        self.last_left_speed = 0 # voir si on garde
        self.last_right_speed = 0
        
        # Callbacks pour l'échantillonnage par le serveur
        # Signature: fn(state: SensorState, command: MotorCommand) -> None
        self._sampling_callback = None

        # Override manuel temporaire (WASD pendant qu'un contrôleur auto est actif)
        # Permet de corriger manuellement sans changer le contrôleur actif.
        self._override_command = None       # MotorCommand ou None
        self._override_time = 0.0           # Timestamp de la dernière commande override
        self._override_timeout = 0.3        # Timeout watchdog (secondes)

        self._init_new_arch_drivers() # Initialise les drivers de la nouvelle architecture (SensorDriver et MotorDriver)
        self._init_robot_sensors() # Initialise les capteurs du robot (MPU, IR, batterie) au demarrage du manager

    # ------------------------------------------------------------------
    #  Enregistrement des contrôleurs
    # ------------------------------------------------------------------
    def register_controller(self, name, controller):
        """Enregistre un contrôleur avec un nom unique."""
        if name in self._controllers:
            raise ValueError(f"Contrôleur '{name}' déjà enregistré.")
        self._controllers[name] = controller

    # ------------------------------------------------------------------
    #  Accès aux contrôleurs
    # ------------------------------------------------------------------
    def get_controller(self, name):
        """Retourne le contrôleur enregistré sous le nom donné."""
        return self._controllers.get(name)
    
    def activate_controller(self, name):
        """Active le contrôleur enregistré sous le nom donné."""
        if name not in self._controllers:
            raise ValueError(f"Contrôleur '{name}' non trouvé.")    
        
        # Arrêter le contrôleur précédent s'il y en avait un
        if self._active_controller:
            self._active_controller.stop()
            
        self._active_controller = self._controllers[name]
        self._active_controller.start()  # On laisse le contrôleur s'initialiser
        self.vp.start_passive_detection() # On démarre la détection passive
        self._start_loop()

    def deactivate_controller(self):
        """Désactive le contrôleur actif (retour à IDLE) et arrête les moteurs."""
        if self._active_controller:
            self._active_controller.stop()
            
        self._active_controller = None
        self._stop_loop()
        self.vp.stop_passive_detection()
        
        # SÉCURITÉ : Forcer l'arrêt du robot physiquement quand aucun contrôleur n'est actif
        if self._motor_driver:
            self._motor_driver.execute(MotorCommand.stop())

    # ------------------------------------------------------------------
    #  Override manuel temporaire (WASD pendant contrôleur auto)
    # ------------------------------------------------------------------
    def set_manual_override(self, command):
        """Injecte une commande moteur temporaire sans changer le contrôleur actif.

        Le contrôleur actif (PID, etc.) reste en place mais ses commandes sont
        ignorées tant que l'override est alimenté. Quand l'override expire
        (watchdog timeout), le contrôleur reprend automatiquement.

        Args:
            command: MotorCommand à envoyer aux moteurs.
        """
        self._override_command = command
        self._override_time = time.time()

    def clear_manual_override(self):
        """Annule l'override manuel. Le contrôleur actif reprend immédiatement."""
        self._override_command = None

    @property
    def manual_override_active(self):
        """True si un override manuel est en cours (non expiré)."""
        if self._override_command is None:
            return False
        return (time.time() - self._override_time) <= self._override_timeout

    def set_loop_delay(self, delay_sec):
        """Modifier le délai de la boucle de contrôle (delay en secondes)"""
        with self._data_lock:
            self._loop_delay = delay_sec

    # ------------------------------------------------------------------
    #  Callback de sampling (appelé à chaque tick de la boucle)
    # ------------------------------------------------------------------
    def set_sampling_callback(self, callback):
        """
        Enregistre un callback appelé à chaque tick de la boucle de contrôle,
        immédiatement après step() et avant execute().

        Args:
            callback: Fonction avec signature fn(state: SensorState, command: MotorCommand) -> None
        """
        self._sampling_callback = callback

    def clear_sampling_callback(self):
        """Désactive le callback de sampling."""
        self._sampling_callback = None


    # ------------------------------------------------------------------
    #  Démarrage des capteurs
    # ------------------------------------------------------------------
    def _init_new_arch_drivers(self):
        """Initialise (une seule fois) SensorDriver et MotorDriver."""
        if self._sensor_driver is None:
            self._sensor_driver = SensorDriver(self.vp, self.robot)
            self._motor_driver = MotorDriver(self.robot)

    def _init_robot_sensors(self):
        """Lecture initiale des capteurs pour remplir last_sensor_data.
        La calibration MPU/gyro est faite dans robot.__init__(), pas ici."""
        self.update_sensors()

    # ------------------------------------------------------------------
    #  Mise à jours des capteurs
    # ------------------------------------------------------------------
    def update_sensors(self):
        """Met à jour les données des capteurs du robot (MPU, IR, batterie).

        La détection de ligne par caméra est active pour tous les contrôleurs
        car le MLP utilise le line_offset comme feature d'entrée.
        """
        if self._sensor_driver is not None:
            state = self._sensor_driver.read(Line_detection=True)
            with self._data_lock:
                self.last_sensor_data = state
    
    def get_last_sensor_data(self):
        with self._data_lock:
            # On retourne la référence (update_sensors recrée un objet SensorState neuf à chaque tick)
            return self.last_sensor_data
    # ------------------------------------------------------------------
    #  Réinitialisation des capteurs
    # ------------------------------------------------------------------
    def _reset_robot_drive_state(self):
        """Réinitialise les capteurs du robot"""
        self.robot.reset_drive_state()  # réinitialise les PID et le Gyro

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

    def _control_loop(self):
        """
        Boucle de contrôle.

        Tourne uniquement tant qu'un mode est actif (``_running == True``).
        Quand le mode retombe en IDLE, la boucle se termine d'elle-même.
        """
        print("[ControlManager] Boucle de contrôle démarrée.")
        while self._running:
            try:
                # sortie de la boucle si le contrôleur est désactivé (sortie pour l'onglet contrôle)
                if self._active_controller is None:
                    break

                # Mise à jours des lectures capteurs
                self.update_sensors()

                # Exécution d'un cycle du contrôleur actif
                state, command = self._tick_controller()

                # Exécution du callback de sampling (après step, avant execute)
                if self._sampling_callback is not None and state is not None and command is not None:
                    try:
                        self._sampling_callback(state, command)
                    except Exception as e:
                        print("[ControlManager] Erreur dans le callback de sampling: {}".format(e))

                # Délai adaptatif selon le contrôleur actif:
                # - Manuel: 33ms (30 Hz) - tick léger, peut aller plus vite pour une meilleure réactivité aux commandes web
                # - ML/autres: 50ms (20 Hz) - marge pour inférence TFLite
                if isinstance(self._active_controller, ManualController):
                    time.sleep(0.033)
                else:
                    time.sleep(self._loop_delay)

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
    def _tick_controller(self):
        """
        Un cycle du contrôleur ControllerBase actif (mode ``controller``).

        Returns:
            tuple: (state, command) pour permettre le sampling synchronisé
        """
        if self._active_controller is None:
            print("ERREUR CTRL MANAGER : aucun contrôleur actif la boucle tic quand même")
            return None, None
        elif self._sensor_driver is None:
            print("ERREUR CTRL MANAGER : le driver des sensors n'a pas été initialisé et la boucle tic quand même")
            return None, None
        elif self._motor_driver is None:
            print("ERREUR CTRL MANAGER : le driver des moteurs n'a pas été initialisé et la boucle tic quand même")
            return None, None

        state = self.get_last_sensor_data()

        # Override manuel : si actif et non expiré, envoyer la commande override
        # au lieu de celle du contrôleur. Le contrôleur reste actif (état PID préservé).
        if self.manual_override_active:
            command = self._override_command
            self._motor_driver.execute(command)
            with self._data_lock:
                self.last_left_speed = command.left_speed
                self.last_right_speed = command.right_speed
                self.last_motor_command = command
            # Logger l'override dans le debug du contrôleur actif
            ctrl = self._active_controller
            if hasattr(ctrl, '_debug_enabled') and ctrl._debug_enabled:
                ctrl._debug_log.append({
                    'tick': getattr(ctrl, '_inference_count', 0),
                    'override': True,
                    'command': [command.left_speed, command.right_speed],
                })
            return state, command

        # Si l'override vient d'expirer, nettoyer
        if self._override_command is not None:
            self._override_command = None

        command = self._active_controller.step(state)
        self._motor_driver.execute(command)
        with self._data_lock: # récupération des commandes de vitesses aux roues
            self.last_left_speed = command.left_speed
            self.last_right_speed = command.right_speed
            self.last_motor_command = command

        return state, command

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    def get_status(self):
        """
        Retourne un dict résumant l'état courant du contrôle.

        Utile pour les routes HTTP de monitoring.
        """
        with self._data_lock:
            data = {
                'running': self._running,
                'last_sensor_data': self.get_last_sensor_data(),
                'left_speed': self.last_left_speed,
                'right_speed': self.last_right_speed,
            }

        # Infos spécifiques au contrôleur actif
        if self._running and self._active_controller:
            data['controller_name'] = self._active_controller.name
            data['controller_debug'] = self._active_controller.get_debug_info()
            data['controller_params'] = self._active_controller.get_params()

        return data
