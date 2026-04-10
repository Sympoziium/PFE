#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simulateur 2D temps reel pour le MLP Zumi.

Genere un circuit virtuel, simule les capteurs IR et IMU,
fait inferer le modele MLP, et affiche le resultat en temps reel avec pygame.
"""

import collections
import json
import math
import random
import time
import numpy as np
import torch
from pathlib import Path

try:
    import pygame
except ImportError:
    pygame = None

from dataset import (
    ENGINEERED_FEATURE_NAMES, WINDOW_SIZE, WINDOW_FEATURE_DIM,
    IR_OFFSET_DEFAULT, GAP_THRESHOLD, GYRO_Z_INDEX,
    DETECTION_INDICES,
)


# ============================================================
# Constantes physiques
# ============================================================

# Dimensions du tapis (cm)
MAT_WIDTH = 114.0
MAT_HEIGHT = 80.0

# Route
ROAD_WIDTH = 13.0       # cm
ROAD_HALF = ROAD_WIDTH / 2
BORDER_WIDTH = 0.5       # bordures jaunes
LINE_WIDTH = 0.7         # lignes blanches
LINE_HALF = LINE_WIDTH / 2
DASH_LENGTH = 2.5        # longueur tiret
DASH_GAP = 2.5           # gap entre tirets
DASH_PERIOD = DASH_LENGTH + DASH_GAP

# Robot Zumi
ROBOT_LENGTH = 9.5       # cm
ROBOT_WIDTH = 6.5        # cm
WHEELBASE = 6.5          # cm (distance entre axes des roues)
FRONT_DIST = 5.0         # cm du centre au front
BACK_DIST = 4.5          # cm du centre a l'arriere

# Capteurs IR bottom (position relative au centre du robot)
IR_FORWARD_OFFSET = FRONT_DIST - 2.0  # 2 cm du front = 3.0 cm du centre
IR_LATERAL_OFFSET = 0.6  # 0.6 cm de chaque cote

# Simulation
SIM_DT = 1.0 / 20.0     # 20 Hz
MOTOR_SPEED_TO_CMS = 0.5  # 1 unite moteur ≈ 0.5 cm/s (estimation)
# Efficacite du moteur gauche: fraction de la vitesse commandee reellement
# produite. Le moteur gauche du robot est plus faible; le PID de cap
# compensait en boostant les commandes gauches. Le modele a appris ce biais.
# En simulant la faiblesse du moteur gauche, les predictions du modele
# (qui incluent la compensation PID) produisent un mouvement correct.
# Valeur par defaut estimee depuis le dataset: mean_right / mean_left.
MOTOR_EFFICIENCY_LEFT_DEFAULT = 0.927

# Rendu
SCALE = 7  # 1 cm = 7 px
WINDOW_W = int(MAT_WIDTH * SCALE) + 100  # marge pour overlay
WINDOW_H = int(MAT_HEIGHT * SCALE) + 60
MARGIN_X = 50
MARGIN_Y = 30

# Couleurs
COL_GRASS = (76, 153, 76)
COL_ROAD = (40, 40, 40)
COL_BORDER = (220, 180, 20)
COL_LINE = (240, 240, 240)
COL_ROBOT = (30, 100, 220)
COL_TRAIL = (0, 200, 200, 128)
COL_TEXT = (240, 240, 240)
COL_OVERLAY_BG = (20, 20, 20, 200)
COL_SENSOR_ROAD = (0, 200, 0)
COL_SENSOR_LINE = (255, 50, 50)
COL_SENSOR_GRASS = (150, 150, 150)


# ============================================================
# Circuits
# ============================================================

def _make_loop_track():
    """Circuit en boucle fermee simple (oval avec virages 90°)."""
    # Rectangle arrondi centré sur le tapis
    cx, cy = MAT_WIDTH / 2, MAT_HEIGHT / 2
    hw, hh = 35, 22  # demi-largeur, demi-hauteur du rectangle
    r = 12  # rayon des virages

    points = []
    # Bas gauche -> bas droite
    for x in np.linspace(cx - hw + r, cx + hw - r, 20):
        points.append((x, cy - hh))
    # Virage bas-droite
    for a in np.linspace(-math.pi/2, 0, 10):
        points.append((cx + hw - r + r * math.cos(a), cy - hh + r + r * math.sin(a)))
    # Droite bas -> droite haut
    for y in np.linspace(cy - hh + r, cy + hh - r, 15):
        points.append((cx + hw, y))
    # Virage haut-droite
    for a in np.linspace(0, math.pi/2, 10):
        points.append((cx + hw - r + r * math.cos(a), cy + hh - r + r * math.sin(a)))
    # Haut droite -> haut gauche
    for x in np.linspace(cx + hw - r, cx - hw + r, 20):
        points.append((x, cy + hh))
    # Virage haut-gauche
    for a in np.linspace(math.pi/2, math.pi, 10):
        points.append((cx - hw + r + r * math.cos(a), cy + hh - r + r * math.sin(a)))
    # Gauche haut -> gauche bas
    for y in np.linspace(cy + hh - r, cy - hh + r, 15):
        points.append((cx - hw, y))
    # Virage bas-gauche
    for a in np.linspace(math.pi, 3*math.pi/2, 10):
        points.append((cx - hw + r + r * math.cos(a), cy - hh + r + r * math.sin(a)))

    return points, True  # True = boucle


def _catmull_rom(p0, p1, p2, p3, n_points=10, alpha=0.5):
    """Interpole une courbe Catmull-Rom entre p1 et p2 (p0/p3 = controle).

    Produit des courbes naturellement lisses sans joints brusques.
    alpha=0.5 = centripetal (evite les boucles et cusps).
    """
    def tj(ti, pi, pj):
        dx, dy = pj[0]-pi[0], pj[1]-pi[1]
        d = (dx*dx + dy*dy) ** 0.5
        return ti + max(d, 1e-6) ** alpha

    t0 = 0.0
    t1 = tj(t0, p0, p1)
    t2 = tj(t1, p1, p2)
    t3 = tj(t2, p2, p3)

    pts = []
    for i in range(n_points):
        t = t1 + (t2 - t1) * i / n_points
        a1 = [(t1-t)/(t1-t0)*p0[j] + (t-t0)/(t1-t0)*p1[j] for j in range(2)]
        a2 = [(t2-t)/(t2-t1)*p1[j] + (t-t1)/(t2-t1)*p2[j] for j in range(2)]
        a3 = [(t3-t)/(t3-t2)*p2[j] + (t-t2)/(t3-t2)*p3[j] for j in range(2)]
        b1 = [(t2-t)/(t2-t0)*a1[j] + (t-t0)/(t2-t0)*a2[j] for j in range(2)]
        b2 = [(t3-t)/(t3-t1)*a2[j] + (t-t1)/(t3-t1)*a3[j] for j in range(2)]
        c  = [(t2-t)/(t2-t1)*b1[j] + (t-t1)/(t2-t1)*b2[j] for j in range(2)]
        pts.append((c[0], c[1]))
    return pts


def _point_polyline_min_dist(px, py, polyline, skip_last_n=0):
    """Distance minimale d'un point a une polyligne (en ignorant les skip_last_n derniers segments)."""
    n = len(polyline) - skip_last_n
    min_d = float('inf')
    for i in range(max(n - 1, 0)):
        ax, ay = polyline[i]
        bx, by = polyline[i+1]
        abx, aby = bx-ax, by-ay
        ab_sq = abx*abx + aby*aby
        if ab_sq < 1e-10:
            d = math.sqrt((px-ax)**2 + (py-ay)**2)
        else:
            t = max(0, min(1, ((px-ax)*abx + (py-ay)*aby) / ab_sq))
            proj_x, proj_y = ax + t*abx, ay + t*aby
            d = math.sqrt((px-proj_x)**2 + (py-proj_y)**2)
        min_d = min(min_d, d)
    return min_d


def _make_course_track():
    """Genere un parcours procedural avec courbes Catmull-Rom lisses.

    Approche:
    1. Placer des points de controle espaces en verifiant les collisions
    2. Interpoler avec une spline Catmull-Rom pour des courbes naturelles
    3. La courbure maximale est controlée par l'espacement des points
    """
    rng = random.Random()  # seed aleatoire = parcours different a chaque lancement
    margin = ROAD_WIDTH + 2       # distance min entre segments non-adjacents
    mat_margin = ROAD_HALF + 2    # marge du bord du tapis
    step_dist = 18.0              # distance entre points de controle (~18cm)
    max_turn = math.pi / 3        # angle max par segment (60°)
    n_control = 60                # nombre max de points de controle (pour ~1000cm)
    pts_per_seg = 8               # points d'interpolation par segment de spline

    # Depart aleatoire pres d'un des 4 coins, direction vers l'interieur
    # parallele a un bord (longueur ou largeur du tapis)
    corner = rng.choice([
        # (x, y, heading) — coin, puis direction parallele vers l'interieur
        (mat_margin + 2, mat_margin + 2, 0),              # bas-gauche → vers la droite
        (MAT_WIDTH - mat_margin - 2, mat_margin + 2, math.pi),  # bas-droite → vers la gauche
        (mat_margin + 2, MAT_HEIGHT - mat_margin - 2, 0),        # haut-gauche → vers la droite
        (MAT_WIDTH - mat_margin - 2, MAT_HEIGHT - mat_margin - 2, math.pi),  # haut-droite → vers la gauche
        (mat_margin + 2, mat_margin + 2, math.pi/2),       # bas-gauche → vers le haut
        (MAT_WIDTH - mat_margin - 2, mat_margin + 2, math.pi/2),  # bas-droite → vers le haut
        (mat_margin + 2, MAT_HEIGHT - mat_margin - 2, -math.pi/2),  # haut-gauche → vers le bas
        (MAT_WIDTH - mat_margin - 2, MAT_HEIGHT - mat_margin - 2, -math.pi/2),  # haut-droite → vers le bas
    ])

    # 5 premiers points en ligne droite pour un depart stable
    start_x, start_y, heading = corner
    control_pts = []
    for i in range(5):
        control_pts.append((
            start_x + i * step_dist * math.cos(heading),
            start_y + i * step_dist * math.sin(heading),
        ))

    for step_i in range(n_control):
        placed = False
        cur_x, cur_y = control_pts[-1]

        # Calculer le vecteur vers le centre du tapis pour biaiser les virages
        center_x, center_y = MAT_WIDTH / 2, MAT_HEIGHT / 2
        to_center_angle = math.atan2(center_y - cur_y, center_x - cur_x)

        # Mesurer la proximite aux bords (0 = au centre, 1 = au bord)
        border_proximity = max(
            1 - cur_x / (MAT_WIDTH / 2) if cur_x < MAT_WIDTH / 2 else 1 - (MAT_WIDTH - cur_x) / (MAT_WIDTH / 2),
            1 - cur_y / (MAT_HEIGHT / 2) if cur_y < MAT_HEIGHT / 2 else 1 - (MAT_HEIGHT - cur_y) / (MAT_HEIGHT / 2),
        )
        border_proximity = max(0, min(1, border_proximity))

        # Generer des angles candidats
        candidates = []
        for _ in range(200):
            delta_a = rng.uniform(-max_turn, max_turn)
            candidates.append(delta_a)

        # Calculer le "centre de masse" de la route deja placee
        # pour biaiser vers les zones vides du tapis
        if len(control_pts) > 1:
            road_cx = sum(p[0] for p in control_pts) / len(control_pts)
            road_cy = sum(p[1] for p in control_pts) / len(control_pts)
        else:
            road_cx, road_cy = cur_x, cur_y

        def _score_angle(delta_a):
            """Score un angle: favorise s'eloigner des bords ET de la route existante."""
            new_h = heading + delta_a
            nx = cur_x + step_dist * math.cos(new_h)
            ny = cur_y + step_dist * math.sin(new_h)

            # Score de base: preferer les virages (parcours interessant)
            score = abs(delta_a) * 0.5

            # Bonus 1: s'eloigner des bords du tapis (pres du bord = fort bonus vers centre)
            angle_to_center = to_center_angle - new_h
            angle_to_center = (angle_to_center + math.pi) % (2 * math.pi) - math.pi
            center_bonus = (1 + math.cos(angle_to_center)) * border_proximity * 2.0
            score += center_bonus

            # Bonus 2: s'eloigner de la concentration de route existante
            # Angle entre la direction candidate et la direction OPPOSEE au centre de masse
            away_from_road = math.atan2(ny - road_cy, nx - road_cx)
            angle_away = away_from_road - new_h
            angle_away = (angle_away + math.pi) % (2 * math.pi) - math.pi
            # Plus on s'eloigne de la concentration, plus le bonus est fort
            # Le bonus augmente avec le nombre de points (plus de route = plus de pression)
            density_factor = min(len(control_pts) / 10, 2.0)
            spread_bonus = (1 + math.cos(angle_away)) * density_factor * 0.8
            score += spread_bonus

            # Petite variation aleatoire pour la diversite
            score += rng.uniform(0, 0.3)
            return score

        # Trier par score (meilleur en premier)
        candidates.sort(key=lambda a: -_score_angle(a))

        for delta_a in candidates:
            new_heading = heading + delta_a
            nx = control_pts[-1][0] + step_dist * math.cos(new_heading)
            ny = control_pts[-1][1] + step_dist * math.sin(new_heading)

            # Hors tapis?
            if nx < mat_margin or nx > MAT_WIDTH - mat_margin:
                continue
            if ny < mat_margin or ny > MAT_HEIGHT - mat_margin:
                continue

            # Collision avec les points existants (ignorer les 3 derniers)
            if len(control_pts) > 3:
                d = _point_polyline_min_dist(nx, ny, control_pts, skip_last_n=3)
                if d < margin:
                    continue

            control_pts.append((nx, ny))
            heading = new_heading
            placed = True
            break

        if not placed:
            break  # bloque, terminer

    if len(control_pts) < 4:
        # Fallback: parcours en S
        control_pts = [
            (MAT_WIDTH - 12, 15), (MAT_WIDTH - 35, 15),
            (MAT_WIDTH - 55, 15), (MAT_WIDTH - 70, 25),
            (MAT_WIDTH - 70, 45), (MAT_WIDTH - 55, 60),
            (MAT_WIDTH - 35, 60), (MAT_WIDTH - 20, 50),
            (MAT_WIDTH - 20, 30), (MAT_WIDTH - 35, 20),
        ]

    # Interpoler avec Catmull-Rom pour des courbes lisses
    # Dupliquer le premier et dernier point pour les tangentes aux extremites
    padded = [control_pts[0]] + control_pts + [control_pts[-1]]
    smooth_pts = []
    for i in range(len(padded) - 3):
        seg_pts = _catmull_rom(padded[i], padded[i+1], padded[i+2], padded[i+3],
                               n_points=pts_per_seg)
        smooth_pts.extend(seg_pts)
    # Ajouter le dernier point
    smooth_pts.append(control_pts[-1])

    return smooth_pts, False


# ============================================================
# Track
# ============================================================

class Track:
    """Representation du circuit comme une polyligne avec route de largeur fixe."""

    def __init__(self, centerline_pts, is_loop=False):
        self.points = np.array(centerline_pts, dtype=np.float64)
        self.is_loop = is_loop
        self._precompute()

    def _precompute(self):
        """Precalcule les segments, longueurs cumulees et angles."""
        pts = self.points
        n = len(pts)
        self.segments = []
        self.cum_lengths = [0.0]
        self.angles = []  # angle de virage a chaque point

        for i in range(n - 1):
            seg = pts[i+1] - pts[i]
            length = np.linalg.norm(seg)
            self.segments.append((pts[i], pts[i+1], seg, max(length, 1e-6)))
            self.cum_lengths.append(self.cum_lengths[-1] + length)

        if self.is_loop and n > 1:
            seg = pts[0] - pts[-1]
            length = np.linalg.norm(seg)
            self.segments.append((pts[-1], pts[0], seg, max(length, 1e-6)))
            self.cum_lengths.append(self.cum_lengths[-1] + length)

        self.total_length = self.cum_lengths[-1]

        # Calculer les angles de virage a chaque point
        for i in range(1, n - 1):
            v1 = pts[i] - pts[i-1]
            v2 = pts[i+1] - pts[i]
            angle = math.atan2(v2[1], v2[0]) - math.atan2(v1[1], v1[0])
            angle = abs((angle + math.pi) % (2 * math.pi) - math.pi)
            self.angles.append(math.degrees(angle))
        if len(self.angles) == 0:
            self.angles = [0.0]

    def closest_point_on_track(self, pos):
        """Trouve le point le plus proche sur la centerline.

        Returns: (closest_point, signed_distance, distance_along_track, segment_index)
        """
        pos = np.array(pos, dtype=np.float64)
        best_dist_sq = float('inf')
        best_point = self.points[0]
        best_along = 0.0
        best_seg_idx = 0

        for i, (p1, p2, seg, seg_len) in enumerate(self.segments):
            # Projection du point sur le segment
            t = np.dot(pos - p1, seg) / (seg_len * seg_len)
            t = max(0.0, min(1.0, t))
            proj = p1 + t * seg
            dist_sq = np.sum((pos - proj) ** 2)

            if dist_sq < best_dist_sq:
                best_dist_sq = dist_sq
                best_point = proj
                best_along = self.cum_lengths[i] + t * seg_len
                best_seg_idx = i

        dist = math.sqrt(best_dist_sq)

        # Signe: positif = a gauche de la direction du segment, negatif = a droite
        seg = self.segments[best_seg_idx]
        dx, dy = seg[2][0], seg[2][1]
        cross = dx * (pos[1] - best_point[1]) - dy * (pos[0] - best_point[0])
        signed_dist = dist if cross >= 0 else -dist

        return best_point, signed_dist, best_along, best_seg_idx

    def is_on_road(self, pos):
        _, signed_dist, _, _ = self.closest_point_on_track(pos)
        return abs(signed_dist) < ROAD_HALF

    def get_turn_angle_at(self, seg_idx):
        """Retourne l'angle de virage au segment donne."""
        if seg_idx < len(self.angles):
            return self.angles[min(seg_idx, len(self.angles) - 1)]
        return 0.0

    def get_start_pos_and_heading(self):
        """Retourne la position et le heading de depart."""
        p0 = self.points[0]
        p1 = self.points[1] if len(self.points) > 1 else self.points[0] + np.array([1, 0])
        heading = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        return (float(p0[0]), float(p0[1])), heading


# ============================================================
# Robot simule
# ============================================================

class SimRobot:
    def __init__(self, x, y, theta, motor_efficiency_left=MOTOR_EFFICIENCY_LEFT_DEFAULT):
        self.x = x
        self.y = y
        self.theta = theta
        self.motor_efficiency_left = motor_efficiency_left
        self.v_left = 0.0
        self.v_right = 0.0
        self.speed = 0.0
        self.omega = 0.0
        self.omega_deg = 0.0  # vitesse angulaire en deg/s (pour gyro_z)
        self.prev_speed = 0.0
        self.trail = []
        # Gyro_z cumule (rot_z): demarre a ~89.9° comme le vrai robot
        self.gyro_z_cumul = 89.9

    def update(self, v_left, v_right, dt):
        self.v_left = v_left
        self.v_right = v_right

        # Conversion unites moteur -> cm/s avec asymetrie moteur simulee
        # Le moteur gauche est plus faible: il produit motor_efficiency_left
        # de la vitesse commandee. Le modele a appris a compenser via le PID.
        vl = v_left * MOTOR_SPEED_TO_CMS * self.motor_efficiency_left
        vr = v_right * MOTOR_SPEED_TO_CMS

        self.prev_speed = self.speed
        self.speed = (vl + vr) / 2
        self.omega = (vl - vr) / WHEELBASE
        self.omega_deg = self.omega * (180 / math.pi)  # vitesse angulaire deg/s

        self.x += self.speed * math.cos(self.theta) * dt
        self.y += self.speed * math.sin(self.theta) * dt
        self.theta += self.omega * dt

        # Accumuler le gyro_z (comme le vrai gyroscope integre)
        self.gyro_z_cumul += self.omega_deg * dt

        self.trail.append((self.x, self.y))
        if len(self.trail) > 2000:
            self.trail = self.trail[-1500:]

    def get_ir_sensor_positions(self):
        """Retourne les positions monde des 2 capteurs IR bottom."""
        cos_t = math.cos(self.theta)
        sin_t = math.sin(self.theta)

        # Position locale: (forward_offset, lateral_offset)
        fwd = IR_FORWARD_OFFSET

        # IR_bot_L: gauche du robot
        lx = self.x + fwd * cos_t - IR_LATERAL_OFFSET * sin_t
        ly = self.y + fwd * sin_t + IR_LATERAL_OFFSET * cos_t

        # IR_bot_R: droite du robot
        rx = self.x + fwd * cos_t + IR_LATERAL_OFFSET * sin_t
        ry = self.y + fwd * sin_t - IR_LATERAL_OFFSET * cos_t

        return (lx, ly), (rx, ry)


# ============================================================
# Modele de capteurs
# ============================================================

class IRSensorModel:
    def __init__(self, track):
        self.track = track

    def sample_ir(self, world_pos):
        """Retourne une valeur IR (0-255) a la position donnee."""
        _, signed_dist, along, _ = self.track.closest_point_on_track(world_pos)
        dist_to_center = abs(signed_dist)

        # Hors route = gazon
        if dist_to_center > ROAD_HALF:
            return 110.0 + random.gauss(0, 5)

        # Sur un tiret blanc?
        in_dash = (along % DASH_PERIOD) < DASH_LENGTH

        if in_dash and dist_to_center < LINE_HALF:
            # Sur la ligne blanche: plus on est au centre, plus c'est bas
            t = dist_to_center / LINE_HALF
            return 80.0 + 40.0 * t + random.gauss(0, 3)
        else:
            # Route noire
            return 215.0 + random.gauss(0, 5)

    def read_all(self, robot):
        """Lit les 6 capteurs IR + calcule IR_diff et IR_sum."""
        pos_l, pos_r = robot.get_ir_sensor_positions()

        ir_bot_l = self.sample_ir(pos_l)
        ir_bot_r = self.sample_ir(pos_r)

        # Les 4 autres capteurs: valeurs moyennes typiques + bruit
        ir_front_r = 182.0 + random.gauss(0, 3)
        ir_back_r = 147.0 + random.gauss(0, 3)
        ir_back_l = 188.0 + random.gauss(0, 3)
        ir_front_l = 194.0 + random.gauss(0, 3)

        ir_diff = ir_bot_l - ir_bot_r
        ir_sum = (ir_bot_l + ir_bot_r) / 2

        return {
            'values': [ir_front_r, ir_bot_r, ir_back_r, ir_bot_l, ir_back_l, ir_front_l],
            'diff': ir_diff,
            'sum': ir_sum,
            'bot_l': ir_bot_l,
            'bot_r': ir_bot_r,
            'pos_l': pos_l,
            'pos_r': pos_r,
        }

    def read_imu(self, robot, dt):
        """Genere des valeurs IMU simulees.

        Mapping vers le vecteur brut 29-dim (indices 16-26):
          [16] gyro_x: vitesse angulaire X (faible, bruit)
          [17] gyro_y: vitesse angulaire Y (faible, bruit)
          [18] gyro_z: vitesse angulaire Z = omega en deg/s (SIGNAL CLE pour le modele)
          [19] acc_x: acceleration lineaire X
          [20] acc_y: acceleration lineaire Y
          [21] comp_x: filtre complementaire X (~= gyro_x)
          [22] comp_y: filtre complementaire Y (~= gyro_y)
          [23] rot_x: angle de rotation X (faible)
          [24] rot_y: angle de rotation Y (faible)
          [25] rot_z: heading cumule en deg (integre du gyro_z)
          [26] tilt_state: etat d'inclinaison (constant ~5)
        """
        acc_linear = (robot.speed - robot.prev_speed) / dt if dt > 0 else 0

        # gyro_z = vitesse angulaire instantanee en deg/s
        # C'est LE signal que le PID de cap utilisait pour detecter la derive.
        # Le modele a appris a reagir a ce signal.
        gyro_z = robot.omega_deg

        return {
            'gyro_x': random.gauss(-0.4, 0.5),
            'gyro_y': random.gauss(1.1, 0.5),
            'gyro_z': gyro_z,
            'acc_x': -1.3 + random.gauss(0, 0.2) + acc_linear * 0.1,
            'acc_y': random.gauss(-0.2, 0.2),
            'comp_x': random.gauss(-0.4, 0.5),
            'comp_y': random.gauss(1.1, 0.5),
            'rot_x': random.gauss(-0.17, 0.03),
            'rot_y': random.gauss(-0.03, 0.03),
            'rot_z': robot.gyro_z_cumul,
            'tilt_state': 5.0,
        }


# ============================================================
# Metriques de simulation
# ============================================================

class SimMetrics:
    def __init__(self):
        self.ticks = 0
        self.time_on_road = 0
        self.time_off_road = 0
        self.off_road_events = 0
        self._was_on_road = True
        self.lateral_errors = []
        self.speeds = []
        self.steerings = []
        self.v_lefts = []
        self.v_rights = []
        self.on_roads = []
        self.streak_current = 0
        self.streak_max = 0
        self.segment_errors = {}  # seg_idx -> [errors]
        self.segment_angles = {}  # seg_idx -> angle

    def record(self, on_road, lateral_error, speed, steering, seg_idx, turn_angle,
               v_left=0, v_right=0):
        self.ticks += 1
        if on_road:
            self.time_on_road += 1
            self.streak_current += 1
            self.streak_max = max(self.streak_max, self.streak_current)
        else:
            self.time_off_road += 1
            if self._was_on_road:
                self.off_road_events += 1
            self.streak_current = 0
        self._was_on_road = on_road

        self.lateral_errors.append(abs(lateral_error))
        self.speeds.append(abs(speed))
        self.steerings.append(abs(steering))
        self.v_lefts.append(v_left)
        self.v_rights.append(v_right)
        self.on_roads.append(on_road)

        if seg_idx not in self.segment_errors:
            self.segment_errors[seg_idx] = []
            self.segment_angles[seg_idx] = turn_angle
        self.segment_errors[seg_idx].append(abs(lateral_error))

    def generate_report(self, track_mode):
        total_time = self.ticks * SIM_DT
        distance = sum(self.speeds) * SIM_DT

        errors = np.array(self.lateral_errors) if self.lateral_errors else np.array([0])
        speeds = np.array(self.speeds) if self.speeds else np.array([0])

        # Categoriser les segments par angle de virage
        angle_bins = [
            ("Lignes droites (<15 deg)", 0, 15),
            ("Virages legers (15-45 deg)", 15, 45),
            ("Virages moyens (45-90 deg)", 45, 90),
            ("Virages serres (>90 deg)", 90, 360),
        ]

        report_lines = []
        report_lines.append("")
        report_lines.append("=" * 60)
        report_lines.append("  Rapport de simulation")
        report_lines.append("=" * 60)
        report_lines.append(f"  Circuit: {'Boucle fermee' if track_mode == 'loop' else 'Parcours depart-arrivee'}")
        report_lines.append(f"  Duree: {total_time:.1f}s ({self.ticks} ticks)")
        report_lines.append(f"  Distance parcourue: {distance:.1f} cm")
        report_lines.append("")
        report_lines.append("  [SUIVI DE LIGNE]")

        on_pct = self.time_on_road / max(self.ticks, 1) * 100
        report_lines.append(f"    Temps sur la route: {self.time_on_road * SIM_DT:.1f}s ({on_pct:.1f}%)")
        report_lines.append(f"    Sorties de route: {self.off_road_events}")
        if self.off_road_events > 0:
            avg_off = self.time_off_road * SIM_DT / self.off_road_events
            report_lines.append(f"    Duree moyenne sortie: {avg_off:.1f}s")
        report_lines.append(f"    Ecart lateral moyen: {errors.mean():.1f} cm")
        report_lines.append(f"    Ecart lateral max: {errors.max():.1f} cm")
        report_lines.append(f"    Plus longue streak: {self.streak_max * SIM_DT:.1f}s ({self.streak_max} ticks)")
        report_lines.append("")
        report_lines.append("  [VITESSE]")
        report_lines.append(f"    Vitesse lineaire moyenne: {speeds.mean():.1f} cm/s")
        report_lines.append(f"    Vitesse max: {speeds.max():.1f} cm/s")

        steerings = np.array(self.steerings)
        report_lines.append(f"    Steering moyen (|L-R|): {steerings.mean():.1f}")
        report_lines.append("")
        report_lines.append("  [VIRAGES]")
        report_lines.append(f"    Performance par angle de virage:")

        for label, min_a, max_a in angle_bins:
            seg_errs = []
            seg_offs = 0
            for seg_idx, errs in self.segment_errors.items():
                angle = self.segment_angles.get(seg_idx, 0)
                if min_a <= angle < max_a:
                    seg_errs.extend(errs)
            if seg_errs:
                avg_err = np.mean(seg_errs)
                report_lines.append(f"      {label:30s}: ecart moyen {avg_err:.1f} cm")
            else:
                report_lines.append(f"      {label:30s}: (aucune donnee)")

        # Score global
        score = min(100, max(0, int(on_pct * 0.7 + (1 - min(errors.mean() / 5, 1)) * 30)))
        report_lines.append("")
        report_lines.append("  [CONCLUSION]")
        report_lines.append(f"    Score global: {score}/100")
        if errors.mean() < 2:
            report_lines.append(f"    Points forts: suivi de ligne precis")
        if self.off_road_events == 0:
            report_lines.append(f"    Points forts: aucune sortie de route")
        if self.off_road_events > 3:
            report_lines.append(f"    Points faibles: sorties de route frequentes ({self.off_road_events})")

        return "\n".join(report_lines), {
            'mode': track_mode,
            'duration_s': total_time,
            'distance_cm': distance,
            'time_on_road_pct': on_pct,
            'off_road_events': self.off_road_events,
            'lateral_error_mean': float(errors.mean()),
            'lateral_error_max': float(errors.max()),
            'longest_streak_s': self.streak_max * SIM_DT,
            'speed_mean': float(speeds.mean()),
            'score': score,
        }

    def generate_plots(self, save_path):
        """Genere les graphiques de la simulation."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        n = self.ticks
        if n < 2:
            return
        t = np.arange(n) * SIM_DT

        fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)

        # 1. Commandes moteur
        axes[0].plot(t, self.v_lefts, 'b-', alpha=0.7, label='Roue Gauche')
        axes[0].plot(t, self.v_rights, 'r-', alpha=0.7, label='Roue Droite')
        axes[0].set_ylabel('Vitesse moteur')
        axes[0].set_title('Commandes moteur au fil du temps')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        # 2. Steering
        steering = np.array(self.v_lefts) - np.array(self.v_rights)
        axes[1].plot(t, steering, 'g-', alpha=0.7)
        axes[1].axhline(y=0, color='k', linewidth=0.5)
        axes[1].set_ylabel('Steering (L-R)')
        axes[1].set_title('Steering')
        axes[1].grid(True, alpha=0.3)

        # 3. Ecart lateral
        axes[2].plot(t, self.lateral_errors, 'purple', alpha=0.7)
        axes[2].axhline(y=ROAD_HALF, color='r', linestyle='--', label=f'Bord route ({ROAD_HALF:.1f} cm)')
        axes[2].set_ylabel('Ecart lateral (cm)')
        axes[2].set_title('Distance a la centerline')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)

        # 4. Sur la route (binaire)
        on_road_arr = np.array(self.on_roads, dtype=float)
        axes[3].fill_between(t, 0, on_road_arr, color='green', alpha=0.3, label='Sur route')
        axes[3].fill_between(t, 0, 1 - on_road_arr, color='red', alpha=0.3, label='Hors route')
        axes[3].set_ylabel('Sur la route')
        axes[3].set_xlabel('Temps (s)')
        axes[3].set_title('Suivi de route')
        axes[3].set_ylim(-0.1, 1.1)
        axes[3].legend()
        axes[3].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"  Graphique sauvegarde: {save_path}")


# ============================================================
# Inference helper
# ============================================================

def build_state_vector(ir_data, imu_data):
    """Construit le vecteur 21-dim (detection exclue: indices 8-15 retires).

    Layout apres exclusion:
      0-5: IR values, 6: diff, 7: sum
      8-18: IMU (gyro, acc, comp, rot, tilt)
      19-20: camera (line_offset, line_detected)
    """
    vec29 = np.zeros(29, dtype=np.float32)
    # IR: indices 0-7
    vec29[0] = ir_data['values'][0]  # front_r
    vec29[1] = ir_data['values'][1]  # bot_r
    vec29[2] = ir_data['values'][2]  # back_r
    vec29[3] = ir_data['values'][3]  # bot_l
    vec29[4] = ir_data['values'][4]  # back_l
    vec29[5] = ir_data['values'][5]  # front_l
    vec29[6] = ir_data['diff']
    vec29[7] = ir_data['sum']
    # Detection: indices 8-15 (pas de detection en simulation)
    # IMU: indices 16-26
    vec29[16] = imu_data['gyro_x']
    vec29[17] = imu_data['gyro_y']
    vec29[18] = imu_data['gyro_z']
    vec29[19] = imu_data['acc_x']
    vec29[20] = imu_data['acc_y']
    vec29[21] = imu_data['comp_x']
    vec29[22] = imu_data['comp_y']
    vec29[23] = imu_data['rot_x']
    vec29[24] = imu_data['rot_y']
    vec29[25] = imu_data['rot_z']
    vec29[26] = imu_data['tilt_state']
    # Camera: indices 27-28
    vec29[27] = 0.0  # line_offset
    vec29[28] = 0.0  # line_detected
    # Exclure detection (indices 8-15) -> 21-dim
    keep_mask = [i for i in range(29) if i not in DETECTION_INDICES]
    return vec29[keep_mask]


def compute_engineered(vec_raw, prev_vec=None, ir_offset=IR_OFFSET_DEFAULT, window_buffer=None):
    """Ajoute 9 features PID-inspired -> 30-dim (detection exclue).

    Args:
        vec_raw: Vecteur 21-dim (detection exclue)
        prev_vec: Vecteur 30-dim precedent (pour derivees)
        ir_offset: Offset IR bottom (bot_left - bot_right)
        window_buffer: Buffer des vecteurs precedents (pour ir_error_integral)
    """
    raw_dim = len(vec_raw)
    ir_bot_r = vec_raw[1]
    ir_bot_l = vec_raw[3]
    ir_sum = (ir_bot_l + ir_bot_r) / 2.0
    gyro_z = vec_raw[GYRO_Z_INDEX]
    line_camera_offset = vec_raw[raw_dim - 2]  # camera toujours avant-dernier

    calibrated_error = (ir_bot_r - ir_bot_l) - (-ir_offset)
    line_visible = 1.0 if ir_sum < GAP_THRESHOLD else 0.0
    cal_error_norm = calibrated_error / (ir_sum + 1e-6)

    gyro_z_rate = 0.0
    if prev_vec is not None:
        rate = gyro_z - prev_vec[GYRO_Z_INDEX]
        if abs(rate) < 150.0:
            gyro_z_rate = rate

    heading_drift = gyro_z_rate * (1.0 - line_visible)

    # --- Nouvelles features ---
    # ir_error_derivative: delta calibrated_error
    ir_error_derivative = 0.0
    if prev_vec is not None:
        ir_error_derivative = calibrated_error - prev_vec[raw_dim + 0]  # prev calibrated_error

    # ir_error_integral: moyenne glissante sur 5 pas
    from dataset import INTEGRAL_WINDOW
    recent_errors = []
    if window_buffer is not None:
        for vec in list(window_buffer)[-(INTEGRAL_WINDOW - 1):]:
            recent_errors.append(vec[raw_dim + 0])  # calibrated_error index
    recent_errors.append(calibrated_error)
    ir_error_integral = sum(recent_errors) / len(recent_errors)

    # gyro_z_accel: delta gyro_z_rate
    gyro_z_accel = 0.0
    if prev_vec is not None:
        prev_gyro_z_rate = prev_vec[raw_dim + 3]  # prev gyro_z_rate
        gyro_z_accel = gyro_z_rate - prev_gyro_z_rate

    # lookahead_delta: discordance camera vs IR
    lookahead_delta = (line_camera_offset - cal_error_norm) * line_visible

    engineered = np.array([
        calibrated_error, line_visible, cal_error_norm,
        gyro_z_rate, heading_drift,
        ir_error_derivative, ir_error_integral, gyro_z_accel, lookahead_delta
    ], dtype=np.float32)

    return np.concatenate([vec_raw, engineered]).astype(np.float32)


def build_windowed_vector(window_buffer):
    """Construit le vecteur windowed a partir du buffer glissant (WINDOW_SIZE x WINDOW_FEATURE_DIM).

    Le buffer est un deque(maxlen=WINDOW_SIZE) de vecteurs WINDOW_FEATURE_DIM-dim.
    Les positions non encore remplies restent a zero (zero-padding),
    identique au comportement du training pipeline aux frontieres de sequence.

    Args:
        window_buffer: collections.deque de np.arrays WINDOW_FEATURE_DIM-dim, maxlen=WINDOW_SIZE

    Returns:
        np.array de shape (WINDOW_SIZE * WINDOW_FEATURE_DIM,)
    """
    flat = np.zeros(WINDOW_SIZE * WINDOW_FEATURE_DIM, dtype=np.float32)
    n = len(window_buffer)
    start_slot = WINDOW_SIZE - n
    for i, vec in enumerate(window_buffer):
        offset = (start_slot + i) * WINDOW_FEATURE_DIM
        flat[offset:offset + WINDOW_FEATURE_DIM] = vec
    return flat


# ============================================================
# Rendu pygame
# ============================================================

def cm_to_px(x, y):
    """Convertit coordonnees cm en pixels ecran (Y inverse)."""
    return int(MARGIN_X + x * SCALE), int(MARGIN_Y + (MAT_HEIGHT - y) * SCALE)


def _build_offset_polyline(track, offset, use_miter=True):
    """Construit une polyligne decalee de 'offset' cm par rapport a la centerline.

    Args:
        track: Track object
        offset: distance de decalage (positif = gauche, negatif = droite)
        use_miter: True = miter join (comble les coins, bon pour les parcours
                   avec peu de points). False = normale simple (pas de spikes,
                   bon pour les circuits denses en points comme l'oval).
    """
    pts = track.points
    n = len(pts)
    normals = []

    for i in range(len(track.segments)):
        _, _, seg, seg_len = track.segments[i]
        dx, dy = seg[0] / seg_len, seg[1] / seg_len
        normals.append((-dy, dx))

    result = []
    for i in range(n):
        if i == 0:
            nx, ny = normals[0]
        elif i == n - 1 and not track.is_loop:
            nx, ny = normals[-1]
        else:
            idx_prev = (i - 1) % len(normals)
            idx_cur = i % len(normals)
            n1x, n1y = normals[idx_prev]
            n2x, n2y = normals[idx_cur]

            bx = n1x + n2x
            by = n1y + n2y
            b_len = math.sqrt(bx*bx + by*by)

            if b_len < 0.01:
                nx, ny = n2x, n2y
            elif not use_miter:
                # Normale simple: moyenne normalisee, pas de miter
                nx, ny = bx / b_len, by / b_len
            else:
                # Miter join: allonger la bisectrice pour combler les coins
                bx /= b_len
                by /= b_len
                dot = n1x * bx + n1y * by
                dot = max(dot, 0.67)
                miter_len = offset / dot
                result.append((pts[i][0] + bx * miter_len, pts[i][1] + by * miter_len))
                continue

        result.append((pts[i][0] + nx * offset, pts[i][1] + ny * offset))

    return result


def draw_track(screen, track):
    """Dessine le circuit avec des polygones continus pour des courbes propres."""

    # Construire les contours gauche et droit de la route
    # Circuit oval (boucle) = beaucoup de points, pas besoin de miter
    # Parcours procedural = moins de points, miter pour combler les coins
    use_miter = not track.is_loop
    left_edge = _build_offset_polyline(track, ROAD_HALF, use_miter=use_miter)
    right_edge = _build_offset_polyline(track, -ROAD_HALF, use_miter=use_miter)

    # Route: polygone continu (contour gauche + contour droit inverse)
    road_polygon = [cm_to_px(x, y) for x, y in left_edge]
    road_polygon += [cm_to_px(x, y) for x, y in reversed(right_edge)]
    if len(road_polygon) >= 3:
        pygame.draw.polygon(screen, COL_ROAD, road_polygon)

    # Bordures jaunes: lignes continues le long des bords
    left_px = [cm_to_px(x, y) for x, y in left_edge]
    right_px = [cm_to_px(x, y) for x, y in right_edge]
    border_w = max(2, int(BORDER_WIDTH * SCALE))
    if len(left_px) >= 2:
        pygame.draw.lines(screen, COL_BORDER, track.is_loop, left_px, border_w)
        pygame.draw.lines(screen, COL_BORDER, track.is_loop, right_px, border_w)

    # Lignes blanches traitillees le long de la centerline
    along = 0.0
    dot_r = max(1, int(LINE_HALF * SCALE))
    for i in range(len(track.segments)):
        p1, p2, seg, seg_len = track.segments[i]
        steps = max(1, int(seg_len / 0.3))
        for s in range(steps):
            t = s / steps
            px_cm = p1[0] + seg[0] * t
            py_cm = p1[1] + seg[1] * t
            pos_along = along + t * seg_len

            if (pos_along % DASH_PERIOD) < DASH_LENGTH:
                pygame.draw.circle(screen, COL_LINE, cm_to_px(px_cm, py_cm), dot_r)

        along += seg_len


def draw_robot(screen, robot, ir_data=None):
    """Dessine le robot et ses capteurs."""
    cos_t = math.cos(robot.theta)
    sin_t = math.sin(robot.theta)

    # Triangle pour le robot
    front = cm_to_px(robot.x + FRONT_DIST * cos_t, robot.y + FRONT_DIST * sin_t)
    bl = cm_to_px(
        robot.x - BACK_DIST * cos_t + ROBOT_WIDTH/2 * (-sin_t),
        robot.y - BACK_DIST * sin_t + ROBOT_WIDTH/2 * cos_t
    )
    br = cm_to_px(
        robot.x - BACK_DIST * cos_t - ROBOT_WIDTH/2 * (-sin_t),
        robot.y - BACK_DIST * sin_t - ROBOT_WIDTH/2 * cos_t
    )
    pygame.draw.polygon(screen, COL_ROBOT, [front, bl, br])

    # Capteurs IR (points colores)
    if ir_data:
        for pos, val in [(ir_data['pos_l'], ir_data['bot_l']), (ir_data['pos_r'], ir_data['bot_r'])]:
            px = cm_to_px(pos[0], pos[1])
            if val < 130:
                color = COL_SENSOR_LINE  # sur ligne
            elif val > 200:
                color = COL_SENSOR_ROAD  # sur route
            else:
                color = COL_SENSOR_GRASS  # gazon/transition
            pygame.draw.circle(screen, color, px, 4)


def draw_trail(screen, trail):
    """Dessine la trajectoire du robot."""
    if len(trail) < 2:
        return
    pts = [cm_to_px(x, y) for x, y in trail[-500:]]
    pygame.draw.lines(screen, COL_TRAIL, False, pts, 1)


def draw_overlay(screen, robot, ir_data, metrics, fps, paused, sim_speed):
    """Affiche les informations en overlay."""
    font = pygame.font.SysFont('consolas', 14)
    y_offset = 5
    steering = robot.v_left - robot.v_right

    texts = [
        f"L:{robot.v_left:+6.1f}  R:{robot.v_right:+6.1f}  Steer:{steering:+5.1f}",
        f"IR_diff:{ir_data['diff']:+6.0f}  IR_sum:{ir_data['sum']:5.0f}",
        f"On road: {'YES' if ir_data['sum'] > 100 else 'NO'}  Score: {metrics.time_on_road}/{metrics.ticks}",
        f"FPS:{fps:3.0f}  Speed:{sim_speed:.1f}x  Eff_L:{robot.motor_efficiency_left:.3f}  {'PAUSED' if paused else ''}",
    ]

    for text in texts:
        surf = font.render(text, True, COL_TEXT)
        screen.blit(surf, (5, y_offset))
        y_offset += 18


# ============================================================
# Boucle principale
# ============================================================

def run_simulator(script_dir, state, track_mode='loop'):
    """Lance le simulateur 2D."""

    if pygame is None:
        print("\n  [ERREUR] pygame non installe. pip install pygame")
        return

    # Charger le modele
    checkpoints_dir = script_dir / "checkpoints"
    from evaluate import load_model_and_stats
    model, stats = load_model_and_stats(checkpoints_dir)
    if model is None:
        return

    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    motor_efficiency_left = stats.get('motor_efficiency_left', MOTOR_EFFICIENCY_LEFT_DEFAULT)
    print(f"  Motor efficiency (left): {motor_efficiency_left:.3f}")

    # Creer le circuit
    if track_mode == 'loop':
        pts, is_loop = _make_loop_track()
    else:
        pts, is_loop = _make_course_track()

    track = Track(pts, is_loop)
    sensor_model = IRSensorModel(track)

    # Initialiser le robot
    start_pos, start_heading = track.get_start_pos_and_heading()
    robot = SimRobot(start_pos[0], start_pos[1], start_heading,
                     motor_efficiency_left=motor_efficiency_left)

    # Buffer glissant pour fenetre temporelle
    window_buffer = collections.deque(maxlen=WINDOW_SIZE)

    # Metriques
    metrics = SimMetrics()

    # Pygame
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    pygame.display.set_caption(f"Zumi MLP Simulator - {'Boucle' if track_mode == 'loop' else 'Parcours'}")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont('consolas', 14)

    running = True
    paused = False
    sim_speed = 1.0
    fps = 20.0
    ir_data = sensor_model.read_all(robot)

    print(f"\n  Simulateur lance ({track_mode}). Controles:")
    print(f"    SPACE=pause, R=reset, ESC=quitter, 1/2/3=vitesse")
    print(f"    +/-=ajuster motor efficiency gauche ({motor_efficiency_left:.3f})")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_r:
                    robot = SimRobot(start_pos[0], start_pos[1], start_heading,
                                     motor_efficiency_left=robot.motor_efficiency_left)
                    window_buffer.clear()
                    metrics = SimMetrics()
                elif event.key == pygame.K_1:
                    sim_speed = 0.5
                elif event.key == pygame.K_2:
                    sim_speed = 1.0
                elif event.key == pygame.K_3:
                    sim_speed = 2.0
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    robot.motor_efficiency_left = min(1.0, robot.motor_efficiency_left + 0.01)
                    print(f"  Motor efficiency left: {robot.motor_efficiency_left:.3f}")
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    robot.motor_efficiency_left = max(0.80, robot.motor_efficiency_left - 0.01)
                    print(f"  Motor efficiency left: {robot.motor_efficiency_left:.3f}")

        if not paused:
            # Nombre de ticks de simulation par frame
            n_steps = max(1, int(sim_speed))

            for _ in range(n_steps):
                # 1. Capteurs
                ir_data = sensor_model.read_all(robot)
                imu_data = sensor_model.read_imu(robot, SIM_DT)

                # 2. Vecteur 21-dim (detection exclue)
                state_vec = build_state_vector(ir_data, imu_data)

                # 3. Features engineered (21 -> 30)
                prev_vec = window_buffer[-1] if len(window_buffer) > 0 else None
                ir_offset = stats.get('ir_offset_bottom', IR_OFFSET_DEFAULT)
                state_30 = compute_engineered(state_vec, prev_vec, ir_offset, window_buffer)

                # 4. Buffer glissant -> vecteur windowed
                window_buffer.append(state_30.copy())
                full = build_windowed_vector(window_buffer)

                # 5. Z-score + inference
                normalized = ((full - mean) / std).astype(np.float32)
                with torch.no_grad():
                    inp = torch.tensor(normalized).unsqueeze(0)
                    pred = model(inp).numpy()[0]

                left_speed = max(-50, min(50, float(pred[0]) * 50))
                right_speed = max(-50, min(50, float(pred[1]) * 50))

                # 6. Physique
                robot.update(left_speed, right_speed, SIM_DT)

                # 7. Metriques
                _, signed_dist, _, seg_idx = track.closest_point_on_track((robot.x, robot.y))
                on_road = abs(signed_dist) < ROAD_HALF
                turn_angle = track.get_turn_angle_at(seg_idx)
                metrics.record(on_road, signed_dist, robot.speed,
                               left_speed - right_speed, seg_idx, turn_angle,
                               v_left=left_speed, v_right=right_speed)

        # Rendu
        screen.fill(COL_GRASS)
        draw_track(screen, track)
        draw_trail(screen, robot.trail)
        draw_robot(screen, robot, ir_data)
        draw_overlay(screen, robot, ir_data, metrics, fps, paused, sim_speed)

        pygame.display.flip()
        fps = clock.get_fps()
        clock.tick(20)

    pygame.quit()

    # Generer le rapport
    report_text, report_data = metrics.generate_report(track_mode)
    print(report_text)

    # Sauvegarder
    save_dir = script_dir / "simulation_results"
    save_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    report_file = save_dir / f"sim_report_{track_mode}_{ts}.json"
    with open(report_file, 'w') as f:
        json.dump(report_data, f, indent=2)
    print(f"\n  Rapport sauvegarde: {report_file}")

    # Graphiques
    plot_file = save_dir / f"sim_plot_{track_mode}_{ts}.png"
    metrics.generate_plots(plot_file)


# ============================================================
# Menu
# ============================================================

def run_simulator_menu(script_dir, state):
    """Menu de lancement du simulateur."""

    if not state.get('has_model'):
        print("\n  [ERREUR] Aucun modele entraine. Entrainez d'abord un modele (option 3).")
        return

    info = state.get('model_info', {})
    arch = ' -> '.join(map(str, info.get('hidden_dims', [])))

    while True:
        print("\n" + "=" * 60)
        print("  Simulateur 2D")
        print("=" * 60)
        print(f"  Modele: {info.get('input_dim', '?')} -> [{arch}] -> {info.get('output_dim', '?')}")
        print()
        print("  Mode de circuit:")
        print("    [1] Boucle fermee (tourne indefiniment)")
        print("    [2] Parcours depart -> arrivee (inspire du tapis)")
        print("    [R] Retour au menu principal")

        choice = input("\n  Choix : ").strip().upper()

        if choice == '1':
            run_simulator(script_dir, state, track_mode='loop')
            input("\n  Appuyez sur Entree pour continuer...")
        elif choice == '2':
            run_simulator(script_dir, state, track_mode='course')
            input("\n  Appuyez sur Entree pour continuer...")
        elif choice == 'R':
            break
        else:
            print("  Choix invalide.")
