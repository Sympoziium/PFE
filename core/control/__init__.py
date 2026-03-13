#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Module de contrôle du robot.

Centralise la logique d'orchestration entre la vision, les contrôleurs PID
et les machines à états. Le serveur web (interface/) délègue les actions
de contrôle à ce module plutôt que de les implémenter directement.
"""

from core.control.control_manager import ControlManager

__all__ = ['ControlManager']
