#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pid_controller.py
# ------------------
"""Contrôleur PID pour l'asservissement du suivi de ligne.

Le contrôleur PID calcule la correction à appliquer aux moteurs
en fonction de l'erreur de position de la ligne détectée.
"""

import time

class PIDController:
    def __init__(self, kp=0.1, ki=0.0, kd=0.05, base_speed=20, max_correction=30, 
             rotation_mode=True, deadband=5, rotation_scale=0.3):
        """
        Initialise le contrôleur PID.
        
        Args:
            kp (float): Gain proportionnel
            ki (float): Gain intégral
            kd (float): Gain dérivé
            base_speed (int): Vitesse de base des moteurs (0-100)
            max_correction (int): Correction maximale applicable
            rotation_mode (bool): Si True, tourne sur place. Si False, avance en suivant la ligne.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.base_speed = base_speed
        self.max_correction = max_correction
        self.rotation_mode = rotation_mode
        self.deadband = deadband
        self.rotation_scale = rotation_scale
        
        # Variables internes
        self.previous_error = 0
        self.integral = 0
        self.last_time = None
        
        # Historique pour debug
        self.error_history = []
        self.correction_history = []
        
    def reset(self):
        """Réinitialise l'état du PID."""
        self.previous_error = 0
        self.integral = 0
        self.last_time = None
        self.error_history = []
        self.correction_history = []
        
    def update_params(self, kp=None, ki=None, kd=None, base_speed=None, max_correction=None, rotation_mode=None):
        """Met à jour les paramètres du PID."""
        if kp is not None:
            self.kp = kp
        if ki is not None:
            self.ki = ki
        if kd is not None:
            self.kd = kd
        if base_speed is not None:
            self.base_speed = base_speed
        if max_correction is not None:
            self.max_correction = max_correction
        if rotation_mode is not None:  # NOUVEAU
            self.rotation_mode = rotation_mode
            
    def get_params(self):
        """Retourne les paramètres actuels du PID."""
        return {
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd,
            'base_speed': self.base_speed,
            'max_correction': self.max_correction,
            'rotation_mode': self.rotation_mode  # NOUVEAU
        }
        
    def compute(self, error):
        """
        Calcule la correction PID basée sur l'erreur.
        
        Args:
            error (float): Erreur de position (offset de la ligne)
                          Négatif = ligne à gauche, Positif = ligne à droite
        
        Returns:
            tuple: (left_speed, right_speed) vitesses des moteurs
        """
        current_time = time.time()
        
        # Calculer dt (delta time)
        if self.last_time is None:
            dt = 0.05  # Valeur par défaut pour la première itération
        else:
            dt = current_time - self.last_time
            if dt <= 0:
                dt = 0.05
                
        self.last_time = current_time
        
        # Terme proportionnel
        P = self.kp * error
        
        # Terme intégral (avec anti-windup)
        self.integral += error * dt
        # Limiter l'intégrale pour éviter le windup
        max_integral = self.max_correction / (self.ki if self.ki != 0 else 1)
        self.integral = max(-max_integral, min(max_integral, self.integral))
        I = self.ki * self.integral
        
        # Terme dérivé
        derivative = (error - self.previous_error) / dt if dt > 0 else 0
        D = self.kd * derivative
        
        # Calcul de la correction totale
        correction = P + I + D
        
        # Limiter la correction
        correction = max(-self.max_correction, min(self.max_correction, correction))
        
        # ===== CHANGEMENT ICI: Mode rotation vs mode avance =====
        if self.rotation_mode:
            # MODE ROTATION: Tourne sur place pour centrer la ligne
            # Ajouter une zone morte pour éviter les micro-mouvements
            DEADBAND = 5  # Ne bouge pas si l'erreur est inférieure à 5 pixels
            ROTATION_SCALE = 0.3  # Réduit la vitesse à 30% en mode rotation
            
            if abs(error) < self.deadband:
                left_speed = 0
                right_speed = 0
            else:
                left_speed = correction * self.rotation_scale
                right_speed = -correction * self.rotation_scale
        else:
            # MODE AVANCE: Avance en suivant la ligne
            # Si erreur positive (ligne à droite): ralentir roue droite, accélérer roue gauche
            # Si erreur négative (ligne à gauche): ralentir roue gauche, accélérer roue droite
            left_speed = self.base_speed + correction
            right_speed = self.base_speed - correction
        
        # Limiter les vitesses entre -100 et 100
        left_speed = max(-100, min(100, left_speed))
        right_speed = max(-100, min(100, right_speed))
        
        # Sauvegarder pour la prochaine itération
        self.previous_error = error
        
        # Historique (garder les 100 dernières valeurs)
        self.error_history.append(error)
        self.correction_history.append(correction)
        if len(self.error_history) > 100:
            self.error_history.pop(0)
            self.correction_history.pop(0)
        
        return (int(left_speed), int(right_speed))
    
    def get_debug_info(self):
        """Retourne les informations de debug."""
        return {
            'previous_error': self.previous_error,
            'integral': self.integral,
            'error_history': self.error_history[-10:],  # 10 dernières valeurs
            'correction_history': self.correction_history[-10:]
        }