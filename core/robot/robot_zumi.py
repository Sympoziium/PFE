#!/usr/bin/env python
# -*- coding: utf-8 -*-
# robot_zumi.py
# ------------------
# Implémentation du robot Zumi.

import numpy
from core.robot.robot_base import RobotBase

# Import du package Zumi
import sys
sys.path.append("/usr/local/lib/python3.5/dist-packages")  # chemin du package zumi
from zumi.zumi import Zumi
from zumi.util.camera import Camera
from zumi.util.screen import Screen  
from zumi.personality import Personality

# Vitesses de référence pour les moteurs du Zumi
DRIVE_SPEED = 20
TURN_SPEED = 15

class RobotZumi(RobotBase):
    def __init__(self):
        self.zumi = Zumi()
        self.camera = Camera()
        self.screen = Screen()
        self.personality = Personality(self.zumi, self.screen)
        
# ---------------------------------------------------------------------------------
#                             Contrôle des moteurs
# ---------------------------------------------------------------------------------
    def control_motors(self, roue_g_speed: float, roue_d_speed: float):
        """
        Définit la vitesse des moteurs du Zumi.
    
        """
        ## les leds semble causer probleme
        try: 
            self.zumi.back_lights_off()
        except Exception as e:
            print("Erreur self.zumi.back_lights_off(): {}".format(e))
        
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
            self.zumi.back_lights_on()
        except Exception as e:
            print("Erreur self.zumi.back_lights_on(): {}".format(e))

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




