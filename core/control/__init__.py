#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module de contrôle du robot.

Centralise la logique d'orchestration entre la vision, les contrôleurs
et les drivers moteur/capteur. Le serveur web (interface/) délègue les
actions de contrôle à ce module plutôt que de les implémenter directement.

Architecture :
    ControlManager (orchestrateur pluggable)
    ├── SensorDriver  → SensorState (entrées standardisées)
    ├── MotorDriver   → MotorCommand (sorties standardisées)
    └── ControllerBase (ABC)
        ├── PIDLineFollowerController
        ├── MLController (futur)
        └── ... (extensible)
"""

from core.control.control_manager import ControlManager
from core.control.controlers.controller_base import ControllerBase
from core.control.IO_drivers.sensor_state import SensorState
from core.control.IO_drivers.motor_command import MotorCommand, CommandType
from core.control.IO_drivers.sensor_driver import SensorDriver
from core.control.IO_drivers.motor_driver import MotorDriver
from core.control.legacy.pid_line_follower import PIDLineFollowerController
from core.control.legacy.line_follower_controller import LineFollowerController
from core.control.controlers.circuit_fsm_controller import CircuitFSMController

__all__ = [
    'ControlManager',
    'ControllerBase',
    'SensorState',
    'MotorCommand',
    'CommandType',
    'SensorDriver',
    'MotorDriver',
    'PIDLineFollowerController',
    'LineFollowerController',
    'CircuitFSMController',
]
