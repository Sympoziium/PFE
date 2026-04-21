#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Augmentation de donnees pour l'entrainement du MLP de controle.

Techniques disponibles (aucune ne modifie les labels moteur) :
  - Bruit IR gaussien : simule la variance naturelle des capteurs
  - Scaling IR : simule des conditions d'eclairage differentes
  - Dropout IR : simule des defaillances capteur momentanees
  - Combine : applique bruit + scaling pour un multiplicateur ~4-6x

Contrainte: le robot a un moteur gauche plus faible compense par PID.
Les labels contiennent cette correction asymetrique et ne doivent JAMAIS
etre modifies ou swappes par l'augmentation.

Usage:
    Appele depuis le menu interactif de train.py (option [3])
    ou directement:
        python augment.py              # Mode interactif
        python augment.py --combined   # Mode automatique (combine recommande)
"""

import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime


# Indices des 6 capteurs IR bruts dans le vecteur brut
IR_SENSOR_INDICES = [0, 1, 2, 3, 4, 5]
IR_DIFF_INDEX = 6
IR_SUM_INDEX = 7


def _recompute_ir_derived(captures: np.ndarray) -> np.ndarray:
    """Recalcule IR_diff et IR_sum apres modification des capteurs IR bruts.

    IR_diff = ir_bottom_left (3) - ir_bottom_right (1)
    IR_sum  = (ir_bottom_left (3) + ir_bottom_right (1)) / 2

    Args:
        captures: array (N, 29 ou 36) avec IR modifies aux indices 0-5

    Returns:
        captures avec indices 6-7 recalcules (modifie en place et retourne)
    """
    captures[:, IR_DIFF_INDEX] = captures[:, 3] - captures[:, 1]
    captures[:, IR_SUM_INDEX] = (captures[:, 3] + captures[:, 1]) / 2.0
    return captures


def augment_ir_noise(captures: np.ndarray, labels: np.ndarray,
                     sigma_levels: list = None, seed: int = None):
    """Genere des copies bruitees des echantillons.

    Ajoute du bruit gaussien N(0, sigma) aux 6 capteurs IR bruts,
    puis recalcule IR_diff et IR_sum. Les labels restent identiques.

    Args:
        captures: array (N, 29 ou 36) — vecteurs bruts
        labels: array (N, 2) — commandes moteur (non modifiees)
        sigma_levels: niveaux de bruit (defaut: [1.5, 3.0, 4.5])
        seed: graine aleatoire pour reproductibilite

    Returns:
        tuple: (aug_captures, aug_labels) — donnees augmentees SANS originaux
    """
    if sigma_levels is None:
        sigma_levels = [1.5, 3.0, 4.5]

    rng = np.random.default_rng(seed)
    all_captures = []
    all_labels = []

    for sigma in sigma_levels:
        noisy = captures.copy()
        noise = rng.normal(0, sigma, size=(len(captures), 6)).astype(np.float32)
        noisy[:, IR_SENSOR_INDICES] += noise
        noisy[:, IR_SENSOR_INDICES] = np.clip(noisy[:, IR_SENSOR_INDICES], 0, 255)
        _recompute_ir_derived(noisy)

        all_captures.append(noisy)
        all_labels.append(labels.copy())

    return np.concatenate(all_captures), np.concatenate(all_labels)


def augment_ir_scaling(captures: np.ndarray, labels: np.ndarray,
                       scale_factors: list = None, seed: int = None):
    """Genere des copies avec eclairage simule different.

    Multiplie les 6 capteurs IR par un facteur d'echelle pour simuler
    des variations de luminosite ambiante. Clamp a [0, 255].

    Args:
        captures: array (N, 29 ou 36) — vecteurs bruts
        labels: array (N, 2) — commandes moteur (non modifiees)
        scale_factors: facteurs d'echelle (defaut: [0.85, 0.92, 1.08, 1.15])
        seed: graine aleatoire (non utilise, deterministe)

    Returns:
        tuple: (aug_captures, aug_labels) — donnees augmentees SANS originaux
    """
    if scale_factors is None:
        scale_factors = [0.85, 0.92, 1.08, 1.15]

    all_captures = []
    all_labels = []

    for factor in scale_factors:
        scaled = captures.copy()
        scaled[:, IR_SENSOR_INDICES] *= factor
        scaled[:, IR_SENSOR_INDICES] = np.clip(scaled[:, IR_SENSOR_INDICES], 0, 255)
        _recompute_ir_derived(scaled)

        all_captures.append(scaled)
        all_labels.append(labels.copy())

    return np.concatenate(all_captures), np.concatenate(all_labels)


def augment_ir_dropout(captures: np.ndarray, labels: np.ndarray,
                       dropout_rate: float = 0.08, patch_size: int = 3,
                       seed: int = None):
    """Genere une copie avec dropout aleatoire des capteurs IR.

    Pour chaque echantillon, avec probabilite dropout_rate, met a zero
    les capteurs IR bottom (indices 1, 3) sur un patch de frames consecutives.
    Simule une perte momentanee de detection de ligne.

    Args:
        captures: array (N, 29 ou 36) — vecteurs bruts
        labels: array (N, 2) — commandes moteur (non modifiees)
        dropout_rate: probabilite de dropout par echantillon
        patch_size: nombre de frames consecutives affectees
        seed: graine aleatoire

    Returns:
        tuple: (aug_captures, aug_labels) — donnees augmentees SANS originaux
    """
    rng = np.random.default_rng(seed)
    dropped = captures.copy()

    # Generer les positions de dropout
    n = len(captures)
    drop_starts = rng.random(n) < dropout_rate

    # Pour chaque position de debut, appliquer le dropout sur patch_size frames
    bottom_ir = [1, 3]  # IR_bottom_right, IR_bottom_left
    for i in range(n):
        if drop_starts[i]:
            end = min(i + patch_size, n)
            # Mettre les capteurs bottom a une valeur haute (route noire = pas de ligne)
            dropped[i:end, bottom_ir] = 240.0

    _recompute_ir_derived(dropped)
    return dropped, labels.copy()


def augment_combined(captures: np.ndarray, labels: np.ndarray, seed: int = None):
    """Applique bruit + scaling pour un multiplicateur ~4x.

    Combine:
      - Bruit IR sigma=[2.0, 4.0] → 2 variantes
      - Scaling IR [0.9, 1.1] → 2 variantes
    Total: 4 variantes supplementaires.

    Args:
        captures: array (N, 29 ou 36) — vecteurs bruts
        labels: array (N, 2) — commandes moteur (non modifiees)
        seed: graine aleatoire

    Returns:
        tuple: (aug_captures, aug_labels) — donnees augmentees SANS originaux
    """
    rng = np.random.default_rng(seed)
    all_captures = []
    all_labels = []

    sigma_levels = [2.0, 4.0]
    scale_factors = [0.9, 1.1]

    for sigma in sigma_levels:
        for factor in scale_factors:
            augmented = captures.copy()

            # Appliquer scaling
            augmented[:, IR_SENSOR_INDICES] *= factor

            # Appliquer bruit
            noise = rng.normal(0, sigma, size=(len(captures), 6)).astype(np.float32)
            augmented[:, IR_SENSOR_INDICES] += noise

            # Clamp et recalculer
            augmented[:, IR_SENSOR_INDICES] = np.clip(
                augmented[:, IR_SENSOR_INDICES], 0, 255
            )
            _recompute_ir_derived(augmented)

            all_captures.append(augmented)
            all_labels.append(labels.copy())

    return np.concatenate(all_captures), np.concatenate(all_labels)


def augment_combined_extended(captures: np.ndarray, labels: np.ndarray, seed: int = None):
    """Augmentation etendue : bruit + scaling en grille dense, multiplicateur ~9x.

    Grille de combinaisons :
      - Bruit IR sigma=[1.5, 3.0, 5.0] (3 niveaux)
      - Scaling IR [0.88, 1.0, 1.12] (3 niveaux, 1.0 = bruit seul)
    Total: 9 variantes (dont 3 avec scaling=1.0 = bruit pur).

    Les niveaux restent dans la plage physique des capteurs (sigma <= 5, scaling <= 1.2).

    Args:
        captures: array (N, 29 ou 36) — vecteurs bruts
        labels: array (N, 2) — commandes moteur (non modifiees)
        seed: graine aleatoire

    Returns:
        tuple: (aug_captures, aug_labels) — donnees augmentees SANS originaux
    """
    rng = np.random.default_rng(seed)
    all_captures = []
    all_labels = []

    sigma_levels = [1.5, 3.0, 5.0]
    scale_factors = [0.88, 1.0, 1.12]

    for sigma in sigma_levels:
        for factor in scale_factors:
            augmented = captures.copy()

            if factor != 1.0:
                augmented[:, IR_SENSOR_INDICES] *= factor

            noise = rng.normal(0, sigma, size=(len(captures), 6)).astype(np.float32)
            augmented[:, IR_SENSOR_INDICES] += noise

            augmented[:, IR_SENSOR_INDICES] = np.clip(
                augmented[:, IR_SENSOR_INDICES], 0, 255
            )
            _recompute_ir_derived(augmented)

            all_captures.append(augmented)
            all_labels.append(labels.copy())

    return np.concatenate(all_captures), np.concatenate(all_labels)


# ══════════════════════════════════════════════════════════════
#  I/O : chargement, sauvegarde, log
# ══════════════════════════════════════════════════════════════

def load_raw_data(data_dir: Path):
    """Charge les donnees brutes (captures + labels) depuis le repertoire data/.

    Gere le melange de vecteurs 29-dim (ancien format), 36-dim (intermediaire)
    et 38-dim (nouveau format) en zero-paddant aux positions semantiquement correctes.

    Returns:
        tuple: (captures, labels) — arrays numpy (N, 38) et (N, 2)
    """
    from dataset import (OLD_STATE_DIM, INTERMEDIATE_STATE_DIM, NEW_STATE_DIM,
                         ZONE_INSERT_POS, ZONE_FEATURES_DIM)

    captures_path = data_dir / "captures.jsonl"
    labels_path = data_dir / "labels.jsonl"

    if not captures_path.exists() or not labels_path.exists():
        raise FileNotFoundError(f"Fichiers non trouves dans {data_dir}")

    captures = []
    with open(captures_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                row = json.loads(line)
                if len(row) == OLD_STATE_DIM:
                    # 29 -> 38: inserer 9 zeros avant les features camera
                    row = (row[:ZONE_INSERT_POS]
                           + [0.0] * ZONE_FEATURES_DIM
                           + row[ZONE_INSERT_POS:])
                elif len(row) == INTERMEDIATE_STATE_DIM:
                    # 36 -> 38: inserer front_dash_count (pos 30) et center_dash_count (pos 35)
                    row = (row[:30]           # IR+eng+det+IMU+front_{det,conf,off}
                           + [0.0]             # front_dash_count_norm
                           + row[30:34]        # 4 corner features
                           + [0.0]             # center_dash_count_norm
                           + row[34:36])       # camera
                captures.append(row)

    labels = []
    with open(labels_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                labels.append(json.loads(line))

    return np.array(captures, dtype=np.float32), np.array(labels, dtype=np.float32)


def save_augmented_data(data_dir: Path, aug_captures: np.ndarray, aug_labels: np.ndarray,
                        n_original: int = None):
    """Sauvegarde les donnees augmentees dans des fichiers separes.

    Ecrit dans captures_augmented.jsonl, labels_augmented.jsonl,
    et sequence_ids_augmented.jsonl (replique les IDs originaux pour chaque copie).
    """
    cap_path = data_dir / "captures_augmented.jsonl"
    lab_path = data_dir / "labels_augmented.jsonl"
    sid_path = data_dir / "sequence_ids_augmented.jsonl"

    with open(cap_path, 'w') as f:
        for row in aug_captures:
            f.write(json.dumps(row.tolist()) + '\n')

    with open(lab_path, 'w') as f:
        for row in aug_labels:
            f.write(json.dumps(row.tolist()) + '\n')

    # Repliquer les sequence_ids originaux pour les donnees augmentees.
    # Chaque copie augmentee garde le meme ID que l'original.
    orig_sid_path = data_dir / "sequence_ids.jsonl"
    if orig_sid_path.exists() and n_original is not None:
        orig_ids = []
        with open(orig_sid_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    orig_ids.append(line)

        if len(orig_ids) == n_original:
            n_copies = len(aug_captures) // n_original
            with open(sid_path, 'w') as f:
                for _ in range(n_copies):
                    for sid in orig_ids:
                        f.write(sid + '\n')
            print(f"[Augment] Sauvegarde: {sid_path} ({n_copies} copies x {n_original} IDs)")
        else:
            print(f"[Augment] WARN: sequence_ids.jsonl ({len(orig_ids)}) != n_original ({n_original}), "
                  f"sequence_ids_augmented.jsonl non genere")

    print(f"[Augment] Sauvegarde: {cap_path} ({len(aug_captures)} echantillons)")
    print(f"[Augment] Sauvegarde: {lab_path}")


def merge_augmented_into_dataset(data_dir: Path):
    """Fusionne les fichiers augmentes dans le dataset principal.

    Appende captures_augmented.jsonl dans captures.jsonl (idem pour labels
    et sequence_ids). Supprime les fichiers augmentes apres fusion.
    """
    for name in ["captures", "labels", "sequence_ids"]:
        main_path = data_dir / f"{name}.jsonl"
        aug_path = data_dir / f"{name}_augmented.jsonl"

        if not aug_path.exists():
            continue

        # Compter les lignes augmentees
        n_aug = 0
        with open(aug_path, 'r') as f:
            for line in f:
                if line.strip():
                    n_aug += 1

        # Appender
        with open(main_path, 'a') as main_f, open(aug_path, 'r') as aug_f:
            for line in aug_f:
                if line.strip():
                    main_f.write(line if line.endswith('\n') else line + '\n')

        aug_path.unlink()
        print(f"[Augment] Fusionne {n_aug} lignes dans {main_path}")


def save_augmentation_log(data_dir: Path, technique: str, n_original: int,
                          n_augmented: int, params: dict):
    """Sauvegarde un log de l'augmentation appliquee pour tracabilite."""
    log_path = data_dir / "augmentation_log.json"

    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "technique": technique,
        "n_original": n_original,
        "n_augmented": n_augmented,
        "n_total": n_original + n_augmented,
        "multiplier": round((n_original + n_augmented) / n_original, 1),
        "params": params,
    }

    # Charger le log existant ou creer un nouveau
    if log_path.exists():
        with open(log_path, 'r') as f:
            log = json.load(f)
    else:
        log = {"history": []}

    log["history"].append(log_entry)
    log["latest"] = log_entry

    with open(log_path, 'w') as f:
        json.dump(log, f, indent=2)

    print(f"[Augment] Log sauvegarde: {log_path}")


# ══════════════════════════════════════════════════════════════
#  Menu interactif (appele depuis train.py ou standalone)
# ══════════════════════════════════════════════════════════════

def run_augmentation_menu(script_dir: Path):
    """Menu interactif d'augmentation des donnees.

    Augmente UNIQUEMENT les donnees d'entrainement (data/train/).
    Les donnees de validation (data/val/) ne sont jamais touchees.
    """
    data_dir = script_dir / "data" / "train"

    print("\n" + "=" * 60)
    print("  Augmentation des donnees (train set uniquement)")
    print("=" * 60)

    # Charger les donnees d'entrainement
    try:
        captures, labels = load_raw_data(data_dir)
    except FileNotFoundError:
        print("\n  ERREUR: Dataset train non trouve dans data/train/")
        print("  -> Executez d'abord l'option [1] Agreger les sequences")
        return False

    n_original = len(captures)
    print(f"\n  Dataset actuel : {n_original:,} echantillons ({captures.shape[1]}-dim)")

    # Verifier si deja augmente
    log_path = data_dir / "augmentation_log.json"
    if log_path.exists():
        with open(log_path, 'r') as f:
            log = json.load(f)
        latest = log.get("latest", {})
        print(f"  Derniere augmentation : {latest.get('technique', 'N/A')} "
              f"({latest.get('timestamp', 'N/A')[:10]})")
        print(f"  [WARN] Le dataset contient deja des echantillons augmentes.")
        print(f"         Re-agregez (option [1]) avant d'augmenter a nouveau.")

    print(f"\n  Techniques disponibles :")
    print(f"    [1] Bruit IR gaussien      (x3,   risque: tres faible)")
    print(f"    [2] Scaling IR (eclairage)  (x4,   risque: faible)")
    print(f"    [3] Dropout capteurs IR     (x1,   risque: faible-moyen)")
    print(f"    [4] Combine                 (x4,   bruit + scaling)")
    print(f"    [5] Combine etendu          (x9,   grille dense bruit + scaling)")
    print(f"    [R] Retour")

    while True:
        choice = input(f"\n  Choix : ").strip().upper()

        if choice == 'R':
            return False

        if choice == '1':
            technique = "ir_noise"
            params = {"sigma_levels": [1.5, 3.0, 4.5]}
            aug_cap, aug_lab = augment_ir_noise(captures, labels, **params, seed=42)
        elif choice == '2':
            technique = "ir_scaling"
            params = {"scale_factors": [0.85, 0.92, 1.08, 1.15]}
            aug_cap, aug_lab = augment_ir_scaling(captures, labels, **params, seed=42)
        elif choice == '3':
            technique = "ir_dropout"
            params = {"dropout_rate": 0.08, "patch_size": 3}
            aug_cap, aug_lab = augment_ir_dropout(captures, labels, **params, seed=42)
        elif choice == '4':
            technique = "combined"
            params = {"sigma_levels": [2.0, 4.0], "scale_factors": [0.9, 1.1]}
            aug_cap, aug_lab = augment_combined(captures, labels, seed=42)
        elif choice == '5':
            technique = "combined_extended"
            params = {"sigma_levels": [1.5, 3.0, 5.0], "scale_factors": [0.88, 1.0, 1.12]}
            aug_cap, aug_lab = augment_combined_extended(captures, labels, seed=42)
        else:
            print(f"  Choix invalide.")
            continue

        break

    n_augmented = len(aug_cap)
    n_total = n_original + n_augmented

    print(f"\n  Resume :")
    print(f"    Technique : {technique}")
    print(f"    Echantillons originaux  : {n_original:,}")
    print(f"    Echantillons augmentes  : +{n_augmented:,}")
    print(f"    Total apres fusion      : {n_total:,} (x{n_total / n_original:.1f})")

    # Validation rapide
    ir_min = aug_cap[:, IR_SENSOR_INDICES].min()
    ir_max = aug_cap[:, IR_SENSOR_INDICES].max()
    print(f"    IR range augmente       : [{ir_min:.0f}, {ir_max:.0f}] (attendu: [0, 255])")

    confirm = input(f"\n  Fusionner dans le dataset ? (O/N) : ").strip().upper()
    if confirm != 'O':
        print("  Augmentation annulee.")
        return False

    # Sauvegarder puis fusionner (incluant les sequence_ids)
    save_augmented_data(data_dir, aug_cap, aug_lab, n_original=n_original)
    merge_augmented_into_dataset(data_dir)
    save_augmentation_log(data_dir, technique, n_original, n_augmented, params)

    print(f"\n" + "=" * 60)
    print(f"  Augmentation terminee!")
    print(f"  Dataset total : {n_total:,} echantillons")
    print(f"=" * 60)

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Augmentation des donnees MLP Zumi")
    parser.add_argument("--combined", action="store_true",
                        help="Appliquer l'augmentation combinee (mode automatique)")
    args = parser.parse_args()

    script_dir = Path(__file__).parent

    if args.combined:
        data_dir = script_dir / "data"
        captures, labels = load_raw_data(data_dir)
        aug_cap, aug_lab = augment_combined(captures, labels, seed=42)
        save_augmented_data(data_dir, aug_cap, aug_lab)
        merge_augmented_into_dataset(data_dir)
        save_augmentation_log(data_dir, "combined", len(captures), len(aug_cap),
                              {"sigma_levels": [2.0, 4.0], "scale_factors": [0.9, 1.1]})
    else:
        run_augmentation_menu(script_dir)
