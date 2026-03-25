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


def load_dataset(data_dir: Path):
    """Charge les fichiers captures.jsonl et labels.jsonl."""
    captures_file = data_dir / "captures.jsonl"
    labels_file = data_dir / "labels.jsonl"

    if not captures_file.exists() or not labels_file.exists():
        return None, None

    captures = []
    labels = []

    with open(captures_file, 'r') as f:
        for line in f:
            if line.strip():
                captures.append(json.loads(line))

    with open(labels_file, 'r') as f:
        for line in f:
            if line.strip():
                labels.append(json.loads(line))

    return np.array(captures, dtype=np.float32), np.array(labels, dtype=np.float32)


def analyze_dataset(captures, labels, save_dir=None):
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
    feature_names = [
        "IR_front_right",       # 0
        "IR_bottom_right",      # 1
        "IR_back_right",        # 2
        "IR_bottom_left",       # 3
        "IR_back_left",         # 4
        "IR_front_left",        # 5
        "IR_diff",              # 6  (bot_left - bot_right)
        "IR_sum",               # 7  (bot_left + bot_right) / 2
        "detect_flag",          # 8
        "class_stop_sign",      # 9
        "class_pieton",         # 10
        "class_pompier",        # 11
        "bbox_cx",              # 12
        "bbox_cy",              # 13
        "bbox_w",               # 14
        "bbox_h",               # 15
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
        "IR_bot_R_delta",       # 27 (delta temporel)
        "IR_bot_L_delta",       # 28 (delta temporel)
        "IR_diff_delta",        # 29 (delta temporel)
        "IR_sum_delta",         # 30 (delta temporel)
        "gyro_z_delta",         # 31 (delta temporel = vitesse angulaire)
    ]

    # Support des anciens datasets 27-dim (sans deltas)
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
    print("[DUPLICATES] Detection de quasi-doublons consecutifs:")
    n_duplicates = 0
    if len(captures) > 1:
        diffs = np.linalg.norm(captures[1:] - captures[:-1], axis=1)
        dup_threshold = 1e-4
        n_duplicates = np.sum(diffs < dup_threshold)
        dup_pct = n_duplicates / (len(captures) - 1) * 100
        print(f"  Paires quasi-identiques (||delta|| < {dup_threshold}): {n_duplicates} ({dup_pct:.1f}%)")
        if n_duplicates > 0:
            print(f"  Distance moyenne entre consecutifs: {diffs.mean():.6f}")
            print(f"  Distance mediane: {np.median(diffs):.6f}")
        if dup_pct > 10:
            print(f"  [WARN] {dup_pct:.0f}% de doublons! Le robot etait probablement arrete")
            print(f"         ou le sampling etait trop rapide. Dataset effectif reduit.")
        else:
            print(f"  [OK] Peu de doublons.")
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

    # === CATEGORISATION FINE DES ACTIONS ===
    # Logique basee sur le controleur manuel (manual_controller.py):
    #   - Rotation pure (A/D): turn_speed=1 -> ~0.01 normalise
    #   - Arc (W+A/W+D): roue interieure ~0.02, exterieure ~0.38
    #   - Tout droit (W/S): ~0.20 par roue
    # Un virage = la roue la plus lente est sous turn_threshold
    print("[ACTIONS] Categorisation fine des commandes:")
    turn_threshold = 0.05   # seuil vitesse roue interieure pour detecter un virage
    stop_threshold = 0 # lorsque le robot est a l'arret les roues sont a 0.
    left = labels[:, 0]
    right = labels[:, 1]
    min_wheel = np.minimum(np.abs(left), np.abs(right))

    is_stop = (np.abs(left) == stop_threshold) & (np.abs(right) == stop_threshold)
    is_turning = (min_wheel < turn_threshold) & ~is_stop
    is_turn_left = is_turning & (left < right)
    is_turn_right = is_turning & (right < left)
    is_reverse = ~is_stop & ~is_turning & (left < 0) & (right < 0)
    is_forward = ~is_stop & ~is_turning & ~is_reverse

    categories = {
        "Arret":          np.sum(is_stop),
        "Tout droit":     np.sum(is_forward),
        "Tourne gauche":  np.sum(is_turn_left),
        "Tourne droite":  np.sum(is_turn_right),
        "Recule":         np.sum(is_reverse),
    }

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
        print(f"  * {len(dead_features)} features mortes retirees automatiquement (masque)")
    if n_duplicates > len(captures) * 0.1:
        print(f"  * {n_duplicates} doublons retires automatiquement (deduplication)")
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


def plot_analysis(captures, labels, save_dir=None):
    """Crée des visualisations du dataset."""

    feature_names = [
        "IR_front_R", "IR_bot_R", "IR_back_R", "IR_bot_L", "IR_back_L", "IR_front_L",
        "IR_diff", "IR_sum",
        "detect", "cls_stop", "cls_piet", "cls_pomp",
        "bbox_cx", "bbox_cy", "bbox_w", "bbox_h",
        "gyro_x", "gyro_y", "gyro_z", "acc_x", "acc_y",
        "comp_x", "comp_y", "rot_x", "rot_y", "rot_z", "tilt",
        "d_bot_R", "d_bot_L", "d_IR_diff", "d_IR_sum", "d_gyro_z",
    ]

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

    # === Figure 5: Distribution des categories d'actions ===
    diff_threshold = 0.05
    stop_threshold = 0.02
    left = labels[:, 0]
    right = labels[:, 1]
    speed_avg = (left + right) / 2.0
    steering = left - right

    is_stop = (np.abs(left) < stop_threshold) & (np.abs(right) < stop_threshold)
    is_reverse = (speed_avg < -stop_threshold) & ~is_stop
    is_turn_left = (steering < -diff_threshold) & ~is_stop & ~is_reverse
    is_turn_right = (steering > diff_threshold) & ~is_stop & ~is_reverse
    is_forward = ~is_stop & ~is_reverse & ~is_turn_left & ~is_turn_right

    cat_names = ["Arret", "Tout droit", "Tourne G", "Tourne D", "Recule"]
    cat_counts = [np.sum(is_stop), np.sum(is_forward), np.sum(is_turn_left),
                  np.sum(is_turn_right), np.sum(is_reverse)]
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

    captures, labels = load_dataset(data_dir)

    if captures is None:
        print("[ERREUR] Impossible de charger le dataset")
        return False

    stats = analyze_dataset(captures, labels)

    if args.plot:
        output_dir = script_dir / args.output_dir
        print(f"[*] Generation des graphiques vers {output_dir}")
        print()
        plot_analysis(captures, labels, output_dir)
        print()

    return True


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
