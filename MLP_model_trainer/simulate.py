#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Simulation & evaluation avancee du modele MLP.

Sous-menu integre au trainer:
  [1] Tests scenariques (inputs synthetiques)
  [2] Metriques par categorie d'action
  [3] Ablation de features
  [4] Simulation boucle ouverte (sur sequence reelle)
"""

import json
import numpy as np
import torch
import matplotlib.pyplot as plt
from pathlib import Path

from dataset import (
    ZumiControlDataset, DELTA_FEATURE_INDICES, DELTA_STEPS, DELTA_WEIGHTS,
    ENGINEERED_FEATURE_NAMES, create_data_loaders,
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
    model = ZumiMLP(
        input_dim=checkpoint['input_dim'],
        output_dim=checkpoint['output_dim'],
        hidden_dims=checkpoint['hidden_dims'],
    )
    model.load_state_dict(checkpoint['model_state_dict'])
    model.eval()

    stats = {
        'feature_mean': np.array(checkpoint.get('feature_mean', [])),
        'feature_std': np.array(checkpoint.get('feature_std', [])),
        'feature_mask': checkpoint.get('feature_mask'),
        'input_dim': checkpoint['input_dim'],
        'output_dim': checkpoint['output_dim'],
        'hidden_dims': checkpoint['hidden_dims'],
        'val_loss': checkpoint.get('val_loss', 0),
        'motor_efficiency_left': checkpoint.get('motor_efficiency_left', 0.927),
    }
    return model, stats


def inference(model, vector, stats):
    """Inference sur un vecteur deja masque. Applique z-score, passe au modele."""
    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    normalized = (vector - mean) / std

    with torch.no_grad():
        inp = torch.tensor(normalized, dtype=torch.float32).unsqueeze(0)
        out = model(inp).numpy()[0]
    return out  # [left, right] normalise [-1, 1]


def compute_engineered_features(raw_vector):
    """Calcule line_position et line_confidence a partir d'un vecteur 27-dim."""
    ir_bot_r = raw_vector[1]
    ir_bot_l = raw_vector[3]
    line_pos = (ir_bot_l - ir_bot_r) / (ir_bot_l + ir_bot_r + 1e-6)
    line_conf = abs(ir_bot_l - ir_bot_r) / ((ir_bot_l + ir_bot_r) / 2 + 1e-6)
    return np.append(raw_vector, [line_pos, line_conf]).astype(np.float32)


def build_full_vector(raw_29, prev_vectors, feature_mask=None):
    """Construit le vecteur complet (29-dim + deltas multi-pas), applique le masque."""
    all_deltas = []
    for step, weight in enumerate(DELTA_WEIGHTS):
        d = np.zeros(len(DELTA_FEATURE_INDICES), dtype=np.float32)
        if step < len(prev_vectors):
            prev = prev_vectors[-(step + 1)]
            d = (raw_29[DELTA_FEATURE_INDICES] - prev[DELTA_FEATURE_INDICES]) * weight
        all_deltas.append(d)

    full = np.concatenate([raw_29] + all_deltas)

    if feature_mask is not None:
        full = full[feature_mask]

    return full


# ============================================================
# [1] Tests scenariques
# ============================================================

def run_scenario_tests(model, stats, data_dir: Path):
    """Teste le modele avec des inputs synthetiques representant des situations connues."""

    print("\n" + "=" * 60)
    print("  Tests scenariques")
    print("=" * 60)

    # Charger les moyennes du dataset pour les features non-testees
    captures_file = data_dir / "captures.jsonl"
    if captures_file.exists():
        captures = []
        with open(captures_file, 'r') as f:
            for line in f:
                if line.strip():
                    captures.append(json.loads(line))
        captures = np.array(captures, dtype=np.float32)
        base_vector = captures.mean(axis=0)  # 27-dim moyennes
    else:
        base_vector = np.zeros(27, dtype=np.float32)
        base_vector[0:6] = [180, 190, 155, 200, 195, 207]  # IR moyennes typiques

    # Note: les checks utilisent les vitesses denormalisees (l, r en unites moteur -50..50)
    # pour que les seuils soient intuitifs.
    scenarios = [
        {
            'name': 'Ligne centree',
            'mods': {1: 190, 3: 190},  # IR_bot_R = IR_bot_L
            'expect': 'tout droit: |steering| < 3, les deux roues > 0',
            'check': lambda l, r: abs(l - r) < 3 and l > 0 and r > 0,
        },
        {
            'name': 'Ligne a droite (IR_bot_R bas)',
            'mods': {1: 100, 3: 220},  # ligne plus proche cote gauche -> tourner droite
            'expect': 'tourner a droite: steering > +3 (left > right de >3)',
            'check': lambda l, r: (l - r) > 3,
        },
        {
            'name': 'Ligne a gauche (IR_bot_L bas)',
            'mods': {1: 220, 3: 100},  # ligne plus proche cote droit -> tourner gauche
            'expect': 'tourner a gauche: steering < -3 (right > left de >3)',
            'check': lambda l, r: (r - l) > 3,
        },
        {
            'name': 'Pas de ligne (IR bas)',
            'mods': {1: 50, 3: 50},
            'expect': 'arret ou lent: les deux roues < 5',
            'check': lambda l, r: abs(l) < 5 and abs(r) < 5,
        },
        {
            'name': 'Correction symetrique (droite vs gauche)',
            'mods': None,  # traite specialement ci-dessous
            'expect': 'steering droite et gauche de signes opposes',
            'check': None,  # traite specialement
        },
    ]

    def _predict_scenario(base, mods):
        """Helper: construit un vecteur, infere, retourne les vitesses moteur."""
        vec = base.copy()
        for idx, val in mods.items():
            vec[idx] = val
        vec[6] = vec[3] - vec[1]  # IR_diff
        vec[7] = (vec[3] + vec[1]) / 2  # IR_sum
        vec_29 = compute_engineered_features(vec)
        full = build_full_vector(vec_29, [], stats.get('feature_mask'))
        pred = inference(model, full, stats)
        return pred[0] * 50, pred[1] * 50  # vitesses moteur denormalisees

    n_pass = 0
    for scenario in scenarios:
        # Test special: symetrie des corrections
        if scenario['name'] == 'Correction symetrique (droite vs gauche)':
            l_right, r_right = _predict_scenario(base_vector, {1: 100, 3: 220})
            l_left, r_left = _predict_scenario(base_vector, {1: 220, 3: 100})
            steer_right = l_right - r_right  # devrait etre positif
            steer_left = l_left - r_left     # devrait etre negatif
            passed = steer_right > 0 and steer_left < 0
            status = "PASS" if passed else "FAIL"
            n_pass += int(passed)
            print(f"\n  [{status}] {scenario['name']}")
            print(f"    Attendu: {scenario['expect']}")
            print(f"    Ligne a droite -> steering={steer_right:+.1f}")
            print(f"    Ligne a gauche -> steering={steer_left:+.1f}")
            continue

        speed_left, speed_right = _predict_scenario(base_vector, scenario['mods'])
        passed = scenario['check'](speed_left, speed_right)
        status = "PASS" if passed else "FAIL"
        n_pass += int(passed)

        print(f"\n  [{status}] {scenario['name']}")
        print(f"    Attendu: {scenario['expect']}")
        print(f"    Predit:  L={speed_left:+.1f}, R={speed_right:+.1f} (steering={speed_left-speed_right:+.1f})")

    print(f"\n  Resultat: {n_pass}/{len(scenarios)} tests passes")
    print()


# ============================================================
# [2] Metriques par categorie
# ============================================================

def run_per_category_metrics(model, stats, data_dir: Path):
    """Calcule MSE/MAE par categorie d'action sur le dataset."""

    print("\n" + "=" * 60)
    print("  Metriques par categorie d'action")
    print("=" * 60)

    # Charger et preparer le dataset de la meme facon que l'entrainement
    dataset = ZumiControlDataset(str(data_dir))
    dataset.deduplicate()
    dataset.compute_line_features()
    dataset.compute_deltas()

    mask = stats.get('feature_mask')
    if mask is not None:
        dataset.apply_feature_mask(mask)

    # Normaliser avec les stats du modele
    mean = stats['feature_mean']
    std = stats['feature_std'].copy()
    std[std < 1e-6] = 1.0
    dataset.captures = ((dataset.captures - mean) / std).astype(np.float32)

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

    # Categoriser
    left = targets[:, 0]
    right = targets[:, 1]
    turn_threshold = 0.05
    min_wheel = np.minimum(np.abs(left), np.abs(right))

    is_stop = (np.abs(left) == 0) & (np.abs(right) == 0)
    is_turning = (min_wheel < turn_threshold) & ~is_stop
    is_turn_left = is_turning & (left < right)
    is_turn_right = is_turning & (right < left)
    is_reverse = ~is_stop & ~is_turning & (left < 0) & (right < 0)
    is_forward = ~is_stop & ~is_turning & ~is_reverse

    categories = {
        'Arret': is_stop,
        'Tout droit': is_forward,
        'Tourne G': is_turn_left,
        'Tourne D': is_turn_right,
        'Recule': is_reverse,
    }

    print(f"\n  {'Categorie':15s} {'MSE':>8s} {'MAE':>8s} {'R2':>8s} {'N':>6s}")
    print(f"  {'-'*47}")

    for cat_name, mask_cat in categories.items():
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
# [3] Ablation de features
# ============================================================

def run_feature_ablation(data_dir: Path):
    """Evalue l'impact de chaque groupe de features avec regression lineaire rapide."""

    print("\n" + "=" * 60)
    print("  Ablation de features (regression lineaire, cross-validation)")
    print("=" * 60)

    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.model_selection import cross_val_score
    except ImportError:
        print("\n  [ERREUR] sklearn requis. pip install scikit-learn")
        return

    # Charger le dataset brut
    dataset = ZumiControlDataset(str(data_dir))
    dataset.deduplicate()
    captures = dataset.captures  # 27-dim
    labels = dataset.labels

    # Calculer les features engineered
    ir_bot_r = captures[:, 1]
    ir_bot_l = captures[:, 3]
    line_pos = (ir_bot_l - ir_bot_r) / (ir_bot_l + ir_bot_r + 1e-6)
    line_conf = np.abs(ir_bot_l - ir_bot_r) / ((ir_bot_l + ir_bot_r) / 2 + 1e-6)

    # Calculer deltas pas 1 pour tester leur apport
    delta_cols = [1, 3, 6, 7, 18]  # IR base deltas
    selected = captures[:, delta_cols]
    deltas_t1 = np.zeros_like(selected)
    deltas_t1[1:] = selected[1:] - selected[:-1]

    # Groupes de features a tester
    ir_raw = captures[:, [0, 1, 2, 3, 4, 5]]
    ir_eng = captures[:, [0, 1, 2, 3, 4, 5, 6, 7]]
    ir_enriched = np.column_stack([ir_eng, line_pos, line_conf])
    ir_enriched_deltas = np.column_stack([ir_enriched, deltas_t1])
    imu = captures[:, 16:27]
    ir_imu = np.column_stack([ir_eng, imu])
    all_features = np.column_stack([ir_enriched, deltas_t1, imu])

    groups = [
        ("IR bruts (6 feat)", ir_raw),
        ("IR + IR_diff/sum (8 feat)", ir_eng),
        ("IR + engineered (10 feat)", ir_enriched),
        ("IR + eng + deltas_t1 (15 feat)", ir_enriched_deltas),
        ("IR + IMU (19 feat)", ir_imu),
        ("Toutes features (26 feat)", all_features),
    ]

    print(f"\n  {'Groupe':40s} {'R2':>10s} {'+/-':>8s}")
    print(f"  {'-'*58}")

    for name, X in groups:
        scores = cross_val_score(LinearRegression(), X, labels, cv=5, scoring='r2')
        print(f"  {name:40s} {scores.mean():10.4f} {scores.std():8.4f}")

    print()


# ============================================================
# [4] Simulation boucle ouverte
# ============================================================

def run_open_loop_simulation(model, stats, sequences_dir: Path, save_dir: Path = None):
    """Simulation boucle ouverte sur une sequence reelle."""

    print("\n" + "=" * 60)
    print("  Simulation boucle ouverte")
    print("=" * 60)

    # Lister les scenarios et sequences
    if not sequences_dir.exists():
        print("\n  [ERREUR] Repertoire sequences/ non trouve")
        return

    scenarios = []
    for item in sorted(sequences_dir.iterdir()):
        if item.is_dir():
            seqs = sorted([d for d in item.iterdir() if d.is_dir() and d.name.startswith('sampling')])
            if seqs:
                scenarios.append((item.name, seqs))

    if not scenarios:
        print("\n  [ERREUR] Aucune sequence trouvee")
        return

    # Afficher les scenarios
    print("\n  Scenarios disponibles:")
    all_seqs = []
    idx = 1
    for scenario_name, seqs in scenarios:
        print(f"\n    {scenario_name}:")
        for seq_dir in seqs[:10]:  # limiter l'affichage
            cap_file = seq_dir / "captures.jsonl"
            if cap_file.exists():
                with open(cap_file) as f:
                    n = sum(1 for line in f if line.strip())
                print(f"      [{idx}] {seq_dir.name} ({n} samples)")
                all_seqs.append(seq_dir)
                idx += 1
        if len(seqs) > 10:
            print(f"      ... et {len(seqs) - 10} autres")
            for seq_dir in seqs[10:]:
                all_seqs.append(seq_dir)

    choice = input(f"\n  Sequence a simuler (1-{len(all_seqs)}) : ").strip()
    try:
        seq_idx = int(choice) - 1
        seq_dir = all_seqs[seq_idx]
    except (ValueError, IndexError):
        print("  Choix invalide.")
        return

    # Charger la sequence
    captures = []
    labels = []
    with open(seq_dir / "captures.jsonl") as f:
        for line in f:
            if line.strip():
                captures.append(json.loads(line))
    with open(seq_dir / "labels.jsonl") as f:
        for line in f:
            if line.strip():
                labels.append(json.loads(line))

    captures = np.array(captures, dtype=np.float32)
    labels = np.array(labels, dtype=np.float32)

    print(f"\n  Sequence: {seq_dir.name} ({len(captures)} samples)")
    print(f"  Simulation en cours...")

    # Simuler: pour chaque timestep, construire le vecteur complet et inferer
    import collections
    prev_vectors = collections.deque(maxlen=DELTA_STEPS)
    predictions = []
    feature_mask = stats.get('feature_mask')

    for t in range(len(captures)):
        raw_27 = captures[t]
        raw_29 = compute_engineered_features(raw_27)
        full = build_full_vector(raw_29, prev_vectors, feature_mask)
        pred = inference(model, full, stats)
        predictions.append(pred)
        prev_vectors.append(raw_29.copy())

    predictions = np.array(predictions)

    # Metriques
    mse = float(((predictions - labels) ** 2).mean())
    mae = float(np.abs(predictions - labels).mean())
    ss_res = ((predictions - labels) ** 2).sum()
    ss_tot = ((labels - labels.mean(axis=0)) ** 2).sum()
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0

    print(f"\n  Resultats sur la sequence:")
    print(f"    MSE:  {mse:.4f}")
    print(f"    MAE:  {mae:.4f}")
    print(f"    R2:   {r2:.4f}")

    # Visualiser
    timesteps = np.arange(len(captures))

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    axes[0].plot(timesteps, labels[:, 0] * 50, 'b-', alpha=0.7, label='Reel')
    axes[0].plot(timesteps, predictions[:, 0] * 50, 'r--', alpha=0.7, label='Predit')
    axes[0].set_ylabel('Vitesse Gauche')
    axes[0].set_title(f'Simulation boucle ouverte - {seq_dir.name}')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(timesteps, labels[:, 1] * 50, 'b-', alpha=0.7, label='Reel')
    axes[1].plot(timesteps, predictions[:, 1] * 50, 'r--', alpha=0.7, label='Predit')
    axes[1].set_ylabel('Vitesse Droite')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)

    real_steering = (labels[:, 0] - labels[:, 1]) * 50
    pred_steering = (predictions[:, 0] - predictions[:, 1]) * 50
    axes[2].plot(timesteps, real_steering, 'b-', alpha=0.7, label='Reel')
    axes[2].plot(timesteps, pred_steering, 'r--', alpha=0.7, label='Predit')
    axes[2].axhline(y=0, color='k', linewidth=0.5)
    axes[2].set_ylabel('Steering (L-R)')
    axes[2].set_xlabel('Timestep')
    axes[2].legend()
    axes[2].grid(True, alpha=0.3)

    plt.tight_layout()

    if save_dir:
        save_dir.mkdir(parents=True, exist_ok=True)
        fname = save_dir / f"simulation_{seq_dir.name.replace(' ', '_')}.png"
        plt.savefig(fname, dpi=150, bbox_inches='tight')
        print(f"  Graphique sauvegarde: {fname}")

    plt.show()
    plt.close()
    print()


# ============================================================
# Menu principal
# ============================================================

def run_simulation_menu(script_dir: Path, state: dict):
    """Menu interactif de simulation et evaluation avancee."""

    checkpoints_dir = script_dir / "checkpoints"
    data_dir = script_dir / "data"
    sequences_dir = script_dir / "sequences"
    sim_output_dir = script_dir / "simulation_results"

    # Verifier le modele
    if not state.get('has_model'):
        print("\n  [ERREUR] Aucun modele entraine. Entrainez d'abord un modele (option 3).")
        return

    model, stats = load_model_and_stats(checkpoints_dir)
    if model is None:
        return

    info = state.get('model_info', {})
    arch = ' -> '.join(map(str, info.get('hidden_dims', [])))
    val_loss = info.get('val_loss', 0)

    while True:
        print("\n" + "=" * 60)
        print("  Simulation & Evaluation avancee")
        print("=" * 60)
        print(f"  Modele: {info.get('input_dim', '?')} -> [{arch}] -> {info.get('output_dim', '?')} "
              f"(val_loss: {val_loss:.6f})")
        print()
        print("  [1] Tests scenariques (inputs synthetiques)")
        print("  [2] Metriques par categorie d'action")
        print("  [3] Ablation de features")
        print("  [4] Simulation boucle ouverte (sur sequence reelle)")
        print("  [R] Retour au menu principal")

        choice = input("\n  Choix : ").strip().upper()

        if choice == '1':
            run_scenario_tests(model, stats, data_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '2':
            run_per_category_metrics(model, stats, data_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '3':
            run_feature_ablation(data_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '4':
            run_open_loop_simulation(model, stats, sequences_dir, sim_output_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == 'R':
            break

        else:
            print("  Choix invalide.")
