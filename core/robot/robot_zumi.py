#!/usr/bin/env python
# -*- coding: utf-8 -*-
# robot_zumi.py
# ------------------
# Implémentation du robot Zumi. ici on interface toute les méthodes mises
# à disposition par le package Zumi pour contrôler le robot.
# Référence des fonctions du package Zumi:
# https://docs.robolink.com/docs/Zumi/Python/Function-Documentation

import time

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

# Vitesses de référence pour les moteurs du Zumi
DRIVE_SPEED = 20
TURN_SPEED = 15

class RobotZumi(RobotBase):
    def __init__(self):
        self.zumi = Zumi()
        self.camera = PiCam2(rotate_180=True)  # Camera montee a l'envers -> rotation 180 deg
        self.screen = Screen()
        self.personality = Personality(self.zumi, self.screen)

        self.calibrate_sensors()  # Calibrage initial des capteurs pour des lectures précises

# ---------------------------------------------------------------------------------
#                             Contrôle des moteurs
# ---------------------------------------------------------------------------------
    def control_motors(self, roue_g_speed: float, roue_d_speed: float):
        """
        Définit la vitesse des moteurs du Zumi.
    
        """
        ## les leds semble causer probleme
        try: 
            self.zumi.brake_lights_off()
        except Exception as e:
            print("Erreur self.zumi.brake_lights_off(): {}".format(e))
        
        try: 
            self.zumi.headlights_on()
        except Exception as e:
            print("Erreur self.zumi.headlights_on(): {}".format(e))

        if roue_g_speed > DRIVE_SPEED:
            left_speed = DRIVE_SPEED
        elif roue_g_speed < -DRIVE_SPEED:
            left_speed = -DRIVE_SPEED
        else:
            left_speed = roue_g_speed

        if roue_d_speed > DRIVE_SPEED:
            right_speed = DRIVE_SPEED
        elif roue_d_speed < -DRIVE_SPEED:
            right_speed = -DRIVE_SPEED
        else:
            right_speed = roue_d_speed


        # contrôle des clignotants
        if right_speed > left_speed:
            try:
                self.zumi.signal_right_on()
            except Exception as e:
                print("Erreur self.zumi.signal_right_on(): {}".format(e))
            try:    
                self.zumi.signal_left_off()
            except Exception as e:
                print("Erreur self.zumi.signal_left_off(): {}".format(e))
        elif left_speed > right_speed:
            try:
                self.zumi.signal_left_on()
            except Exception as e:
                print("Erreur self.zumi.signal_left_on(): {}".format(e))
            try:
                self.zumi.signal_right_off()
            except Exception as e:
                print("Erreur self.zumi.signal_right_off(): {}".format(e))
        else:
            try:
                self.zumi.signal_left_off()
            except Exception as e:
                print("Erreur self.zumi.signal_left_off(): {}".format(e))
            try:
                self.zumi.signal_right_off()
            except Exception as e:
                print("Erreur self.zumi.signal_right_off(): {}".format(e))
        
        self.zumi.control_motors(left_speed, right_speed)

    def stop(self):
        """
        Arrête les moteurs du Zumi.
        """
        self.zumi.stop()
        try:
            self.zumi.brake_lights_on()
        except Exception as e:
            print("Erreur self.zumi.brake_lights_on(): {}".format(e))

        self._reset_PID()  # Réinitialise les PIDs pour éviter les dérives après un arrêt


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
        Calibre les capteurs du Zumi (MPU, IR, etc.).
        Doit être appelé au démarrage pour assurer des lectures précises.
        """
        try:
            # Reset des états de conduite
            self._reset_drive_state()

            # Calibration des sensors
            self.zumi.calibrate_gyro()
            time.sleep(0.5)  # Pause pour stabiliser les lectures après calibrage
            self.zumi.mpu.calibrate_MPU(count = 500)
            time.sleep(0.5)  # Pause pour stabiliser les lectures après calibrage
        except Exception as e:
            print("Erreur lors du calibrage des capteurs: {}".format(e))

    def _reset_drive_state(self):
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
            self.zumi.forward_step(speed, desired_angle)
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




