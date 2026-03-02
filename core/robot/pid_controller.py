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
             rotation_mode=True, deadband=1, rotation_scale=0.3, auto_reset_threshold=100,
             angle_scale=0.3, max_angle=45, min_angle_threshold=2):
        """
        Initialise le contrôleur PID.
        
        Args:
            kp (float): Gain proportionnel
            ki (float): Gain intégral
            kd (float): Gain dérivé
            base_speed (int): Vitesse de base des moteurs (0-100)
            max_correction (int): Correction maximale applicable
            rotation_mode (bool): Si True, utilise turn() pour rotation précise. Si False, avance en suivant la ligne.
            angle_scale (float): Facteur de conversion erreur -> angle (ex: 0.3 = 100 pixels erreur -> 30 degrés)
            max_angle (float): Angle maximal de rotation en degrés (limite les rotations brusques)
            min_angle_threshold (float): Seuil minimal d'angle en degrés (en dessous, pas de rotation)
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.base_speed = base_speed
        self.max_correction = max_correction
        self.rotation_mode = rotation_mode
        self.deadband = deadband
        self.rotation_scale = rotation_scale
        self.auto_reset_threshold = auto_reset_threshold
        
        # Paramètres pour le calcul d'angle en mode rotation
        self.angle_scale = angle_scale
        self.max_angle = max_angle
        self.min_angle_threshold = min_angle_threshold
        
        # Variables internes
        self.previous_error = 0
        self.integral = 0
        self.last_time = None
        self.last_angle = 0  # Dernier angle calculé
        
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
        
    def update_params(self, kp=None, ki=None, kd=None, base_speed=None, max_correction=None, 
                      rotation_mode=None, angle_scale=None, max_angle=None, min_angle_threshold=None):
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
        if rotation_mode is not None:  
            self.rotation_mode = rotation_mode
        if angle_scale is not None:
            self.angle_scale = angle_scale
        if max_angle is not None:
            self.max_angle = max_angle
        if min_angle_threshold is not None:
            self.min_angle_threshold = min_angle_threshold
            
    def get_params(self):
        """Retourne les paramètres actuels du PID."""
        return {
            'kp': self.kp,
            'ki': self.ki,
            'kd': self.kd,
            'base_speed': self.base_speed,
            'max_correction': self.max_correction,
            'rotation_mode': self.rotation_mode,
            'auto_reset_threshold': self.auto_reset_threshold,
            'angle_scale': self.angle_scale,
            'max_angle': self.max_angle,
            'min_angle_threshold': self.min_angle_threshold
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
            # ===== AUTO-RESET si erreur trop grande =====
            if abs(error) > self.auto_reset_threshold:
                print("[PID] Erreur trop grande ({}), réinitialisation automatique".format(error))
                self.integral = 0  # Reset de l'intégrale
                self.previous_error = 0  # Reset du terme dérivé
                # On garde last_time pour éviter un saut dans dt
    
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
            
            # ===== NOUVELLE FONCTION: Saturation non-linéaire =====
            def apply_nonlinear_scaling(speed):
                """
                Applique une courbe non-linéaire pour réduire les petites vitesses.
                Utilise une fonction cubique pour avoir un contrôle plus fin.
                """
                # Seuil en dessous duquel on applique la mise à l'échelle agressive
                if abs(speed) < 1.0:
                    return 0  # Vitesses vraiment minuscules = 0
                
                # Fonction cubique: vitesse_finale = signe * (vitesse_normalisée)^3 * échelle
                # Cela donne une courbe douce avec plus de résolution pour les petites valeurs
                sign = 1 if speed >= 0 else -1
                abs_speed = abs(speed)
                
                # Normaliser par rapport à la correction max
                normalized = abs_speed / self.max_correction
                
                # Appliquer une courbe cubique (x^3) pour avoir plus de granularité en bas
                # puis re-scaler à la correction max
                scaled = (normalized ** 3) * self.max_correction
                
                return sign * scaled
            
            # ===== Mode rotation vs mode avance =====
            if self.rotation_mode:
                # MODE ROTATION: Tourne sur place pour centrer la ligne
                # Appliquer la correction avec mise à l'échelle non-linéaire
                left_correction = apply_nonlinear_scaling(correction) * self.rotation_scale
                right_correction = apply_nonlinear_scaling(correction) * self.rotation_scale
                
                # Si erreur négative (ligne à gauche): tourner à gauche (L-, R+)
                # Si erreur positive (ligne à droite): tourner à droite (L+, R-)
                left_speed = -left_correction
                right_speed = right_correction
            else:
                # MODE AVANCE: Avance en suivant la ligne
                # Appliquer la mise à l'échelle non-linéaire
                scaled_correction = apply_nonlinear_scaling(correction)
                
                # Si erreur positive (ligne à droite): ralentir roue droite, accélérer roue gauche
                # Si erreur négative (ligne à gauche): ralentir roue gauche, accélérer roue droite
                left_speed = self.base_speed - scaled_correction
                right_speed = self.base_speed + scaled_correction
            
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
    
    def compute_rotation_angle(self, error):
        """
        Calcule l'angle de rotation nécessaire pour corriger l'erreur.
        Utilisé en mode rotation avec la fonction turn().
        
        Args:
            error (float): Erreur de position (offset de la ligne)
                          Négatif = ligne à gauche, Positif = ligne à droite
        
        Returns:
            float: Angle de rotation en degrés (positif = gauche, négatif = droite)
                   Retourne None si l'angle est en dessous du seuil minimal
        """
        # Calculer l'angle brut basé sur l'erreur
        # Erreur négative (ligne à gauche) -> angle positif (tourner à gauche)
        # Erreur positive (ligne à droite) -> angle négatif (tourner à droite)
        raw_angle = -error * self.angle_scale
        
        # Appliquer le PID pour affiner l'angle
        current_time = time.time()
        
        # Calculer dt (delta time)
        if self.last_time is None:
            dt = 0.05
        else:
            dt = current_time - self.last_time
            if dt <= 0:
                dt = 0.05
        
        self.last_time = current_time
        
        # Terme proportionnel sur l'erreur
        P = self.kp * error
        
        # Terme intégral (avec limites)
        self.integral += error * dt
        max_integral = 100  # Limite arbitraire pour l'intégrale
        self.integral = max(-max_integral, min(max_integral, self.integral))
        I = self.ki * self.integral
        
        # Terme dérivé
        derivative = (error - self.previous_error) / dt if dt > 0 else 0
        D = self.kd * derivative
        
        # Correction PID
        pid_correction = P + I + D
        
        # Appliquer la correction à l'angle (conversion avec angle_scale)
        angle = -pid_correction * self.angle_scale
        
        # Limiter l'angle
        angle = max(-self.max_angle, min(self.max_angle, angle))
        
        # Sauvegarder pour la prochaine itération
        self.previous_error = error
        self.last_angle = angle
        
        # Historique
        self.error_history.append(error)
        self.correction_history.append(angle)
        if len(self.error_history) > 100:
            self.error_history.pop(0)
            self.correction_history.pop(0)
        
        # Si l'angle est trop petit, ne pas tourner
        if abs(angle) < self.min_angle_threshold:
            return None
        
        return angle
    
    def get_debug_info(self):
        """Retourne les informations de debug."""
        return {
            'previous_error': self.previous_error,
            'integral': self.integral,
            'error_history': self.error_history[-10:],  # 10 dernières valeurs
            'correction_history': self.correction_history[-10:],
            'last_angle': self.last_angle if hasattr(self, 'last_angle') else 0
        }