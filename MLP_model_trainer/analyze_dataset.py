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
    both_wheels_low = np.sum((np.abs(labels[:, 0]) < threshold_straight) &
                            (np.abs(labels[:, 1]) < threshold_straight))
    total_straight_pct = (both_wheels_low / len(labels)) * 100

    print(f"[BIAS] Distribution des actions:")
    print(f"  'Tout droit' (|V_left| < 0.1 ET |V_right| < 0.1): {both_wheels_low:6d} ({total_straight_pct:5.1f}%)")
    print(f"  Actions complexes: {len(labels) - both_wheels_low:6d} ({100 - total_straight_pct:5.1f}%)")

    if total_straight_pct > 85:
        print(f"  [WARN] Biais important vers 'tout droit'! Le modele risque de sur-apprendre cette action.")
    print()

    # === ANALYSE DES CAPTURES (FEATURES ENTREE) ===
    print(f"[STATS] Features d'entree (Captures) - 20 dimensions:")
    feature_names = [
        "IR_front_right",       # 0
        "IR_bottom_right",      # 1
        "IR_back_right",        # 2
        "IR_bottom_left",       # 3
        "IR_back_left",         # 4
        "IR_front_left",        # 5
        "vision_flag",          # 6
        "vision_stop",          # 7
        "vision_pied",          # 8
        "vision_pompier",       # 9
        "bbox_x",               # 10
        "bbox_y",               # 11
        "bbox_w",               # 12
        "bbox_h",               # 13
        "imu_ax",               # 14
        "imu_ay",               # 15
        "imu_az",               # 16
        "imu_gx",               # 17
        "imu_gy",               # 18
        "imu_gz"                # 19
    ]

    for i in range(captures.shape[1]):
        feature_data = captures[:, i]
        print(f"  [{i:2d}] {feature_names[i]:20s} - "
              f"Min: {feature_data.min():7.4f}, Max: {feature_data.max():7.4f}, "
              f"Mean: {feature_data.mean():7.4f}, Std: {feature_data.std():7.4f}")

    print()

    # === DETECTION DE VALEURS ABERRANTES ===
    print("[OUTLIERS] Detection de valeurs aberrantes:")

    # Les features doivent etre normalisees entre [-1, 1]
    out_of_bounds = np.sum((captures < -1.0) | (captures > 1.0))
    print(f"  Valeurs hors [-1, 1]: {out_of_bounds}")

    if out_of_bounds > 0:
        print(f"  [WARN] Certaines features ne sont pas normalisees correctement!")

    # Vérifier les NaN
    nan_count = np.sum(np.isnan(captures)) + np.sum(np.isnan(labels))
    if nan_count > 0:
        print(f"  [WARN] {nan_count} valeurs NaN detectees!")
    else:
        print(f"  [OK] Aucune valeur NaN")

    print()

    # === VISION ANALYSIS ===
    print("[VISION] Analyse des détections:")
    vision_flag = captures[:, 6]
    nb_detections = np.sum(vision_flag > 0.5)
    detection_pct = (nb_detections / len(captures)) * 100
    print(f"  Echantillons avec detection: {nb_detections:6d} ({detection_pct:5.1f}%)")
    print(f"  Echantillons sans detection: {len(captures) - nb_detections:6d} ({100 - detection_pct:5.1f}%)")

    if detection_pct < 10:
        print(f"  [WARN] Peu de donnees avec detection d'objets! (~{detection_pct:.1f}%)")
        print(f"         Cela peut biaiser l'apprentissage vers 'tout droit'.")

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
        print("  * Utiliser une strategie d'oversampling pour les actions complexes")
        print("  * Ou utiliser weighted loss dans l'entrainement")
    else:
        print("  * Dataset bien equilibre")

    print()
    print("=" * 70)

    return {
        "n_samples": len(captures),
        "straight_pct": total_straight_pct,
        "detection_pct": detection_pct,
        "out_of_bounds": out_of_bounds,
        "nan_count": nan_count
    }


def plot_analysis(captures, labels, save_dir=None):
    """Crée des visualisations du dataset."""

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
    ax.set_ylim(0, 1.0)
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
