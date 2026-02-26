#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Line_detector.py
# ------------------
# Module de détecteur de lignes dans une image
# en appliquant des filtres de traitement d'image,
# comme la détection de contours

from .detector_base import BaseDetector
import cv2
import numpy as np

class LineDetector(BaseDetector):
    def process(self, frame):



        return {"detector": "line", "value": self.detect_lines(frame)}
    
    def attach_capture_dir(self, capture_dir):
        """Attache le dossier de capture d'images au détecteur."""
        self.CAPTURE_DIR = capture_dir

    def process_passive(self, frame):
        """Détection de lignes optimisée pour le live feed."""
        return {"detector": "line", "value": self.detect_lines(frame)}