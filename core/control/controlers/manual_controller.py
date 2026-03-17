#!/usr/bin/env python
# -*- coding: utf-8 -*-
# manual_controller.py
# ------------------
"""Contrôleur manuel pour le pilotage via l'interface web (touches directionnelles).
    
    Il écoute les intentions de mouvement envoyées par Flask et les transforme 
    en MotorCommand. Il intègre également son propre Watchdog : si aucune commande 
    n'est reçue pendant X ms, il arrête les moteurs.
"""

import time
from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.motor_command import MotorCommand

class ManualController(ControllerBase):
    def __init__(self, default_speed=30, watchdog_timeout=0.6):
        self._name = "manual_controller"
        self.default_speed = default_speed
        self.watchdog_timeout = watchdog_timeout

        # Contrôle PWM logiciel pour réduire la vitesse des virages
        self._turn_tick = 0
        self.turn_duty_on  = 1   # ticks actifs  (configurable depuis l'interface)
        self.turn_duty_off = 1   # ticks inactifs → vitesse effective ÷ 2
        
        self._current_action = "stop"
        self._last_action_time = time.time()

    @property
    def name(self):
        return self._name
    
    def set_action(self, action, speed=None):
        """Met à jour l'intention de mouvement depuis le serveur web."""
        self._current_action = action
        self._last_action_time = time.time()
        if speed is not None:
            self.default_speed = speed

    def start(self):
        """Appelé quand l'utilisateur prend le contrôle manuel."""
        self._current_action = "stop"
        self._last_action_time = time.time()

    def stop(self):
        self._current_action = "stop"

    def step(self, state):
        """Calcule la commande en fonction de la dernière action web reçue."""
        
        # 1. Vérification du Watchdog (déconnexion ou arrêt d'appui de touche)
        if time.time() - self._last_action_time > self.watchdog_timeout:
            self._current_action = "stop"

        # Contrôle PWM logiciel pour les virages : on n'envoie la commande de virage que turn_duty_on tick sur turn_duty_on + turn_duty_off, pour réduire la vitesse effective.
        if self._current_action in ("left", "right"):
            self._turn_tick += 1
            active = (self._turn_tick % (self.turn_duty_on + self.turn_duty_off)) < self.turn_duty_on
            if not active:
                return MotorCommand.stop()

        # 2. Traduction de l'action en MotorCommand
        if self._current_action == "stop":
            return MotorCommand.stop()
            
        elif self._current_action == "forward":
            # Contrôle manuel direct des moteurs, sans correction de cap.
            return MotorCommand.make_speed(self.default_speed, self.default_speed)
            
        elif self._current_action == "reverse":
            return MotorCommand.make_speed(-self.default_speed, -self.default_speed)
            
        elif self._current_action == "left":
            # Tourner sur place par friction (différentielle pure)
            return MotorCommand.make_speed(-self.default_speed, self.default_speed)
            
        elif self._current_action == "right":
            return MotorCommand.make_speed(self.default_speed, -self.default_speed)
            
        return MotorCommand.stop()

    def get_debug_info(self):
        return {
            "current_action": self._current_action,
            "timeout_warning": (time.time() - self._last_action_time > self.watchdog_timeout)
        }

    def get_params(self):
        return {"default_speed": self.default_speed, "turn_duty_on": self.turn_duty_on, "turn_duty_off": self.turn_duty_off}

    def update_params(self, **kwargs):
        if "default_speed" in kwargs:
            self.default_speed = kwargs["default_speed"]