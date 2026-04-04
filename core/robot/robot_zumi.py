#!/usr/bin/env python
# -*- coding: utf-8 -*-
# robot_zumi.py
# ------------------
# Implémentation du robot Zumi. ici on interface toute les méthodes mises
# à disposition par le package Zumi pour contrôler le robot.
# Référence des fonctions du package Zumi:
# https://docs.robolink.com/docs/Zumi/Python/Function-Documentation

import json
import time
from pathlib import Path

import numpy
from core.robot.robot_base import RobotBase

# Import de notre wrapper de caméra Zumi (convertit RGB→BGR)
from core.camera.picam2 import PiCam2

# Import du package Zumi
import sys
sys.path.append("/usr/local/lib/python3.5/dist-packages")  # chemin du package zumi
from zumi.zumi import Zumi
from core.hardware.screen import Screen
from core.hardware.personality import Personality

# === Constantes de contrôle centralisées ===
# Ces valeurs sont la source unique de vérité pour tout le projet.
DRIVE_SPEED_DEFAULT = 15    # Vitesse par défaut avance/recul
TURN_SPEED_DEFAULT = 1     # Vitesse par défaut virages

# Constantes legacy (pour compatibilité, utilisent les nouvelles valeurs)
DRIVE_SPEED = DRIVE_SPEED_DEFAULT
TURN_SPEED = TURN_SPEED_DEFAULT

BATTERY_VOLTAGE_MAX = 4.2  # Tension max de la batterie du Zumi (en volts)
BATTERY_VOLTAGE_MIN = 3.4  # Tension minimale pour un fonctionnement sûr (en volts)

# === Profils de caméra ===
# Utilisés par le server_controller pour ajuster automatiquement la résolution
# selon le mode actif (contrôleur ou streaming seul).
CAMERA_PROFILES = {
    'passive': {  # Détection passive avec contrôleurs (manuel, ML) - économie CPU
        'width': 320,
        'height': 240,
        'fps': 20,
    },
    'stream': {   # Streaming vidéo seul (pas de contrôleur actif)
        'width': 640,
        'height': 480,
        'fps': 30,
    },
}

class RobotZumi(RobotBase):
    def __init__(self):
        self.zumi = Zumi()
        self.camera = PiCam2(rotate_180=True)  # Camera montee a l'envers -> rotation 180 deg
        self.screen = Screen()
        self.personality = Personality(self.zumi, self.screen)
        self._stop_since = None  # Timestamp du début de l'arrêt courant
        self._PID_RESET_DELAY = 1  # Secondes d'arrêt continu avant reset PID

        # Calibration IR: offsets entre paires L/R et baselines par capteur
        self.ir_calibration = None
        self._ir_calibration_path = Path(__file__).parent / "ir_calibration.json"
        self.load_ir_calibration()

        self.calibrate_sensors()  # Calibrage initial des capteurs pour des lectures précises

# ---------------------------------------------------------------------------------
#                             Contrôle des moteurs
# ---------------------------------------------------------------------------------
    def control_motors(self, roue_g_speed: float, roue_d_speed: float):
        """
        Définit la vitesse des moteurs du Zumi.
        La correction de trajectoire est gérée par le PID de cap du ManualController,
        pas par un trim statique ici.
        """
        # Clamp matériel final absolu (Zumi accepte typiquement -126 à 127, on limite à 100 par sécurité)
        left_speed  = int(max(-100, min(100, roue_g_speed)))
        right_speed = int(max(-100, min(100, roue_d_speed)))

        self._stop_since = None  # ← Le robot bouge, on annule le timer d'arrêt
        self.zumi.control_motors(right_speed, left_speed)

    def stop(self):
        """
        Arrête les moteurs du Zumi.
        """
        self.zumi.stop()
        now = time.time()
        if self._stop_since is None:
            self._stop_since = now  # Début d'un arrêt
        elif now - self._stop_since >= self._PID_RESET_DELAY:
            self._reset_PID()
            self._reset_gyro()
            self._stop_since = now  # Réarme pour le prochain arrêt prolongé


    def turn(self, angle: float):
        """
        Fait tourner le Zumi d'un angle donné.
        Angle positif = rotation à gauche, angle négatif = rotation à droite.
        
        Args:
            angle (float): Angle de rotation en degrés
        """
        try:
            if angle > 0:
                self.zumi.turn_left(abs(angle))
            elif angle < 0:
                self.zumi.turn_right(abs(angle))
            else:
                print("turn() appelé avec angle=0, aucune rotation effectuée")  # Si angle == 0, ne fait rien
        except Exception as e:
            print("Erreur lors de la rotation de {} degrés: {}".format(angle, e))

        self._reset_gyro()  # Réinitialise le gyroscope après la rotation pour éviter les dérives

# ---------------------------------------------------------------------------------
#                             Contrôle de l'écran
# ---------------------------------------------------------------------------------
    def display_text(self, text: str):
        """
        Affiche de le texte sur l'écran du Zumi.
        """
        try:
            self.screen.draw_text_center(text)
        except Exception as e:
            print("Erreur lors de l'affichage du texte: {}".format(e))
    
    def display_image_from_path(self, image_path: str):
        """
        Affiche une image sur l'écran du Zumi apartir d'un path d'enregistrement.
        """
        try:
            self.screen.draw_image(self.screen.path_to_image(image_path))
        except Exception as e:
            print("Erreur lors de l'affichage de l'image: {}".format(e))

    def display_image(self, image: numpy.ndarray):
        """
        Docstring for display_image
        :type image: numpy.ndarray
        """
        try:
            self.screen.show_screen(image)
        except Exception as e:
            print("Erreur lors de l'affichage de l'image: {}".format(e))

    def clear_screen(self):
        """
        Efface l'écran du Zumi.
        """
        try:
            self.screen.clear_display()
        except Exception as e:
            print("Erreur lors de l'effacement de l'écran: {}".format(e))

    # --------------------------------------------------------
    #                   Contrôle de la personalité
    # --------------------------------------------------------
    def angry_reaction(self):
        """
        Fait une réaction "colère" avec le Zumi.
        """
        try:
            self.screen.angry()
            self.personality.angry()
        except Exception as e:
            print("Erreur lors de la réaction de colère: {}".format(e))

    def happy_reaction(self):
        """
        Fait une réaction "heureux" avec le Zumi.
        """
        try:
            self.screen.happy()
            self.personality.happy()
        except Exception as e:
            print("Erreur lors de la réaction heureux: {}".format(e))

    def look_around_reaction(self):
        """
        Fait une réaction "regarder autour" avec le Zumi.
        """
        try:
            self.personality.look_around()
        except Exception as e:
            print("Erreur lors de la réaction regarder autour: {}".format(e))

    def sad_reaction(self):
        """
        Fait une réaction "triste" avec le Zumi.
        """
        try:
            self.screen.sad()
        except Exception as e:
            print("Erreur lors de la réaction triste: {}".format(e))

    def sleeping_reaction(self):
        """
        Fait une réaction "dormir" avec le Zumi.
        """
        try:
            self.screen.sleeping()
        except Exception as e:
            print("Erreur lors de la réaction dormir: {}".format(e))

    def celebrate_reaction(self):
        """
        Fait une réaction "célébrer" avec le Zumi.
        """
        try:
            self.personality.celebrate()
        except Exception as e:
            print("Erreur lors de la réaction célébrer: {}".format(e))

    # --------------------------------------------------------
    #                   Capteurs (MPU, IR, batterie)
    # --------------------------------------------------------

    def calibrate_sensors(self):
        """
        Calibre les capteurs du Zumi (MPU, gyro).
        La calibration IR est chargée depuis ir_calibration.json au boot.
        Pour recalibrer les IR, utiliser calibrate_ir() via le UI.
        """
        try:
            # Reset des états de conduite
            self.reset_drive_state()

            # Calibration MPU + gyro
            self.zumi.calibrate_gyro()
            time.sleep(0.5)
            self.zumi.mpu.calibrate_MPU(count=500)
            time.sleep(0.5)

            # Vérifier si la calibration IR existe
            if self.ir_calibration is None:
                print("[WARN] Pas de calibration IR! Utilisez le Sensor Profiler pour creer un profil.")
        except Exception as e:
            print("Erreur lors du calibrage des capteurs: {}".format(e))

    def calibrate_ir(self, n_samples=50):
        """Calibre les 6 capteurs IR en mesurant les baselines sur surface noire.

        Le robot doit etre immobile sur la route noire (sans ligne, espace
        degage). Mesure la baseline de chaque capteur et les offsets entre
        paires gauche/droite.

        Ordre des capteurs: [front_r, bottom_r, back_r, bottom_l, back_l, front_l]

        Args:
            n_samples: Nombre d'echantillons (50=light auto, 200=heavy manuel)
        """
        try:
            print("[IR Calibration] Demarrage ({} samples)...".format(n_samples))
            readings = []
            for i in range(n_samples):
                ir = self.get_ir_data()
                if ir is not None:
                    readings.append(ir)
                time.sleep(0.02)  # ~50 Hz

            if len(readings) < 10:
                print("[IR Calibration] Echec: pas assez de lectures ({})".format(len(readings)))
                return None

            arr = numpy.array(readings, dtype=numpy.float64)
            baselines = arr.mean(axis=0).tolist()

            # Indices: 0=front_r, 1=bottom_r, 2=back_r, 3=bottom_l, 4=back_l, 5=front_l
            offsets = {
                "bottom": float(baselines[3] - baselines[1]),   # bot_left - bot_right
                "front": float(baselines[5] - baselines[0]),    # front_left - front_right
                "back": float(baselines[4] - baselines[2]),     # back_left - back_right
            }

            self.ir_calibration = {
                "ir_baselines": [round(b, 1) for b in baselines],
                "ir_offsets": offsets,
                "n_samples": len(readings),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }

            # Sauvegarder
            with open(str(self._ir_calibration_path), 'w') as f:
                json.dump(self.ir_calibration, f, indent=2)

            print("[IR Calibration] Baselines: {}".format(
                ["{}={:.0f}".format(n, b) for n, b in
                 zip(["fr", "br", "bkr", "bl", "bkl", "fl"], baselines)]))
            print("[IR Calibration] Offsets: bottom={:.1f}, front={:.1f}, back={:.1f}".format(
                offsets["bottom"], offsets["front"], offsets["back"]))
            print("[IR Calibration] Sauvegarde: {}".format(self._ir_calibration_path))

            return self.ir_calibration

        except Exception as e:
            print("[IR Calibration] Erreur: {}".format(e))
            return None

    def load_ir_calibration(self):
        """Charge la calibration IR depuis le fichier JSON si disponible."""
        try:
            if self._ir_calibration_path.exists():
                with open(str(self._ir_calibration_path), 'r') as f:
                    self.ir_calibration = json.load(f)
                print("[IR Calibration] Charge depuis {} (offset bottom={})".format(
                    self._ir_calibration_path,
                    self.ir_calibration.get("ir_offsets", {}).get("bottom", "?")))
            else:
                print("[IR Calibration] Pas de fichier de calibration ({}), utilisation des defauts".format(
                    self._ir_calibration_path))
        except Exception as e:
            print("[IR Calibration] Erreur chargement: {}".format(e))
            self.ir_calibration = None

    def reset_drive_state(self):
        """
        Réinitialise les PIDs et le Gyro du Zumi
        """
        try:
            self.zumi.reset_drive()
        except Exception as e:
            print("Erreur lors de la réinitialisation de l'état de conduite: {}".format(e))

    def _reset_gyro(self):
        """
        Réinitialise le gyroscope du Zumi.
        Utile pour corriger les dérives après une longue utilisation.
        """
        try:
            self.zumi.reset_gyro()
        except Exception as e:
            print("Erreur lors de la réinitialisation du gyroscope: {}".format(e))

    def _reset_PID(self):
        """
        Réinitialise les PIDs internes du Zumi.
        Utile pour corriger les dérives après une longue utilisation.
        """
        try:
            self.zumi.reset_PID()
        except Exception as e:
            print("Erreur lors de la réinitialisation des PIDs: {}".format(e))

    def forward_step(self, speed, desired_angle):
        """Un pas en avant avec correction de cap via le PID interne du Zumi.

        Args:
            speed:         Vitesse de déplacement [0, 127].
            desired_angle: Cap désiré en degrés.
        """
        try:
            if desired_angle is None:
                desired_angle = 0.0
            self.zumi.forward_step(speed = speed, desired_angle = desired_angle)
        except Exception as e:
            print("Erreur forward_step: {}".format(e))

    def get_angles(self):
        """Lit les angles gyroscope/accéléromètre via le MPU du Zumi.

        Returns:
            list: [Gyro_x, Gyro_y, Gyro_z, Acc_x, Acc_y,
                   Comp_x, Comp_y, Rot_x, Rot_y, Rot_z, tilt_state]
        """
        try:
            return self.zumi.update_angles()
        except Exception as e:
            print("Erreur get_angles: {}".format(e))
            return None

    def get_ir_data(self):
        """Lit les 6 capteurs IR du Zumi.

        Returns:
            list: [front_r, bottom_r, back_r, bottom_l, back_l, front_l]
                  valeurs 0-255.
        """
        try:
            return self.zumi.get_all_IR_data()
        except Exception as e:
            print("Erreur get_ir_data: {}".format(e))
            return None
        
    def get_front_right_ir(self):
        """Lit le capteur IR droit avant du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.front_right_detect()
        except Exception as e:
            print("Erreur get_front_right_ir: {}".format(e))
            return None
        
    def get_front_left_ir(self):
        """Lit le capteur IR gauche avant du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.front_left_detect()
        except Exception as e:
            print("Erreur get_front_left_ir: {}".format(e))
            return None
    
    def get_bottom_right_ir(self):
        """Lit le capteur IR droit bas du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.bottom_right_detect()
        except Exception as e:
            print("Erreur get_bottom_right_ir: {}".format(e))
            return None
        
    def get_bottom_left_ir(self):
        """Lit le capteur IR gauche bas du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.bottom_left_detect()
        except Exception as e:
            print("Erreur get_bottom_left_ir: {}".format(e))
            return None
        
    def get_back_right_ir(self):
        """Lit le capteur IR droit arrière du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.back_right_detect()
        except Exception as e:
            print("Erreur get_back_right_ir: {}".format(e))
            return None
        
    def get_back_left_ir(self): 
        """Lit le capteur IR gauche arrière du Zumi.

        Returns:
            int: Valeur du capteur (0-255).
        """
        try:
            return self.zumi.back_left_detect()
        except Exception as e:
            print("Erreur get_back_left_ir: {}".format(e))
            return None

    def get_orientation(self):
        """Retourne l'état d'orientation du Zumi.

        Returns:
            int: -1 à 7 (5 = roues au sol).
        """
        try:
            return self.zumi.get_orientation()
        except Exception as e:
            print("Erreur get_orientation: {}".format(e))
            return -1

    def get_battery_voltage(self):
        """Retourne la tension de la batterie du Zumi.

        Returns:
            float: Tension en volts (max 4.2V).
        """
        try:
            return self.zumi.get_battery_voltage()
        except Exception as e:
            print("Erreur get_battery_voltage: {}".format(e))
            return 0.0




