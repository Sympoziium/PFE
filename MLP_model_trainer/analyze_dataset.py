#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'analyse de distribution du dataset d'entraînement.

Analyse la qualité du dataset agrégé et détecte les potentiels problèmes:
- Distribution des commandes moteur
- Valeurs aberrantes
- Statistiques par feature
- Détection du biais de classe (trop de "tout droit" vs réactions aux objets)

Usage:
    python analyze_dataset.py              # Analyse du dataset par défaut
    python analyze_dataset.py --data-dir ./data
"""

import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import spearmanr
from pathlib import Path

from dataset import (classify_actions, ACTION_NAMES, GYRO_Z_INDEX,
                     IR_OFFSET_DEFAULT, GAP_THRESHOLD, OFF_ROAD_THRESHOLD,
                     GRASS_THRESHOLD,
                     OLD_STATE_DIM, INTERMEDIATE_STATE_DIM, NEW_STATE_DIM,
                     ZONE_INSERT_POS, ZONE_FEATURES_DIM)


# ============================================================
# Noms des features du vecteur brut 38-dim (produit par VisionAdapter)
# Source de verite unique pour tous les rapports d'analyse.
# Format: [IR(6), IR_eng(2), Detection(8), IMU(11), Zones(9), Camera(2)] = 38
# ============================================================
RAW_FEATURE_NAMES = [
    # IR raw (0-5)
    "IR_front_right",       # 0
    "IR_bottom_right",      # 1
    "IR_back_right",        # 2
    "IR_bottom_left",       # 3
    "IR_back_left",         # 4
    "IR_front_left",        # 5
    # IR engineered (6-7)
    "IR_diff",              # 6  (bot_left - bot_right)
    "IR_sum",               # 7  (bot_left + bot_right) / 2
    # Detection Haar (8-15, exclue en pratique)
    "detect_flag",          # 8
    "class_stop_sign",      # 9
    "class_pieton",         # 10
    "class_pompier",        # 11
    "bbox_cx",              # 12
    "bbox_cy",              # 13
    "bbox_w",               # 14
    "bbox_h",               # 15
    # IMU (16-26)
    "imu_gyro_x",           # 16
    "imu_gyro_y",           # 17
    "imu_gyro_z",           # 18
    "imu_acc_x",            # 19
    "imu_acc_y",            # 20
    "imu_comp_x",           # 21
    "imu_comp_y",           # 22
    "imu_rot_x",            # 23
    "imu_rot_y",            # 24
    "imu_rot_z",            # 25
    "imu_tilt_state",       # 26
    # Zone features multi-cameras (27-35)
    "front_line_detected",  # 27
    "front_line_confirmed", # 28
    "front_offset_norm",    # 29
    "front_dash_count",     # 30
    "corner_left_detected", # 31
    "corner_right_detected",# 32
    "corner_left_area",     # 33
    "corner_right_area",    # 34
    "center_dash_count",    # 35
    # Ligne camera centre (36-37)
    "line_camera_offset",   # 36
    "line_camera_detected", # 37
]

# Version courte pour les graphiques (axes, legendes)
RAW_FEATURE_NAMES_SHORT = [
    "IR_fr_R", "IR_bot_R", "IR_bck_R", "IR_bot_L", "IR_bck_L", "IR_fr_L",
    "IR_diff", "IR_sum",
    "detect", "cls_stop", "cls_piet", "cls_pomp",
    "bbox_cx", "bbox_cy", "bbox_w", "bbox_h",
    "gyro_x", "gyro_y", "gyro_z", "acc_x", "acc_y",
    "comp_x", "comp_y", "rot_x", "rot_y", "rot_z", "tilt",
    "fr_det", "fr_conf", "fr_off", "fr_dash",
    "cL_det", "cR_det", "cL_area", "cR_area", "ctr_dash",
    "cam_off", "cam_det",
]

assert len(RAW_FEATURE_NAMES) == 38, \
    f"RAW_FEATURE_NAMES doit avoir 38 entrees, a {len(RAW_FEATURE_NAMES)}"
assert len(RAW_FEATURE_NAMES_SHORT) == 38, \
    f"RAW_FEATURE_NAMES_SHORT doit avoir 38 entrees, a {len(RAW_FEATURE_NAMES_SHORT)}"


def load_dataset(data_dir: Path):
    """Charge les fichiers captures.jsonl, labels.jsonl et sequence_ids.jsonl.

    Gere le melange de vecteurs 29-dim (ancien), 36-dim (intermediaire) et 38-dim
    (nouveau) en zero-paddant aux positions semantiquement correctes.
    """
    captures_file = data_dir / "captures.jsonl"
    labels_file = data_dir / "labels.jsonl"
    seqids_file = data_dir / "sequence_ids.jsonl"

    if not captures_file.exists() or not labels_file.exists():
        return None, None, None

    captures = []
    labels = []

    with open(captures_file, 'r') as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                if len(row) == OLD_STATE_DIM:
                    # 29 -> 38: inserer 9 zeros avant les features camera
                    row = (row[:ZONE_INSERT_POS]
                           + [0.0] * ZONE_FEATURES_DIM
                           + row[ZONE_INSERT_POS:])
                elif len(row) == INTERMEDIATE_STATE_DIM:
                    # 36 -> 38: inserer front_dash_count (pos 30) et center_dash_count (pos 35)
                    row = (row[:30]
                           + [0.0]
                           + row[30:34]
                           + [0.0]
                           + row[34:36])
                captures.append(row)

    with open(labels_file, 'r') as f:
        for line in f:
            if line.strip():
                labels.append(json.loads(line))

    # Charger les sequence_ids
    sequence_ids = None
    if seqids_file.exists():
        seq_ids = []
        with open(seqids_file, 'r') as f:
            for line in f:
                if line.strip():
                    seq_ids.append(int(line.strip()))
        if len(seq_ids) == len(captures):
            sequence_ids = np.array(seq_ids, dtype=np.int32)
            print(f"[Dataset] Sequence IDs chargés: {len(np.unique(sequence_ids))} séquences")
        else:
            print(f"[WARN] sequence_ids.jsonl incompatible ({len(seq_ids)} vs {len(captures)})")

    return np.array(captures, dtype=np.float32), np.array(labels, dtype=np.float32), sequence_ids


def analyze_dataset(captures, labels, save_dir=None, sequence_ids=None):
    """Analyse en détail le dataset."""

    print("[*] Analyse du Dataset")
    print("=" * 70)
    print()

    # === INFORMATIONS GENERALES ===
    print("[INFO] Dimensions:")
    print(f"  Captures: {captures.shape}")
    print(f"  Labels: {labels.shape}")
    print(f"  Nombre d'echantillons: {len(captures)}")
    print()

    # === ANALYSE DES COMMANDES MOTEUR (LABELS) ===
    print("[STATS] Commandes Moteur (Labels):")
    print(f"  Roue Gauche:")
    print(f"    Min: {labels[:, 0].min():.4f}")
    print(f"    Max: {labels[:, 0].max():.4f}")
    print(f"    Mean: {labels[:, 0].mean():.4f}")
    print(f"    Std: {labels[:, 0].std():.4f}")
    print(f"  Roue Droite:")
    print(f"    Min: {labels[:, 1].min():.4f}")
    print(f"    Max: {labels[:, 1].max():.4f}")
    print(f"    Mean: {labels[:, 1].mean():.4f}")
    print(f"    Std: {labels[:, 1].std():.4f}")
    print()

    # === DETECTION DU BIAIS DE CLASSE ===
    # Seuil pour détecter "tout droit" : les deux roues presque égales et proches de 0
    threshold_straight = 0.1
    both_wheels_low = np.sum((np.abs(labels[:, 0]) > threshold_straight) &
                            (np.abs(labels[:, 1]) > threshold_straight))
    total_straight_pct = (len(labels) - both_wheels_low) / len(labels) * 100

    print(f"[BIAS] Distribution des actions:")
    print(f"  'Tout droit' (|V_left| > 0.1 ET |V_right| > 0.1): {len(labels) - both_wheels_low:6d} ({total_straight_pct:5.1f}%)")
    print(f"  Actions complexes: {both_wheels_low:6d} ({100 - total_straight_pct:5.1f}%)")

    if total_straight_pct > 85:
        print(f"  [WARN] Biais important vers 'tout droit'! Le modele risque de sur-apprendre cette action.")
    print()

    # === ANALYSE DES CAPTURES (FEATURES ENTREE) ===
    n_features = captures.shape[1]
    print(f"[STATS] Features d'entree (Captures) - {n_features} dimensions:")
    # Utilise le mapping centralise pour le vecteur brut 38-dim
    feature_names = list(RAW_FEATURE_NAMES)

    # Support des anciens datasets (sans all engineered features)
    for i in range(captures.shape[1]):
        feature_data = captures[:, i]
        name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
        print(f"  [{i:2d}] {name:20s} - "
              f"Min: {feature_data.min():7.4f}, Max: {feature_data.max():7.4f}, "
              f"Mean: {feature_data.mean():7.4f}, Std: {feature_data.std():7.4f}")

    print()

    # === FEATURES MORTES ===
    dead_threshold = 1e-6
    dead_features = []
    for i in range(n_features):
        if captures[:, i].std() < dead_threshold:
            dead_features.append(i)

    if dead_features:
        print(f"[DEAD] Features mortes (std < {dead_threshold}):")
        for i in dead_features:
            name = feature_names[i] if i < len(feature_names) else f"feature_{i}"
            print(f"  [{i:2d}] {name:20s} - valeur constante: {captures[:, i].mean():.4f}")
        print(f"  [WARN] {len(dead_features)} features n'apportent aucune information.")
        print(f"         Elles occupent de la capacite du modele pour rien.")
    else:
        print(f"[DEAD] Aucune feature morte detectee.")
    print()

    # === DETECTION DE VALEURS ABERRANTES ===
    print("[OUTLIERS] Detection de valeurs aberrantes:")

    # Les features doivent etre normalisees entre [-1, 1]
    out_of_bounds = 0
    out_of_bounds_details = []
    
    # Vérifier les plages brutes pour chaque groupe de features
    # [0-5]: IR sensors (0-255)
    ir_oob = np.sum((captures[:, 0:6] < 0) | (captures[:, 0:6] > 255))
    out_of_bounds += ir_oob
    if ir_oob > 0:
        out_of_bounds_details.append(f"IR sensors (0-255): {ir_oob}")
    
    # [6-7]: IR engineered (raw values, large range possible)
    ir_eng_oob = np.sum(np.abs(captures[:, 6:8]) > 255)
    out_of_bounds += ir_eng_oob
    if ir_eng_oob > 0:
        out_of_bounds_details.append(f"IR engineered (|x| > 255): {ir_eng_oob}")
    
    # [8]: detection flag (0 ou 1)
    detect_oob = np.sum((captures[:, 8] < 0) | (captures[:, 8] > 1))
    out_of_bounds += detect_oob
    if detect_oob > 0:
        out_of_bounds_details.append(f"Detection flag (0-1): {detect_oob}")
    
    # [9 à 9+N_classes]: class one-hot (0 ou 1)
    n_classes = 3  # stop_sign, pieton, pompier
    class_oob = np.sum((captures[:, 9:9+n_classes] < 0) | (captures[:, 9:9+n_classes] > 1))
    out_of_bounds += class_oob
    if class_oob > 0:
        out_of_bounds_details.append(f"Class one-hot (0-1): {class_oob}")
    
    # [9+N_classes à 13+N_classes]: bbox normalized (0-1)
    bbox_oob = np.sum((captures[:, 9+n_classes:13+n_classes] < 0) | (captures[:, 9+n_classes:13+n_classes] > 1))
    out_of_bounds += bbox_oob
    if bbox_oob > 0:
        out_of_bounds_details.append(f"BBox normalized (0-1): {bbox_oob}")
    
    # [13+N_classes à 23+N_classes]: IMU raw (angles en degrés, plage [-360, 360])
    imu_oob = np.sum(np.abs(captures[:, 13+n_classes:13+n_classes+10]) > 360)
    out_of_bounds += imu_oob
    if imu_oob > 0:
        out_of_bounds_details.append(f"IMU angles (|-360, 360|): {imu_oob}")
    
    # [23+N_classes]: tilt_state (-1 à 7)
    tilt_oob = np.sum((captures[:, 13+n_classes+10] < -2) | (captures[:, 13+n_classes+10] > 8))
    out_of_bounds += tilt_oob
    if tilt_oob > 0:
        out_of_bounds_details.append(f"Tilt state (-1 à 7): {tilt_oob}")

    # === Zone features (indices 27-35) — plages attendues ===
    # Verifie seulement si le vecteur est au nouveau format 38-dim
    if captures.shape[1] >= 38:
        # Booleens {0, 1} : front_det(27), front_conf(28), cL_det(31), cR_det(32)
        bool_indices = [27, 28, 31, 32]
        bool_oob = 0
        for idx in bool_indices:
            bool_oob += int(np.sum((captures[:, idx] < -0.01) | (captures[:, idx] > 1.01)))
        if bool_oob > 0:
            out_of_bounds_details.append(f"Zone booleens {{0,1}}: {bool_oob}")
            out_of_bounds += bool_oob

        # front_offset_norm (29): [-1, 1]
        front_off_oob = int(np.sum((captures[:, 29] < -1.01) | (captures[:, 29] > 1.01)))
        if front_off_oob > 0:
            out_of_bounds_details.append(f"front_offset_norm [-1,1]: {front_off_oob}")
            out_of_bounds += front_off_oob

        # Aires et dash counts normalises [0, 1] : indices 30, 33, 34, 35
        norm_indices = [30, 33, 34, 35]
        norm_oob = 0
        for idx in norm_indices:
            norm_oob += int(np.sum((captures[:, idx] < -0.01) | (captures[:, idx] > 1.01)))
        if norm_oob > 0:
            out_of_bounds_details.append(f"Zone aires/counts [0,1]: {norm_oob}")
            out_of_bounds += norm_oob

        # === Line camera (indices 36-37) ===
        # line_camera_offset (36): [-1, 1]
        cam_off_oob = int(np.sum((captures[:, 36] < -1.01) | (captures[:, 36] > 1.01)))
        if cam_off_oob > 0:
            out_of_bounds_details.append(f"line_camera_offset [-1,1]: {cam_off_oob}")
            out_of_bounds += cam_off_oob

        # line_camera_detected (37): {0, 1}
        cam_det_oob = int(np.sum((captures[:, 37] < -0.01) | (captures[:, 37] > 1.01)))
        if cam_det_oob > 0:
            out_of_bounds_details.append(f"line_camera_detected {{0,1}}: {cam_det_oob}")
            out_of_bounds += cam_det_oob

    print(f"  Valeurs hors limites attendues: {out_of_bounds}")
    if out_of_bounds_details:
        print(f"  [WARN] Valeurs aberrantes detectees:")
        for detail in out_of_bounds_details:
            print(f"    - {detail}")
    else:
        print(f"  [OK] Toutes les valeurs sont dans les plages attendues (raw)")

    # Vérifier les NaN
    nan_count = np.sum(np.isnan(captures)) + np.sum(np.isnan(labels))
    if nan_count > 0:
        print(f"  [WARN] {nan_count} valeurs NaN detectees!")
    else:
        print(f"  [OK] Aucune valeur NaN")

    print()

    # === DOUBLONS / QUASI-DOUBLONS ===
    # Seuls les groupes >= min_run_length sont consideres comme de vrais doublons.
    # Les paires courtes (2-3 echantillons similaires) sont normales a ~80ms de
    # sampling: commande maintenue, virage constant, temps de reaction humain.
    print("[DUPLICATES] Detection de quasi-doublons consecutifs:")
    n_duplicates = 0
    min_run_length = 5  # aligne avec dataset.deduplicate()
    if len(captures) > 1:
        diffs = np.linalg.norm(captures[1:] - captures[:-1], axis=1)
        dup_threshold = 1e-4
        is_dup = diffs < dup_threshold

        # Identifier les groupes (runs) de doublons consecutifs
        runs = []
        run_start = None
        for i in range(len(is_dup)):
            if is_dup[i]:
                if run_start is None:
                    run_start = i  # i = dernier original, i+1 = premier doublon
            else:
                if run_start is not None:
                    runs.append((run_start, i))  # run_start..i inclus
                    run_start = None
        if run_start is not None:
            runs.append((run_start, len(captures) - 1))

        run_lengths = [end - start + 1 for start, end in runs]
        total_similar_pairs = int(np.sum(is_dup))

        # Separer les groupes courts (normaux) des groupes longs (vrais doublons)
        short_runs = [(l, s, e) for l, (s, e) in zip(run_lengths, runs) if l < min_run_length]
        long_runs = [(l, s, e) for l, (s, e) in zip(run_lengths, runs) if l >= min_run_length]
        n_short_samples = sum(l - 1 for l, _, _ in short_runs)  # samples qui seraient retires
        n_long_samples = sum(l - 1 for l, _, _ in long_runs)
        n_duplicates = n_long_samples  # seuls les longs groupes sont retires

        print(f"  Paires consecutives similaires (||delta|| < {dup_threshold}): {total_similar_pairs}")
        print(f"  Distance moyenne entre consecutifs: {diffs.mean():.6f}")
        print(f"  Distance mediane: {np.median(diffs):.6f}")
        print()

        # Distribution par taille de groupe
        print(f"  Distribution par taille de groupe:")
        if run_lengths:
            length_arr = np.array(run_lengths)
            bins = [(2, 2, "2 (paire)"), (3, 4, "3-4"), (5, 9, "5-9"), (10, 99, "10+")]
            for lo, hi, label in bins:
                mask = (length_arr >= lo) & (length_arr <= hi)
                count = int(np.sum(mask))
                samples_in = int(np.sum(length_arr[mask] - 1))  # echantillons redondants
                marker = " <- retires" if lo >= min_run_length else " <- conserves (signal valide)"
                print(f"    Taille {label:10s}: {count:5d} groupes ({samples_in:5d} echantillons){marker}")
        print()

        # Details sur les groupes longs (ceux qui seront effectivement retires)
        if long_runs:
            print(f"  [DEDUP] Groupes retires a l'entrainement (>= {min_run_length} samples): "
                  f"{len(long_runs)} groupes, {n_long_samples} echantillons")

            # Breakdown par action (via IMU gyro_z)
            # Classifier chaque echantillon du dataset, puis compter par groupe
            all_categories = classify_actions(captures, labels, sequence_ids=sequence_ids)
            long_run_cat_counts = {name: 0 for name in ACTION_NAMES}
            for length, start, end in long_runs:
                # Action dominante du groupe = mode des categories
                grp_cats = all_categories[start:end+1]
                dominant = int(np.bincount(grp_cats, minlength=5).argmax())
                long_run_cat_counts[ACTION_NAMES[dominant]] += length - 1

            print(f"  Repartition des doublons retires par action (IMU-based):")
            for name, count in long_run_cat_counts.items():
                pct = count / n_long_samples * 100 if n_long_samples > 0 else 0
                bar = "#" * int(pct / 2)
                print(f"    {name:18s}: {count:5d} ({pct:5.1f}%) {bar}")

            # Top 5 plus grands groupes
            top_long = sorted(long_runs, reverse=True)[:5]
            print(f"\n  Top 5 plus grands groupes:")
            for length, start, end in top_long:
                grp_left = labels[start:end+1, 0].mean()
                grp_right = labels[start:end+1, 1].mean()
                grp_gyro_z = captures[start:end+1, GYRO_Z_INDEX].mean()
                dominant = int(np.bincount(all_categories[start:end+1], minlength=5).argmax())
                action = ACTION_NAMES[dominant]
                print(f"      idx [{start:5d}-{end:5d}] ({length:4d} samples) "
                      f"action={action:10s} V_left={grp_left:+.4f} V_right={grp_right:+.4f} "
                      f"gyro_z={grp_gyro_z:+.1f} deg/s")
        else:
            print(f"  [OK] Aucun groupe de >= {min_run_length} echantillons identiques consecutifs.")
            print(f"       Toutes les similarites sont des commandes maintenues (signal valide).")
            n_duplicates = 0

        print()
        if n_duplicates > 0:
            dup_pct = n_duplicates / len(captures) * 100
            print(f"  [INFO] {n_duplicates} echantillons a retirer ({dup_pct:.1f}% du dataset)")
            print(f"         {n_short_samples} echantillons similaires conserves (groupes < {min_run_length})")
        else:
            print(f"  [OK] Pas de stagnation significative detectee.")
    print()

    # === SAUTS BRUSQUES DANS LES LABELS ===
    print("[JUMPS] Detection de sauts brusques dans les commandes moteur:")
    if len(labels) > 1:
        label_diffs = np.abs(labels[1:] - labels[:-1])
        jump_threshold = 0.3
        jumps_left = np.sum(label_diffs[:, 0] > jump_threshold)
        jumps_right = np.sum(label_diffs[:, 1] > jump_threshold)
        total_transitions = len(labels) - 1
        print(f"  Seuil de saut: |delta| > {jump_threshold}")
        print(f"  Sauts roue gauche:  {jumps_left:5d} ({jumps_left/total_transitions*100:.1f}%)")
        print(f"  Sauts roue droite:  {jumps_right:5d} ({jumps_right/total_transitions*100:.1f}%)")
        max_jump_left = label_diffs[:, 0].max()
        max_jump_right = label_diffs[:, 1].max()
        print(f"  Plus grand saut: gauche={max_jump_left:.4f}, droite={max_jump_right:.4f}")
        jump_pct = max(jumps_left, jumps_right) / total_transitions * 100
        if jump_pct > 15:
            print(f"  [WARN] Beaucoup de transitions brusques. Verifier la qualite")
            print(f"         de la telecommande ou le taux d'echantillonnage.")
        else:
            print(f"  [OK] Transitions globalement lisses.")
    print()

    # === DETECTION DES ARRETS PWM ===
    stop_thresh = 0.02
    left_lbl = labels[:, 0]
    right_lbl = labels[:, 1]
    is_stop_lbl = (np.abs(left_lbl) < stop_thresh) & (np.abs(right_lbl) < stop_thresh)
    total_stops = int(is_stop_lbl.sum())

    # Compter les arrets PWM isoles (1 tick entre deux commandes non-nulles)
    n_pwm = 0
    for i in range(1, len(labels) - 1):
        if not is_stop_lbl[i]:
            continue
        if sequence_ids is not None:
            if sequence_ids[i] != sequence_ids[i - 1] or sequence_ids[i] != sequence_ids[i + 1]:
                continue
        if not is_stop_lbl[i - 1] and not is_stop_lbl[i + 1]:
            n_pwm += 1

    n_real_stops = total_stops - n_pwm
    print(f"[PWM] Analyse des arrets:")
    print(f"  Total arrets (labels ~0):       {total_stops:6d} ({total_stops/len(labels)*100:.1f}%)")
    print(f"  Arrets PWM isoles (artefacts):  {n_pwm:6d} ({n_pwm/len(labels)*100:.1f}%)")
    print(f"  Vrais arrets (2+ consecutifs):  {n_real_stops:6d} ({n_real_stops/len(labels)*100:.1f}%)")
    if n_pwm > 0:
        print(f"  [INFO] {n_pwm} arrets PWM seront retires par remove_pwm_stops() a l'entrainement")
    print()

    # === CATEGORISATION FINE DES ACTIONS ===
    # Utilise le gyroscope (gyro_z) pour detecter les rotations reelles
    # plutot que les commandes moteur (biaisees par le PID de cap).
    print("[ACTIONS] Categorisation fine des actions (IMU-based, gyro_z):")
    action_categories = classify_actions(captures, labels, sequence_ids=sequence_ids)
    categories = {}
    for i, name in enumerate(ACTION_NAMES):
        categories[name] = int(np.sum(action_categories == i))

    for name, count in categories.items():
        pct = count / len(labels) * 100
        bar = "#" * int(pct / 2)
        print(f"  {name:18s}: {count:5d} ({pct:5.1f}%) {bar}")

    print()

    # === VISION ANALYSIS ===
    print("[VISION] Analyse des détections:")
    vision_flag = captures[:, 8]  # feature "detect_flag"
    nb_detections = np.sum(vision_flag > 0.5)
    detection_pct = (nb_detections / len(captures)) * 100
    print(f"  Echantillons avec detection: {nb_detections:6d} ({detection_pct:5.1f}%)")
    print(f"  Echantillons sans detection: {len(captures) - nb_detections:6d} ({100 - detection_pct:5.1f}%)")

    if detection_pct < 10:
        print(f"  [WARN] Peu de donnees avec detection d'objets! (~{detection_pct:.1f}%)")
        print(f"         Cela peut biaiser l'apprentissage vers 'tout droit'.")

    print()

    # === CORRELATION FEATURES-LABELS (Pearson) ===
    print("[CORR] Correlation Pearson features-labels (relations lineaires):")
    active_features = [i for i in range(n_features) if i not in dead_features]
    corr_left = []
    corr_right = []
    for i in active_features:
        cl = np.corrcoef(captures[:, i], labels[:, 0])[0, 1]
        cr = np.corrcoef(captures[:, i], labels[:, 1])[0, 1]
        corr_left.append((i, cl))
        corr_right.append((i, cr))

    corr_left.sort(key=lambda x: abs(x[1]), reverse=True)
    corr_right.sort(key=lambda x: abs(x[1]), reverse=True)

    def _fname(idx):
        return feature_names[idx] if idx < len(feature_names) else f"feature_{idx}"

    print(f"  Top correlations avec roue gauche:")
    for i, c in corr_left[:5]:
        print(f"    [{i:2d}] {_fname(i):20s}: {c:+.4f}")
    print(f"  Top correlations avec roue droite:")
    for i, c in corr_right[:5]:
        print(f"    [{i:2d}] {_fname(i):20s}: {c:+.4f}")

    uncorrelated = [i for i in active_features
                    if abs(np.corrcoef(captures[:, i], labels[:, 0])[0, 1]) < 0.02
                    and abs(np.corrcoef(captures[:, i], labels[:, 1])[0, 1]) < 0.02]
    if uncorrelated:
        print(f"  [INFO] Features sans correlation lineaire avec les labels (<0.02):")
        for i in uncorrelated:
            print(f"    [{i:2d}] {_fname(i)}")

    print()

    # === ANALYSE DIFFERENTIELLE IR (line following) ===
    # Les capteurs IR bottom servent a suivre la ligne. Pearson les sous-estime
    # car IR_bot_left pousse a droite et IR_bot_right pousse a gauche: les effets
    # s'annulent dans la correlation individuelle. Le differentiel les revele.
    print("[IR-DIFF] Analyse differentielle des capteurs IR bottom (line following):")
    ir_bot_right = captures[:, 1]  # IR_bottom_right
    ir_bot_left  = captures[:, 3]  # IR_bottom_left
    ir_diff = ir_bot_left - ir_bot_right  # positif = ligne a droite -> tourner a droite
    left = labels[:, 0]
    right = labels[:, 1]
    steering_cmd = left - right            # positif = tourne a droite

    corr_diff_steering = np.corrcoef(ir_diff, steering_cmd)[0, 1]
    corr_diff_left = np.corrcoef(ir_diff, labels[:, 0])[0, 1]
    corr_diff_right = np.corrcoef(ir_diff, labels[:, 1])[0, 1]

    print(f"  IR_diff (bot_left - bot_right) vs steering (V_left - V_right): {corr_diff_steering:+.4f}")
    print(f"  IR_diff vs roue gauche: {corr_diff_left:+.4f}")
    print(f"  IR_diff vs roue droite: {corr_diff_right:+.4f}")

    if abs(corr_diff_steering) > 0.15:
        print(f"  [OK] Les IR bottom ont une bonne influence differentielle sur le steering.")
    elif abs(corr_diff_steering) > 0.05:
        print(f"  [INFO] Correlation moderee. Le robot reagit aux IR mais pas fortement.")
    else:
        print(f"  [WARN] Faible correlation IR bottom <-> steering.")
        print(f"         Le robot ne semble pas utiliser les capteurs de ligne efficacement.")

    # Spearman (rang) pour capturer les relations non-lineaires
    spear_ir_diff, _ = spearmanr(ir_diff, steering_cmd)
    print(f"  Spearman IR_diff vs steering: {spear_ir_diff:+.4f} (capte les relations non-lineaires)")

    print()

    # === FEATURES ENGINEERED ===
    print("[ENGINEERED] Analyse des features de suivi de ligne (calculees a la volee):")
    ir_bot_l = captures[:, 3]
    ir_bot_r = captures[:, 1]
    line_pos = (ir_bot_l - ir_bot_r) / (ir_bot_l + ir_bot_r + 1e-6)
    line_conf = np.abs(ir_bot_l - ir_bot_r) / ((ir_bot_l + ir_bot_r) / 2 + 1e-6)

    corr_pos_steering = np.corrcoef(line_pos, steering_cmd)[0, 1]
    corr_conf_abs_steering = np.corrcoef(line_conf, np.abs(steering_cmd))[0, 1]
    spear_pos, _ = spearmanr(line_pos, steering_cmd)

    print(f"  line_position (normalise): mean={line_pos.mean():.4f}, std={line_pos.std():.4f}")
    print(f"  line_confidence:           mean={line_conf.mean():.4f}, std={line_conf.std():.4f}")
    print(f"  Pearson  line_pos vs steering:    {corr_pos_steering:+.4f}")
    print(f"  Spearman line_pos vs steering:    {spear_pos:+.4f}")
    print(f"  Pearson  line_conf vs |steering|: {corr_conf_abs_steering:+.4f}")
    print(f"  (comparaison IR_diff brut Pearson: {corr_diff_steering:+.4f})")
    if abs(corr_pos_steering) > abs(corr_diff_steering):
        print(f"  [OK] line_position ameliore la correlation vs IR_diff brut "
              f"({abs(corr_pos_steering):.4f} > {abs(corr_diff_steering):.4f})")
    else:
        print(f"  [INFO] line_position n'ameliore pas la correlation lineaire vs IR_diff brut")
    print()

    # === PID-FEATURES: Analyse des 8 features engineered du pipeline ===
    print("[PID-FEATURES] Analyse des features PID-inspired (pipeline 95-dim):")
    ir_bot_r_raw = captures[:, 1]
    ir_bot_l_raw = captures[:, 3]
    ir_front_r_raw = captures[:, 0]
    ir_front_l_raw = captures[:, 5]
    ir_sum_raw = (ir_bot_l_raw + ir_bot_r_raw) / 2.0
    gyro_z_raw = captures[:, GYRO_Z_INDEX]

    # 27: calibrated_error
    pid_cal_error = (ir_bot_r_raw - ir_bot_l_raw) - (-IR_OFFSET_DEFAULT)

    # 28: line_visible
    pid_line_visible = (ir_sum_raw < GAP_THRESHOLD).astype(np.float32)

    # 29: cal_error_norm
    pid_cal_error_norm = pid_cal_error / (ir_sum_raw + 1e-6)

    # 30: approaching_line (with boundary detection via sequence_ids)
    pid_abs_error = np.abs(pid_cal_error)
    pid_abs_error_prev = np.zeros_like(pid_abs_error)
    pid_abs_error_prev[1:] = pid_abs_error[:-1]
    pid_approaching = np.where(pid_abs_error < pid_abs_error_prev, 1.0, -1.0).astype(np.float32)
    pid_boundaries = np.zeros(len(captures), dtype=bool)
    pid_boundaries[0] = True
    if sequence_ids is not None:
        pid_boundaries[1:] = sequence_ids[1:] != sequence_ids[:-1]
    else:
        pid_error_jumps = np.abs(pid_cal_error[1:] - pid_cal_error[:-1])
        pid_boundaries[1:] = pid_error_jumps > 100.0
    pid_approaching[pid_boundaries] = 0.0

    # 31: on_road
    pid_on_road = (ir_sum_raw > OFF_ROAD_THRESHOLD).astype(np.float32)

    # 32: grass_detect
    pid_grass_detect = (np.minimum(ir_front_l_raw, ir_front_r_raw) < GRASS_THRESHOLD).astype(np.float32)

    # 33: gyro_z_rate (with boundary detection via sequence_ids)
    pid_gyro_z_rate = np.zeros(len(captures), dtype=np.float32)
    pid_gyro_z_rate[1:] = gyro_z_raw[1:] - gyro_z_raw[:-1]
    if sequence_ids is not None:
        gyro_boundaries = np.zeros(len(captures), dtype=bool)
        gyro_boundaries[0] = True
        gyro_boundaries[1:] = sequence_ids[1:] != sequence_ids[:-1]
        pid_gyro_z_rate[gyro_boundaries] = 0.0
    else:
        pid_gyro_boundaries = np.abs(pid_gyro_z_rate) > 150.0
        pid_gyro_z_rate[pid_gyro_boundaries] = 0.0

    # 34: heading_drift
    pid_heading_drift = pid_gyro_z_rate * (1.0 - pid_line_visible)

    pid_features = {
        "calibrated_error": pid_cal_error,
        "line_visible": pid_line_visible,
        "cal_error_norm": pid_cal_error_norm,
        "approaching_line": pid_approaching,
        "on_road": pid_on_road,
        "grass_detect": pid_grass_detect,
        "gyro_z_rate": pid_gyro_z_rate,
        "heading_drift": pid_heading_drift,
    }

    print(f"  {'Feature':22s} {'mean':>8s} {'std':>8s} {'Pearson':>8s} {'Spearman':>9s}")
    print(f"  {'-'*22} {'-'*8} {'-'*8} {'-'*8} {'-'*9}")
    for fname, fdata in pid_features.items():
        pearson_r = np.corrcoef(fdata, steering_cmd)[0, 1]
        spearman_r, _ = spearmanr(fdata, steering_cmd)
        print(f"  {fname:22s} {fdata.mean():+8.4f} {fdata.std():8.4f} {pearson_r:+8.4f} {spearman_r:+9.4f}")
    print()

    # Comparison: calibrated_error vs raw ir_diff (index 6)
    raw_ir_diff = captures[:, 6]
    pearson_raw_ir_diff = np.corrcoef(raw_ir_diff, steering_cmd)[0, 1]
    spearman_raw_ir_diff, _ = spearmanr(raw_ir_diff, steering_cmd)
    pearson_cal_error = np.corrcoef(pid_cal_error, steering_cmd)[0, 1]
    spearman_cal_error, _ = spearmanr(pid_cal_error, steering_cmd)

    print(f"  Comparaison calibrated_error vs ir_diff brut (index 6):")
    print(f"    {'':22s} {'Pearson':>8s} {'Spearman':>9s}")
    print(f"    {'ir_diff (raw)':22s} {pearson_raw_ir_diff:+8.4f} {spearman_raw_ir_diff:+9.4f}")
    print(f"    {'calibrated_error':22s} {pearson_cal_error:+8.4f} {spearman_cal_error:+9.4f}")
    pearson_improvement = abs(pearson_cal_error) - abs(pearson_raw_ir_diff)
    spearman_improvement = abs(spearman_cal_error) - abs(spearman_raw_ir_diff)
    print(f"    Amelioration Pearson:  {pearson_improvement:+.4f}")
    print(f"    Amelioration Spearman: {spearman_improvement:+.4f}")
    if pearson_improvement > 0:
        print(f"    [OK] calibrated_error ameliore la correlation Pearson vs ir_diff brut")
    else:
        print(f"    [INFO] calibrated_error n'ameliore pas la correlation Pearson vs ir_diff brut")
    print()

    # Mode-conditional analysis: line_visible == 1 vs line_visible == 0
    mask_line = pid_line_visible == 1.0
    mask_gap = pid_line_visible == 0.0
    n_line = int(mask_line.sum())
    n_gap = int(mask_gap.sum())

    print(f"  Analyse conditionnelle par mode:")
    print(f"    line_visible=1 (ligne presente): {n_line} echantillons ({n_line/len(captures)*100:.1f}%)")
    print(f"    line_visible=0 (gap/pas de ligne): {n_gap} echantillons ({n_gap/len(captures)*100:.1f}%)")
    print()

    for mode_name, mask in [("line_visible=1", mask_line), ("line_visible=0", mask_gap)]:
        if mask.sum() < 10:
            print(f"    [{mode_name}] Pas assez d'echantillons pour l'analyse.")
            continue
        print(f"    [{mode_name}] Correlations vs steering_cmd:")
        print(f"      {'Feature':22s} {'Pearson':>8s} {'Spearman':>9s}")
        print(f"      {'-'*22} {'-'*8} {'-'*9}")
        steering_sub = steering_cmd[mask]
        for fname, fdata in pid_features.items():
            fdata_sub = fdata[mask]
            if fdata_sub.std() < 1e-8:
                print(f"      {fname:22s} {'N/A':>8s} {'N/A':>9s}  (variance nulle)")
                continue
            p_r = np.corrcoef(fdata_sub, steering_sub)[0, 1]
            s_r, _ = spearmanr(fdata_sub, steering_sub)
            print(f"      {fname:22s} {p_r:+8.4f} {s_r:+9.4f}")
        print()

    # === TEST D'IMPACT DES FEATURES ===
    print("[FEATURE-IMPACT] Evaluation rapide de l'apport des features engineered:")
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import cross_val_score

        base_features = captures[:, [0, 1, 2, 3, 4, 5, 6, 7]]
        enriched_features = np.column_stack([base_features, line_pos, line_conf])

        for feat_name, X in [("IR bruts (8 feat)", base_features),
                              ("IR + engineered (10 feat)", enriched_features)]:
            scores = cross_val_score(LinearRegression(), X, labels, cv=5, scoring='r2')
            print(f"  {feat_name:30s}: R2={scores.mean():.4f} (+/- {scores.std():.4f})")
        print()
    except ImportError:
        print("  [SKIP] sklearn non disponible, test d'impact ignore.")
        print()

    # === ECHELLE DES LABELS ===
    label_max = max(abs(labels.min()), abs(labels.max()))
    print(f"[SCALE] Echelle des labels:")
    print(f"  Max |label| = {label_max:.4f} (vitesse max={label_max*50:.1f} avec MOTOR_SPEED_MAX=50)")
    print()

    # === RECOMMANDATIONS ===
    print("[RECOMMEND] Recommandations pour l'entrainement:")
    if total_straight_pct > 85 and detection_pct < 10:
        print("  * PRIORITE HAUTE: Recollecter plus de sequences avec objets!")
        print("    Le dataset est trop biaise vers 'tout droit'.")
        print("    Collectez des sequences specifiques pour:")
        print("      - Arret devant pieton")
        print("      - Arret au panneau stop")
        print("      - Evitement camion pompier")
    elif total_straight_pct > 80:
        print("  * Echantillonnage equilibre actif (WeightedRandomSampler)")
    else:
        print("  * Dataset bien equilibre")

    if dead_features:
        print(f"  * {len(dead_features)} features mortes (retirees par le pipeline via feature_mask)")
    if n_duplicates > 0:
        print(f"  * {n_duplicates} doublons detectes (retires par dataset.deduplicate() a l'entrainement)")
    print(f"  * Dataset effectif apres dedup: ~{len(captures) - n_duplicates} echantillons")

    print()
    print("=" * 70)

    return {
        "n_samples": len(captures),
        "straight_pct": total_straight_pct,
        "detection_pct": detection_pct,
        "out_of_bounds": out_of_bounds,
        "nan_count": nan_count,
        "n_duplicates": n_duplicates,
        "n_dead_features": len(dead_features),
        "categories": categories,
    }


def plot_analysis(captures, labels, save_dir=None, sequence_ids=None):
    """Crée des visualisations du dataset."""

    # Utilise les noms courts centralises (38-dim)
    feature_names = list(RAW_FEATURE_NAMES_SHORT)

    if save_dir:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

    # === Figure 1: Distribution des commandes moteur ===
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].hist(labels[:, 0], bins=50, alpha=0.7, label='Roue Gauche', edgecolor='black')
    axes[0].axvline(labels[:, 0].mean(), color='r', linestyle='--', linewidth=2, label='Mean')
    axes[0].set_xlabel('Vitesse normalisee [-1, 1]')
    axes[0].set_ylabel('Frequence')
    axes[0].set_title('Distribution Roue Gauche')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].hist(labels[:, 1], bins=50, alpha=0.7, label='Roue Droite', color='orange', edgecolor='black')
    axes[1].axvline(labels[:, 1].mean(), color='r', linestyle='--', linewidth=2, label='Mean')
    axes[1].set_xlabel('Vitesse normalisee [-1, 1]')
    axes[1].set_ylabel('Frequence')
    axes[1].set_title('Distribution Roue Droite')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "motor_commands_distribution.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: motor_commands_distribution.png")
    plt.close()

    # === Figure 2: Correlation Gauche-Droite ===
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(labels[:, 0], labels[:, 1], alpha=0.3, s=20)
    ax.axhline(y=0, color='k', linestyle='-', linewidth=0.5)
    ax.axvline(x=0, color='k', linestyle='-', linewidth=0.5)
    ax.set_xlabel('Vitesse Roue Gauche')
    ax.set_ylabel('Vitesse Roue Droite')
    ax.set_title('Correlation Moteurs Gauche-Droite')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(-1.1, 1.1)
    ax.set_ylim(-1.1, 1.1)
    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "motor_correlation.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: motor_correlation.png")
    plt.close()

    # === Figure 3: Statistiques des IR sensors ===
    fig, ax = plt.subplots(figsize=(10, 5))
    ir_stats = []
    ir_names = ['Frnt_R', 'Bot_R', 'Back_R', 'Bot_L', 'Back_L', 'Frnt_L']
    for i in range(6):
        ir_stats.append(captures[:, i].mean())

    bars = ax.bar(ir_names, ir_stats, color='skyblue', edgecolor='black')
    ax.set_ylabel('Valeur moyenne normalisee')
    ax.set_title('Moyennes des Capteurs IR')
    ax.set_ylim(0, 255)
    ax.grid(True, alpha=0.3, axis='y')

    for bar, val in zip(bars, ir_stats):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{val:.2f}', ha='center', va='bottom')

    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "ir_sensors_stats.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: ir_sensors_stats.png")
    plt.close()

    # === Figure 4: Matrice de correlation globale (features actives + labels) ===
    n_features = captures.shape[1]
    active_idx = [i for i in range(n_features) if captures[:, i].std() > 1e-6]
    active_names = [feature_names[i] if i < len(feature_names) else f"f{i}" for i in active_idx]
    all_names = active_names + ["V_gauche", "V_droite"]

    active_data = captures[:, active_idx]
    combined = np.hstack([active_data, labels])
    corr_matrix = np.corrcoef(combined, rowvar=False)

    fig, ax = plt.subplots(figsize=(max(10, len(all_names) * 0.6), max(8, len(all_names) * 0.5)))
    im = ax.imshow(corr_matrix, cmap='RdBu_r', vmin=-1, vmax=1, aspect='auto')
    ax.set_xticks(range(len(all_names)))
    ax.set_yticks(range(len(all_names)))
    ax.set_xticklabels(all_names, rotation=45, ha='right', fontsize=7)
    ax.set_yticklabels(all_names, fontsize=7)
    ax.set_title('Matrice de correlation (features actives + labels)')
    fig.colorbar(im, ax=ax, shrink=0.8)
    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "correlation_matrix.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: correlation_matrix.png")
    plt.close()

    # === Figure 4b: Correlation features vs Roue Gauche / Roue Droite ===
    corr_per_label = np.zeros((len(active_idx), 2))
    for j, idx in enumerate(active_idx):
        corr_per_label[j, 0] = np.corrcoef(captures[:, idx], labels[:, 0])[0, 1]
        corr_per_label[j, 1] = np.corrcoef(captures[:, idx], labels[:, 1])[0, 1]

    fig, axes = plt.subplots(1, 2, figsize=(14, max(5, len(active_idx) * 0.3)))

    for ax_idx, (ax, label_name) in enumerate(zip(axes, ["Roue Gauche", "Roue Droite"])):
        vals = corr_per_label[:, ax_idx]
        sort_order = np.argsort(np.abs(vals))[::-1]
        sorted_names = [active_names[i] for i in sort_order]
        sorted_vals = vals[sort_order]

        colors = ['#e74c3c' if v < 0 else '#2ecc71' for v in sorted_vals]
        y_pos = np.arange(len(sorted_names))
        ax.barh(y_pos, sorted_vals, color=colors, edgecolor='black', height=0.7)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(sorted_names, fontsize=7)
        ax.set_xlabel('Correlation Pearson')
        ax.set_title(f'Features vs {label_name}')
        ax.set_xlim(-0.25, 0.25)
        ax.axvline(x=0, color='k', linewidth=0.5)
        ax.grid(True, alpha=0.3, axis='x')
        ax.invert_yaxis()

    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "correlation_per_label.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: correlation_per_label.png")
    plt.close()

    # === Figure 5: Distribution des categories d'actions (IMU-based) ===
    action_cats = classify_actions(captures, labels, sequence_ids=sequence_ids)
    cat_names = list(ACTION_NAMES)
    cat_counts = [int(np.sum(action_cats == i)) for i in range(5)]
    colors = ['#e74c3c', '#2ecc71', '#3498db', '#f39c12', '#9b59b6']

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(cat_names, cat_counts, color=colors, edgecolor='black')
    ax.set_ylabel('Nombre d\'echantillons')
    ax.set_title('Distribution des categories d\'actions')
    ax.grid(True, alpha=0.3, axis='y')
    for bar, count in zip(bars, cat_counts):
        pct = count / len(labels) * 100
        ax.text(bar.get_x() + bar.get_width()/2., bar.get_height(),
                f'{count}\n({pct:.1f}%)', ha='center', va='bottom', fontsize=8)
    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "action_categories.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: action_categories.png")
    plt.close()

    # === Figure 6: Top correlations features vs labels (barplot) ===
    corr_with_labels = []
    for i in active_idx:
        cl = np.corrcoef(captures[:, i], labels[:, 0])[0, 1]
        cr = np.corrcoef(captures[:, i], labels[:, 1])[0, 1]
        fname = feature_names[i] if i < len(feature_names) else f"f{i}"
        corr_with_labels.append((fname, cl, cr))

    corr_with_labels.sort(key=lambda x: max(abs(x[1]), abs(x[2])), reverse=True)
    top_n = min(10, len(corr_with_labels))
    top = corr_with_labels[:top_n]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(top_n)
    width = 0.35
    ax.bar(x - width/2, [t[1] for t in top], width, label='Roue Gauche', color='steelblue', edgecolor='black')
    ax.bar(x + width/2, [t[2] for t in top], width, label='Roue Droite', color='darkorange', edgecolor='black')
    ax.set_xticks(x)
    ax.set_xticklabels([t[0] for t in top], rotation=30, ha='right', fontsize=8)
    ax.set_ylabel('Coefficient de correlation')
    ax.set_title('Top correlations features-labels')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.axhline(y=0, color='k', linewidth=0.5)
    plt.tight_layout()
    if save_dir:
        plt.savefig(save_dir / "feature_label_correlation.png", dpi=150, bbox_inches='tight')
        print(f"[OK] Graphique sauvegarde: feature_label_correlation.png")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description="Analyse le dataset d'entrainement")
    parser.add_argument("--data-dir", type=str, default="data",
                       help="Repertoire du dataset (defaut: data)")
    parser.add_argument("--plot", action="store_true",
                       help="Generer les graphiques")
    parser.add_argument("--output-dir", type=str, default="dataset_analysis",
                       help="Repertoire de sortie pour les graphiques")

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    data_dir = script_dir / args.data_dir

    if not data_dir.exists():
        print(f"[ERREUR] Repertoire non trouve: {data_dir}")
        return False

    print(f"[*] Chargement du dataset depuis {data_dir}")
    print()

    captures, labels, sequence_ids = load_dataset(data_dir)

    if captures is None:
        print("[ERREUR] Impossible de charger le dataset")
        return False

    stats = analyze_dataset(captures, labels, sequence_ids=sequence_ids)

    if args.plot:
        output_dir = script_dir / args.output_dir
        print(f"[*] Generation des graphiques vers {output_dir}")
        print()
        plot_analysis(captures, labels, output_dir, sequence_ids=sequence_ids)
        print()

    return True


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
