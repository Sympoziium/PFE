#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Evaluation avancee du modele MLP.

Sous-menu integre au trainer:
  [1] Evaluation sur sequences reelles (predictions vs labels)
  [2] Metriques par categorie d'action
  [3] Permutation importance (groupes de features)
"""

import collections
import json
import os
import sys
import numpy as np
import torch
import matplotlib.pyplot as plt
from pathlib import Path

from dataset import (
    ZumiControlDataset, ENGINEERED_FEATURE_NAMES,
    WINDOW_SIZE, WINDOW_FEATURE_DIM, TEMPORAL_DECAY,
    IR_OFFSET_DEFAULT, GAP_THRESHOLD, GYRO_Z_INDEX,
    DETECTION_INDICES,
    classify_actions, ACTION_NAMES,
)


# ============================================================
# Utilitaires
# ============================================================

def load_model_and_stats(checkpoints_dir: Path):
    """Charge le modele PyTorch et les stats de normalisation."""
    from train import ZumiMLP

    model_path = checkpoints_dir / "best_model.pt"
    if not model_path.exists():
        print("[ERREUR] Modele non trouve:", model_path)
        return None, None

    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    use_batchnorm = checkpoint.get('use_batchnorm', False)
    model = ZumiMLP(
        input_dim=checkpoint['input_dim'],
        output_dim=checkpoint['output_dim'],
        hidden_dims=checkpoint['hidden_dims'],
        use_batchnorm=use_batchnorm,
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    stats = {
        'feature_mean': np.array(checkpoint.get('feature_mean', [])),
        'feature_std': np.array(checkpoint.get('feature_std', [])),
        'input_dim': checkpoint['input_dim'],
        'output_dim': checkpoint['output_dim'],
        'hidden_dims': checkpoint['hidden_dims'],
        'val_loss': checkpoint.get('val_loss', 0),
        'motor_efficiency_left': checkpoint.get('motor_efficiency_left', 0.927),
        'exclude_detection': checkpoint.get('exclude_detection', False),
        'temporal_decay': checkpoint.get('temporal_decay', 1.0),
        'window_size': checkpoint.get('window_size', WINDOW_SIZE),
    }
    return model, stats


def inference(model, vector, stats):
    """Inference sur un vecteur windowed (WINDOW_SIZE * WINDOW_FEATURE_DIM dims). Applique z-score, passe au modele."""
    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    normalized = (vector - mean) / std

    with torch.no_grad():
        inp = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0)
        out = model(inp).numpy()[0]
    return out  # [left, right] normalise [-1, 1]


def build_windowed_vector(window_buffer):
    """Construit le vecteur windowed a partir du buffer glissant (WINDOW_SIZE x WINDOW_FEATURE_DIM).

    Le buffer est un deque(maxlen=WINDOW_SIZE) de vecteurs WINDOW_FEATURE_DIM-dim.
    Les positions non encore remplies restent a zero (zero-padding),
    identique au comportement du training pipeline aux frontieres de sequence.
    """
    flat = np.zeros(WINDOW_SIZE * WINDOW_FEATURE_DIM, dtype=np.float32)
    n = len(window_buffer)
    start_slot = WINDOW_SIZE - n
    for i, vec in enumerate(window_buffer):
        offset = (start_slot + i) * WINDOW_FEATURE_DIM
        flat[offset:offset + WINDOW_FEATURE_DIM] = vec
    return flat


def compute_engineered_features(raw_vector, prev_vec34=None, ir_offset=IR_OFFSET_DEFAULT):
    """Calcule les 9 features engineered a partir d'un vecteur brut -> +9 dim."""
    ir_bot_r = raw_vector[1]
    ir_bot_l = raw_vector[3]
    ir_sum = (ir_bot_l + ir_bot_r) / 2.0
    gyro_z = raw_vector[GYRO_Z_INDEX]

    calibrated_error = (ir_bot_r - ir_bot_l) - (-ir_offset)
    line_visible = 1.0 if ir_sum < GAP_THRESHOLD else 0.0
    cal_error_norm = calibrated_error / (ir_sum + 1e-6)

    gyro_z_rate = 0.0
    if prev_vec34 is not None:
        rate = gyro_z - prev_vec34[GYRO_Z_INDEX]
        if abs(rate) < 150.0:
            gyro_z_rate = rate

    heading_drift = gyro_z_rate * (1.0 - line_visible)

    engineered = np.array([
        calibrated_error, line_visible, cal_error_norm,
        gyro_z_rate, heading_drift
    ], dtype=np.float32)

    return np.concatenate([raw_vector, engineered]).astype(np.float32)


# ============================================================
# [1] Evaluation sur sequences reelles
# ============================================================

def run_sequence_evaluation(model, stats, data_dir: Path, save_dir: Path = None):
    """Evalue le modele sur des segments continus du dataset reel.

    Charge le dataset avec le pipeline complet (engineered + sliding windows),
    identifie les frontieres de sequence, et compare les predictions du modele
    aux labels reels avec un graphique temporel.
    """

    print("\n" + "=" * 60)
    print("  Evaluation sur sequences reelles")
    print("=" * 60)

    exclude_det = stats.get('exclude_detection', True)
    decay = stats.get('temporal_decay', TEMPORAL_DECAY)
    ws = stats.get('window_size', WINDOW_SIZE)

    # Charger le dataset brut (avant pipeline)
    dataset = ZumiControlDataset(str(data_dir))
    dataset.deduplicate()
    if exclude_det:
        dataset.exclude_detection_features()
    raw_captures = dataset.captures.copy()
    raw_labels = dataset.labels.copy()

    # Construire la liste des segments continus via sequence_ids
    seq_ids = dataset.sequence_ids
    unique_seqs = np.unique(seq_ids)
    segments = []
    for sid in unique_seqs:
        mask = np.where(seq_ids == sid)[0]
        start = int(mask[0])
        end = int(mask[-1]) + 1
        length = end - start
        if length >= 20:  # au moins 1 seconde
            segments.append((start, end, length))

    if not segments:
        print("\n  [ERREUR] Aucun segment d'au moins 20 pas trouve.")
        return

    # Afficher les segments disponibles
    print(f"\n  {len(segments)} segments trouves (>= 20 pas):")
    display_max = min(20, len(segments))
    for i, (start, end, length) in enumerate(segments[:display_max]):
        dur = length / 20.0  # duree en secondes a 20Hz
        print(f"    [{i + 1:2d}] Pas {start:6d}-{end:6d} ({length:5d} pas, {dur:.1f}s)")
    if len(segments) > display_max:
        print(f"    ... et {len(segments) - display_max} autres")

    # Choix du segment
    choice = input(f"\n  Segment a evaluer (1-{len(segments)}, A=tous les top-5) : ").strip().upper()

    if choice == 'A':
        # Prendre les 5 plus longs segments
        sorted_segs = sorted(segments, key=lambda s: s[2], reverse=True)[:5]
    else:
        try:
            seg_idx = int(choice) - 1
            sorted_segs = [segments[seg_idx]]
        except (ValueError, IndexError):
            print("  Choix invalide.")
            return

    # Appliquer le pipeline complet
    dataset.compute_engineered_features()
    dataset.compute_sliding_windows(window_size=ws, temporal_decay=decay)
    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    dataset.captures = ((dataset.captures - mean) / std).astype(np.float32)

    # Evaluer chaque segment
    for seg_num, (start, end, length) in enumerate(sorted_segs):
        print(f"\n  --- Segment {start}-{end} ({length} pas, {length / 20.0:.1f}s) ---")

        predictions = []
        model.eval()
        with torch.no_grad():
            for t in range(start, end):
                x = torch.tensor(dataset.captures[t], dtype=torch.float32).unsqueeze(0)
                pred = model(x).numpy()[0]
                predictions.append(pred)
        predictions = np.array(predictions)
        targets = raw_labels[start:end]

        # Metriques
        mse = float(((predictions - targets) ** 2).mean())
        mae = float(np.abs(predictions - targets).mean())
        ss_res = ((predictions - targets) ** 2).sum()
        ss_tot = ((targets - targets.mean(axis=0)) ** 2).sum()
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0

        print(f"    MSE: {mse:.4f}  MAE: {mae:.4f}  R2: {r2:.4f}")

        # Graphique
        timesteps = np.arange(length) / 20.0  # en secondes

        fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

        axes[0].plot(timesteps, targets[:, 0] * 50, 'b-', alpha=0.7, label='Reel')
        axes[0].plot(timesteps, predictions[:, 0] * 50, 'r--', alpha=0.7, label='Predit')
        axes[0].set_ylabel('Vitesse Gauche')
        axes[0].set_title(f'Evaluation sequence reelle — pas {start}-{end} '
                          f'(MSE={mse:.4f}, R2={r2:.4f})')
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)

        axes[1].plot(timesteps, targets[:, 1] * 50, 'b-', alpha=0.7, label='Reel')
        axes[1].plot(timesteps, predictions[:, 1] * 50, 'r--', alpha=0.7, label='Predit')
        axes[1].set_ylabel('Vitesse Droite')
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)

        real_steering = (targets[:, 0] - targets[:, 1]) * 50
        pred_steering = (predictions[:, 0] - predictions[:, 1]) * 50
        axes[2].plot(timesteps, real_steering, 'b-', alpha=0.7, label='Reel')
        axes[2].plot(timesteps, pred_steering, 'r--', alpha=0.7, label='Predit')
        axes[2].axhline(y=0, color='k', linewidth=0.5)
        axes[2].set_ylabel('Steering (L-R)')
        axes[2].set_xlabel('Temps (s)')
        axes[2].legend()
        axes[2].grid(True, alpha=0.3)

        plt.tight_layout()

        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            fname = save_dir / f"eval_seq_{start}_{end}.png"
            plt.savefig(fname, dpi=150, bbox_inches='tight')
            print(f"    Graphique sauvegarde: {fname}")

        if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or sys.platform == 'win32':
            plt.show()
        plt.close()

    print()


# ============================================================
# [2] Metriques par categorie
# ============================================================

def _prepare_eval_dataset(data_dir: Path, stats: dict):
    """Prepare le dataset pour l'evaluation avec le meme pipeline que l'entrainement.

    Lit exclude_detection et temporal_decay depuis les stats du modele.
    Utilise les sequence_ids pour les frontieres de sequence.
    """
    exclude_det = stats.get('exclude_detection', True)
    decay = stats.get('temporal_decay', TEMPORAL_DECAY)
    ws = stats.get('window_size', WINDOW_SIZE)

    dataset = ZumiControlDataset(str(data_dir))
    dataset.deduplicate()
    if exclude_det:
        dataset.exclude_detection_features()
    dataset.compute_engineered_features()
    return dataset, exclude_det, decay, ws


def _prepare_full_eval_dataset(data_dir: Path, stats: dict):
    """Prepare le dataset complet (avec sliding windows) pour l'evaluation."""
    dataset, exclude_det, decay, ws = _prepare_eval_dataset(data_dir, stats)
    dataset.compute_sliding_windows(window_size=ws, temporal_decay=decay)

    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    dataset.captures = ((dataset.captures - mean) / std).astype(np.float32)

    return dataset, exclude_det


def run_per_category_metrics(model, stats, data_dir: Path):
    """Calcule MSE/MAE/R2 par categorie d'action sur le dataset."""

    print("\n" + "=" * 60)
    print("  Metriques par categorie d'action")
    print("=" * 60)

    dataset_pre, exclude_det, decay, ws = _prepare_eval_dataset(data_dir, stats)

    # Categoriser AVANT le windowing (classify_actions a besoin de gyro_z brut)
    categories = classify_actions(dataset_pre.captures, dataset_pre.labels,
                                  sequence_ids=dataset_pre.sequence_ids)

    # Fenetre glissante + normalisation
    dataset_pre.compute_sliding_windows(window_size=ws, temporal_decay=decay)
    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    dataset_pre.captures = ((dataset_pre.captures - mean) / std).astype(np.float32)
    dataset = dataset_pre

    # Inference sur tout le dataset
    model.eval()
    all_preds = []
    with torch.no_grad():
        for i in range(len(dataset)):
            x, _ = dataset[i]
            pred = model(x.unsqueeze(0)).numpy()[0]
            all_preds.append(pred)
    predictions = np.array(all_preds)
    targets = dataset.labels

    print(f"\n  {'Categorie':15s} {'MSE':>8s} {'MAE':>8s} {'R2':>8s} {'N':>6s}")
    print(f"  {'-'*47}")

    for cat_idx, cat_name in enumerate(ACTION_NAMES):
        mask_cat = categories == cat_idx
        n = int(mask_cat.sum())
        if n == 0:
            continue
        p = predictions[mask_cat]
        t = targets[mask_cat]
        mse = float(((p - t) ** 2).mean())
        mae = float(np.abs(p - t).mean())
        ss_res = ((p - t) ** 2).sum()
        ss_tot = ((t - t.mean(axis=0)) ** 2).sum()
        r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0
        print(f"  {cat_name:15s} {mse:8.4f} {mae:8.4f} {r2:8.4f} {n:6d}")

    # Global
    mse_g = float(((predictions - targets) ** 2).mean())
    mae_g = float(np.abs(predictions - targets).mean())
    ss_res = ((predictions - targets) ** 2).sum()
    ss_tot = ((targets - targets.mean(axis=0)) ** 2).sum()
    r2_g = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0
    print(f"  {'-'*47}")
    print(f"  {'GLOBAL':15s} {mse_g:8.4f} {mae_g:8.4f} {r2_g:8.4f} {len(targets):6d}")
    print()


# ============================================================
# [3] Permutation importance
# ============================================================

def get_feature_groups(exclude_detection: bool = True) -> dict:
    """Retourne les groupes de features selon que Detection est exclue ou non.

    Avec Detection (49-dim/pas):
        IR bruts 0-5, IR diff/sum 6-7, Detection 8-15, IMU 16-26,
        Zone features 27-35 (9), Camera 36-37, Engineered 38-48 (11)
    Sans Detection (41-dim/pas):
        IR bruts 0-5, IR diff/sum 6-7, IMU 8-18,
        Zone features 19-27 (9), Camera 28-29, Engineered 30-40 (11)
    """
    if exclude_detection:
        return {
            'IR bruts (0-5)':     list(range(0, 6)),
            'IR diff/sum (6-7)':  list(range(6, 8)),
            'IMU (8-18)':         list(range(8, 19)),
            'Zones (19-27)':      list(range(19, 28)),
            'Camera (28-29)':     list(range(28, 30)),
            'Engineered (30-40)': list(range(30, 41)),
        }
    else:
        return {
            'IR bruts (0-5)':     list(range(0, 6)),
            'IR diff/sum (6-7)':  list(range(6, 8)),
            'Detection (8-15)':   list(range(8, 16)),
            'IMU (16-26)':        list(range(16, 27)),
            'Zones (27-35)':      list(range(27, 36)),
            'Camera (36-37)':     list(range(36, 38)),
            'Engineered (38-48)': list(range(38, 49)),
        }

# Defaut: detection exclue (coherent avec WINDOW_FEATURE_DIM=41)
FEATURE_GROUPS = get_feature_groups(exclude_detection=True)


def run_permutation_importance(model, stats, data_dir: Path, save_dir: Path = None):
    """Mesure l'importance de chaque groupe de features par permutation.

    Principe:
      1. Evaluer le modele normalement sur le dataset -> MSE de base.
      2. Pour chaque groupe de features, melanger aleatoirement les valeurs
         de ce groupe entre les echantillons (casse la relation feature-sortie
         tout en conservant la distribution statistique).
      3. Re-evaluer le modele. Si le MSE augmente beaucoup, le modele
         depend fortement de ce groupe.

    Interpretation des resultats:
      - Importance = (MSE_brouille - MSE_base) / MSE_base x 100%
      - Importance elevee (ex: +150%): le modele depend fortement de ces features
      - Importance faible (ex: +2%): le modele ignore pratiquement ces features
      - Importance ~0%: features mortes / inutiles pour le modele

    Chaque groupe est teste sur les 20 pas de la fenetre glissante simultanement.
    Le test est repete 5 fois par groupe pour obtenir une estimation robuste
    (moyenne +/- ecart-type).
    """

    print("\n" + "=" * 60)
    print("  Permutation importance (groupes de features)")
    print("=" * 60)

    N_REPEATS = 5

    # Charger et preparer le dataset (meme pipeline que l'entrainement)
    exclude_det = stats.get('exclude_detection', True)
    decay = stats.get('temporal_decay', TEMPORAL_DECAY)
    ws = stats.get('window_size', WINDOW_SIZE)

    dataset = ZumiControlDataset(str(data_dir))
    dataset.deduplicate()
    if exclude_det:
        dataset.exclude_detection_features()
    dataset.compute_engineered_features()
    dataset.compute_sliding_windows(window_size=ws, temporal_decay=decay)

    # Utiliser les bons groupes de features
    feature_groups = get_feature_groups(exclude_detection=exclude_det)

    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    dataset.captures = ((dataset.captures - mean) / std).astype(np.float32)

    X = dataset.captures  # (N, WINDOW_SIZE * WINDOW_FEATURE_DIM)
    Y = dataset.labels     # (N, 2)

    # MSE de base
    model.eval()
    with torch.no_grad():
        X_tensor = torch.tensor(X, dtype=torch.float32)
        preds_base = model(X_tensor).numpy()
    mse_base = float(((preds_base - Y) ** 2).mean())
    print(f"\n  MSE de base: {mse_base:.6f}")

    # Pour chaque groupe, calculer les indices dans le vecteur windowed
    # (le groupe couvre les WINDOW_SIZE pas de la fenetre)
    results = {}
    print(f"\n  {'Groupe':25s} {'Importance':>12s} {'MSE brouille':>14s}")
    print(f"  {'-'*55}")

    step_dim = WINDOW_FEATURE_DIM  # 30 si detection exclue, 38 sinon

    for group_name, step_indices in feature_groups.items():
        # Indices dans le vecteur plat: pour chaque pas w, offset = w * step_dim + idx
        windowed_indices = []
        for w in range(ws):
            for idx in step_indices:
                windowed_indices.append(w * step_dim + idx)
        windowed_indices = np.array(windowed_indices)

        importances = []
        for _ in range(N_REPEATS):
            X_perm = X.copy()
            # Melanger les colonnes du groupe entre les echantillons
            perm_order = np.random.permutation(len(X_perm))
            X_perm[:, windowed_indices] = X_perm[perm_order][:, windowed_indices]

            with torch.no_grad():
                preds_perm = model(torch.tensor(X_perm, dtype=torch.float32)).numpy()
            mse_perm = float(((preds_perm - Y) ** 2).mean())
            importance_pct = (mse_perm - mse_base) / mse_base * 100.0
            importances.append(importance_pct)

        mean_imp = np.mean(importances)
        std_imp = np.std(importances)
        results[group_name] = (mean_imp, std_imp)
        print(f"  {group_name:25s} {mean_imp:+10.1f}% +/-{std_imp:4.1f}%  "
              f"({mse_base * (1 + mean_imp / 100):.6f})")

    # Tri par importance decroissante
    sorted_results = sorted(results.items(), key=lambda x: x[1][0], reverse=True)

    print(f"\n  Classement (plus important en premier):")
    for rank, (name, (imp, std_imp)) in enumerate(sorted_results, 1):
        bar = '#' * max(0, int(imp / 5))  # 1 # pour chaque 5%
        print(f"    {rank}. {name:25s} {imp:+8.1f}% {bar}")

    # Bar chart
    names = [name for name, _ in sorted_results]
    means = [imp for _, (imp, _) in sorted_results]
    stds = [std_imp for _, (_, std_imp) in sorted_results]

    fig, ax = plt.subplots(figsize=(10, 6))
    y_pos = np.arange(len(names))
    colors = ['#d32f2f' if m > 50 else '#f57c00' if m > 10 else '#388e3c' if m > 1 else '#9e9e9e'
              for m in means]
    ax.barh(y_pos, means, xerr=stds, color=colors, capsize=4, edgecolor='black', linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names)
    ax.set_xlabel('Importance (% augmentation MSE)')
    ax.set_title('Permutation Importance par groupe de features')
    ax.axvline(x=0, color='black', linewidth=0.5)
    ax.invert_yaxis()
    ax.grid(axis='x', alpha=0.3)

    # Legende des couleurs
    ax.text(0.98, 0.02,
            'Rouge: critique (>50%)  Orange: important (>10%)\n'
            'Vert: utile (>1%)  Gris: negligeable (<1%)',
            transform=ax.transAxes, fontsize=8, ha='right', va='bottom',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = save_dir / "permutation_importance.png"
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"\n  Graphique sauvegarde: {fname}")

    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY') or sys.platform == 'win32':
        plt.show()
    plt.close()
    print()


# ============================================================
# Menu principal
# ============================================================

def run_simulation_menu(script_dir: Path, state: dict):
    """Menu interactif d'evaluation avancee."""

    checkpoints_dir = script_dir / "checkpoints"
    data_dir = script_dir / "data" / "val"  # Evaluer sur le val set (donnees reelles pures)
    eval_output_dir = script_dir / "evaluation_results"

    # Verifier le modele
    if not state.get('has_model'):
        print("\n  [ERREUR] Aucun modele entraine. Entrainez d'abord un modele (option 4).")
        return

    model, stats = load_model_and_stats(checkpoints_dir)
    if model is None:
        return

    info = state.get('model_info', {})
    arch = ' -> '.join(map(str, info.get('hidden_dims', [])))
    val_loss = info.get('val_loss', 0)

    while True:
        print("\n" + "=" * 60)
        print("  Evaluation avancee")
        print("=" * 60)
        print(f"  Modele: {info.get('input_dim', '?')} -> [{arch}] -> {info.get('output_dim', '?')} "
              f"(val_loss: {val_loss:.6f})")
        print()
        print("  [1] Evaluation sur sequences reelles (predictions vs labels)")
        print("  [2] Metriques par categorie d'action")
        print("  [3] Permutation importance (groupes de features)")
        print("  [R] Retour au menu principal")

        choice = input("\n  Choix : ").strip().upper()

        if choice == '1':
            run_sequence_evaluation(model, stats, data_dir, eval_output_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '2':
            run_per_category_metrics(model, stats, data_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '3':
            run_permutation_importance(model, stats, data_dir, eval_output_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == 'R':
            break

        else:
            print("  Choix invalide.")
