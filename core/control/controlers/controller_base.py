#!/usr/bin/env python
# -*- coding: utf-8 -*-
# controller_base.py
# ------------------
"""Interface abstraite pour un contrôleur de robot.

Tout contrôleur (PID suivi de ligne, MLP, state machine, …) doit hériter
de cette classe et implémenter au minimum `name` et `step()`.

Le ControlManager utilise cette interface pour traiter tous les contrôleurs
de façon polymorphe : il appelle ``step(state)`` et reçoit un ``MotorCommand``.
"""

from abc import ABC, abstractmethod

from core.control.IO_drivers.sensor_state import SensorState
from core.control.IO_drivers.motor_command import MotorCommand


class ControllerBase(ABC):
    """Classe de base abstraite pour tous les contrôleurs du robot.

    Contrat minimal :
        - ``name``  : propriété retournant un identifiant unique (str).
        - ``step()`` : reçoit un `SensorState`, retourne un `MotorCommand`.

    Méthodes optionnelles (override si nécessaire) :
        - ``start()``         : appelé à l'activation du contrôleur.
        - ``stop()``          : appelé à la désactivation.
        - ``get_debug_info()`` : données de monitoring pour l'UI.
        - ``get_params()``    : paramètres réglables.
        - ``update_params()`` : mise à jour des paramètres en runtime.
    """

    @property
    @abstractmethod
    def name(self):
        """str : Nom unique identifiant ce contrôleur (ex: 'pid_line', 'ml_imitation')."""

    @abstractmethod
    def step(self, state):
        """Calcule la prochaine commande moteur à partir de l'état capteur.

        Args:
            state (SensorState): État courant des capteurs du robot.

        Returns:
            MotorCommand: Commande moteur à exécuter.
        """

    # ------------------------------------------------------------------
    #  Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Appelé quand ce contrôleur devient le contrôleur actif.

        Utiliser pour réinitialiser l'état interne (PID, historique, etc.).
        """

    def stop(self):
        """Appelé quand ce contrôleur est désactivé.

        Utiliser pour libérer des ressources si nécessaire.
        """

    # ------------------------------------------------------------------
    #  Monitoring & configuration
    # ------------------------------------------------------------------

    def get_debug_info(self):
        """Retourne un dict de données de monitoring pour l'interface opérateur.

        Returns:
            dict: Données de debug (erreurs récentes, état interne, etc.).
        """
        return {}

    def get_params(self):
        """Retourne un dict des paramètres réglables de ce contrôleur.

        Returns:
            dict: Paramètres actuels (ex: kp, ki, kd, base_speed, …).
        """
        return {}

    def update_params(self, **kwargs):
        """Met à jour les paramètres du contrôleur en runtime.

        Args:
            **kwargs: Paramètres à mettre à jour (clés = noms des paramètres).
        """