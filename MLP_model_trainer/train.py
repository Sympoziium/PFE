#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Point d'entree interactif du pipeline d'entrainement MLP pour le controle du robot Zumi.

Menu interactif :
  [1] Agreger les sequences (consolide tous les scenarios -> data/)
  [2] Analyser le dataset (statistiques + graphiques)
  [3] Entrainer un modele (profils par defaut ou personnalise)
  [Q] Quitter

Usage:
    python train.py                # Lance le menu interactif
    python train.py --headless     # Mode automatique (parametres par defaut)
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau

from dataset import ZumiControlDataset, create_data_loaders
from model import create_model, ZumiMLP


# ══════════════════════════════════════════════════════════════
#  Profils d'entrainement par defaut
# ══════════════════════════════════════════════════════════════

TRAINING_PROFILES = {
    'rapide': {
        'name': 'Rapide',
        'description': 'Test rapide, petit modele',
        'model_size': 'small',
        'hidden_dims': [32, 16],
        'epochs': 50,
        'batch_size': 64,
        'lr': 1e-3,
        'weight_decay': 1e-4,
    },
    'equilibre': {
        'name': 'Equilibre',
        'description': 'Bon compromis qualite/temps',
        'model_size': 'medium',
        'hidden_dims': [64, 32],
        'epochs': 100,
        'batch_size': 32,
        'lr': 1e-3,
        'weight_decay': 1e-4,
    },
    'precision': {
        'name': 'Precision',
        'description': 'Meilleure qualite, plus long',
        'model_size': 'large',
        'hidden_dims': [128, 64, 32],
        'epochs': 200,
        'batch_size': 16,
        'lr': 5e-4,
        'weight_decay': 1e-5,
    },
}


# ══════════════════════════════════════════════════════════════
#  Classe Trainer (inchangee)
# ══════════════════════════════════════════════════════════════

def load_environment_config(script_dir: Path) -> dict:
    """Charge la configuration d'environnement generee par validate_env.py.

    Si le fichier n'existe pas, le genere automatiquement.
    """
    config_path = script_dir / "environment_config.json"

    # Générer si n'existe pas
    if not config_path.exists():
        print("\n📊 Configuration d'environnement non trouvée, génération automatique...\n")
        try:
            import validate_env
            config = validate_env.generate_config(verbose=False)
            validate_env.save_config(config, config_path)
            # Appliquer les configs PyTorch
            validate_env.apply_pytorch_config(config)
        except Exception as e:
            print(f"⚠️  Erreur lors de la génération de la config: {e}")
            return None
    else:
        # Charger depuis le fichier
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            print(f"✅ Configuration chargée: {config_path}")

            # Appliquer les configs PyTorch
            try:
                import validate_env
                validate_env.apply_pytorch_config(config)
            except Exception as e:
                print(f"⚠️  Erreur lors de l'application de la config PyTorch: {e}")
        except Exception as e:
            print(f"⚠️  Erreur lors du chargement de la config: {e}")
            return None

    return config


class Trainer:
    """Classe d'entraînement du modèle MLP."""

    def __init__(
        self,
        model: nn.Module,
        train_loader,
        val_loader,
        device: torch.device,
        lr: float = 1e-3,
        weight_decay: float = 1e-4,
        norm_stats: dict = None
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device
        self.norm_stats = norm_stats or {}

        self.criterion = nn.MSELoss()
        self.optimizer = optim.AdamW(
            model.parameters(),
            lr=lr,
            weight_decay=weight_decay
        )
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=10
        )

        # Historique
        self.history = {
            "train_loss": [],
            "val_loss": [],
            "lr": []
        }
        self.best_val_loss = float('inf')

    def train_epoch(self) -> float:
        """Entraîne le modèle pour une époque."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for states, commands in self.train_loader:
            states = states.to(self.device)
            commands = commands.to(self.device)

            self.optimizer.zero_grad()
            predictions = self.model(states)
            loss = self.criterion(predictions, commands)
            loss.backward()

            # Gradient clipping pour stabilité
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    @torch.no_grad()
    def validate(self) -> float:
        """Évalue le modèle sur le set de validation."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        for states, commands in self.val_loader:
            states = states.to(self.device)
            commands = commands.to(self.device)

            predictions = self.model(states)
            loss = self.criterion(predictions, commands)

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    @torch.no_grad()
    def evaluate(self, test_loader=None) -> dict:
        """Évalue le modèle avec plusieurs métriques détaillées.

        Args:
            test_loader: DataLoader d'évaluation. Par défaut utilise val_loader.

        Returns:
            dict: Dictionnaire contenant MSE, MAE, RMSE, R²
        """
        if test_loader is None:
            test_loader = self.val_loader

        self.model.eval()
        all_predictions = []
        all_targets = []

        for states, commands in test_loader:
            states = states.to(self.device)
            predictions = self.model(states)

            all_predictions.append(predictions.cpu().numpy())
            all_targets.append(commands.numpy())

        predictions = np.concatenate(all_predictions)
        targets = np.concatenate(all_targets)

        # Calcul des métriques
        mse = np.mean((predictions - targets) ** 2)
        mae = np.mean(np.abs(predictions - targets))
        rmse = np.sqrt(mse)

        # R² (coefficient de détermination)
        ss_res = np.sum((targets - predictions) ** 2)
        ss_tot = np.sum((targets - np.mean(targets)) ** 2)
        r2 = 1 - (ss_res / ss_tot)

        return {
            "mse": mse,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "predictions": predictions,
            "targets": targets
        }

    def visualize_results(self, metrics: dict, save_dir: Path):
        """Crée les visualisations de résultats du modèle.

        Args:
            metrics: Dictionnaire retourné par evaluate()
            save_dir: Répertoire de sauvegarde des visualisations
        """
        save_dir.mkdir(parents=True, exist_ok=True)

        predictions = metrics["predictions"]
        targets = metrics["targets"]

        # === Figure 1: Prédictions vs Cibles (scatter plot) ===
        n_outputs = targets.shape[1]
        fig, axes = plt.subplots(1, n_outputs, figsize=(6 * n_outputs, 5))

        # Adapter pour un seul output
        if n_outputs == 1:
            axes = [axes]

        output_names = ["Vitesse Gauche", "Vitesse Droite"] if n_outputs == 2 else [f"Output {i}" for i in range(n_outputs)]

        for i, ax in enumerate(axes):
            ax.scatter(targets[:, i], predictions[:, i], alpha=0.5, s=30)
            ax.plot([-1, 1], [-1, 1], 'r--', linewidth=2, label='Parfait')
            ax.set_xlabel('Cible')
            ax.set_ylabel('Prédiction')
            ax.set_title(output_names[i])
            ax.legend()
            ax.grid(True, alpha=0.3)
            ax.set_xlim(-1.1, 1.1)
            ax.set_ylim(-1.1, 1.1)

        plt.tight_layout()
        predictions_path = save_dir / "predictions.png"
        plt.savefig(predictions_path, dpi=150, bbox_inches='tight')
        print(f"  Graphique sauvegardé: {predictions_path}")
        plt.close()

        # === Figure 2: Erreur vs Cibles (residuals plot) ===
        fig, axes = plt.subplots(1, n_outputs, figsize=(6 * n_outputs, 5))

        if n_outputs == 1:
            axes = [axes]

        for i, ax in enumerate(axes):
            errors = predictions[:, i] - targets[:, i]
            ax.scatter(targets[:, i], errors, alpha=0.5, s=30)
            ax.axhline(y=0, color='r', linestyle='--', linewidth=2)
            ax.set_xlabel('Cible')
            ax.set_ylabel('Erreur (Prédiction - Cible)')
            ax.set_title(f"Erreurs - {output_names[i]}")
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        residuals_path = save_dir / "residuals.png"
        plt.savefig(residuals_path, dpi=150, bbox_inches='tight')
        print(f"  Graphique sauvegardé: {residuals_path}")
        plt.close()

        # === Figure 3: Courbe de perte d'entraînement ===
        fig, ax = plt.subplots(figsize=(10, 6))

        epochs_range = range(1, len(self.history["train_loss"]) + 1)
        ax.plot(epochs_range, self.history["train_loss"], 'b-', label='Train Loss', linewidth=2)
        ax.plot(epochs_range, self.history["val_loss"], 'r-', label='Val Loss', linewidth=2)
        ax.set_xlabel('Époque')
        ax.set_ylabel('Loss (MSE)')
        ax.set_title('Courbe d\'entraînement')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        loss_path = save_dir / "training_loss.png"
        plt.savefig(loss_path, dpi=150, bbox_inches='tight')
        print(f"  Graphique sauvegardé: {loss_path}")
        plt.close()

        # === Figure 4: Learning Rate Evolution ===
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(epochs_range, self.history["lr"], 'g-', linewidth=2)
        ax.set_xlabel('Époque')
        ax.set_ylabel('Learning Rate')
        ax.set_title('Évolution du Learning Rate')
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')

        plt.tight_layout()
        lr_path = save_dir / "learning_rate.png"
        plt.savefig(lr_path, dpi=150, bbox_inches='tight')
        print(f"  Graphique sauvegardé: {lr_path}")
        plt.close()

    def train(
        self,
        epochs: int,
        save_dir: Path,
        early_stopping_patience: int = 20
    ) -> dict:
        """Boucle d'entraînement principale.

        Args:
            epochs: Nombre d'époques
            save_dir: Répertoire de sauvegarde
            early_stopping_patience: Arrêt si pas d'amélioration pendant N époques

        Returns:
            dict: Historique d'entraînement
        """
        save_dir.mkdir(parents=True, exist_ok=True)
        best_model_path = save_dir / "best_model.pt"
        no_improve_count = 0

        print(f"\n{'='*60}")
        print(f"Début de l'entraînement - {epochs} époques")
        print(f"Device: {self.device}")
        print(f"{'='*60}\n")

        start_time = time.time()

        for epoch in range(1, epochs + 1):
            epoch_start = time.time()

            # Entraînement et validation
            train_loss = self.train_epoch()
            val_loss = self.validate()

            # Mise à jour du scheduler
            current_lr = self.optimizer.param_groups[0]['lr']
            self.scheduler.step(val_loss)

            # Enregistrement historique
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["lr"].append(current_lr)

            # Sauvegarde du meilleur modèle
            is_best = val_loss < self.best_val_loss
            if is_best:
                self.best_val_loss = val_loss
                no_improve_count = 0
                checkpoint_data = {
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'val_loss': val_loss,
                    'input_dim': self.model.input_dim,
                    'output_dim': self.model.output_dim,
                    'hidden_dims': self.model.hidden_dims,
                }
                if self.norm_stats:
                    checkpoint_data['feature_mean'] = self.norm_stats['feature_mean']
                    checkpoint_data['feature_std'] = self.norm_stats['feature_std']
                    checkpoint_data['feature_mask'] = self.norm_stats.get('feature_mask')
                    checkpoint_data['motor_speed_max'] = self.norm_stats.get('motor_speed_max', 50.0)
                torch.save(checkpoint_data, best_model_path)
            else:
                no_improve_count += 1

            # Affichage
            epoch_time = time.time() - epoch_start
            best_marker = " *" if is_best else ""
            print(
                f"Epoch {epoch:3d}/{epochs} | "
                f"Train: {train_loss:.6f} | "
                f"Val: {val_loss:.6f} | "
                f"LR: {current_lr:.2e} | "
                f"Time: {epoch_time:.1f}s{best_marker}"
            )

            # Early stopping
            if no_improve_count >= early_stopping_patience:
                print(f"\nEarly stopping: pas d'amélioration depuis {early_stopping_patience} époques")
                break

        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"Entraînement terminé en {total_time:.1f}s")
        print(f"Meilleur val_loss: {self.best_val_loss:.6f}")
        print(f"Modèle sauvegardé: {best_model_path}")
        print(f"{'='*60}\n")

        return self.history


def save_training_report(
    save_dir: Path,
    model: nn.Module,
    history: dict,
    config: dict,
    dataset_stats: dict,
    metrics: dict = None
):
    """Sauvegarde un rapport JSON de l'entraînement.

    Args:
        save_dir: Répertoire de sauvegarde
        model: Le modèle entraîné
        history: Historique d'entraînement
        args: Arguments de ligne de commande
        dataset_stats: Statistiques du dataset
        metrics: Métriques d'évaluation (optionnel)
    """
    report = {
        "timestamp": datetime.now().isoformat(),
        "model": {
            "input_dim": model.input_dim,
            "output_dim": model.output_dim,
            "hidden_dims": model.hidden_dims,
            "n_parameters": model.count_parameters()
        },
        "training": {
            "epochs": len(history["train_loss"]),
            "best_val_loss": min(history["val_loss"]),
            "final_train_loss": history["train_loss"][-1],
            "final_val_loss": history["val_loss"][-1],
        },
        "hyperparameters": {
            "learning_rate": config.get('lr', 1e-3),
            "batch_size": config.get('batch_size', 32),
            "weight_decay": config.get('weight_decay', 1e-4),
            "profile": config.get('name', 'custom')
        },
        "dataset": dataset_stats,
        "history": history
    }

    # Ajouter les métriques d'évaluation si disponibles
    if metrics:
        report["evaluation"] = {
            "mse": float(metrics["mse"]),
            "mae": float(metrics["mae"]),
            "rmse": float(metrics["rmse"]),
            "r2": float(metrics["r2"])
        }

    report_path = save_dir / "training_report.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"  Rapport sauvegarde: {report_path}")


# ══════════════════════════════════════════════════════════════
#  Utilitaires du menu
# ══════════════════════════════════════════════════════════════

def check_data_state(data_dir: Path, sequences_dir: Path) -> dict:
    """
    Analyse l'etat actuel des donnees.
    Retourne un dict indiquant quelles etapes ont deja ete completees.
    """
    state = {}

    # Verifier les scenarios disponibles
    state['n_scenarios'] = 0
    state['scenarios'] = []
    if sequences_dir.exists():
        for item in sorted(sequences_dir.iterdir()):
            if item.is_dir():
                sampling_dirs = list(item.glob('sampling_*'))
                if sampling_dirs:
                    state['scenarios'].append({
                        'name': item.name,
                        'n_sequences': len(sampling_dirs)
                    })
        state['n_scenarios'] = len(state['scenarios'])

    # Verifier le dataset agrege
    captures_file = data_dir / "captures.jsonl"
    labels_file = data_dir / "labels.jsonl"
    state['has_dataset'] = captures_file.exists() and labels_file.exists()
    state['n_samples'] = 0

    if state['has_dataset']:
        with open(captures_file, 'r') as f:
            state['n_samples'] = sum(1 for line in f if line.strip())

    # Verifier les modeles entraines
    checkpoints_dir = data_dir.parent / "checkpoints"
    state['has_model'] = False
    state['model_info'] = None

    best_model_path = checkpoints_dir / "best_model.pt"
    if best_model_path.exists():
        state['has_model'] = True
        try:
            checkpoint = torch.load(best_model_path, map_location='cpu', weights_only=False)
            state['model_info'] = {
                'input_dim': checkpoint.get('input_dim'),
                'output_dim': checkpoint.get('output_dim'),
                'hidden_dims': checkpoint.get('hidden_dims'),
                'val_loss': checkpoint.get('val_loss'),
            }
        except Exception:
            pass

    # Verifier le modele tflite
    export_dir = data_dir.parent / "export"
    state['has_tflite'] = False
    tflite_path = export_dir / "zumi_mlp.tflite"
    tflite_quant_path = export_dir / "zumi_mlp_quant.tflite"
    if tflite_path.exists():
        state['has_tflite'] = True
        state['tflite_path'] = tflite_path
        state['tflite_size'] = tflite_path.stat().st_size / 1024
    elif tflite_quant_path.exists():
        state['has_tflite'] = True
        state['tflite_path'] = tflite_quant_path
        state['tflite_size'] = tflite_quant_path.stat().st_size / 1024

    return state


def show_main_menu(script_dir: Path) -> tuple:
    """
    Affiche le menu principal interactif avec l'etat actuel des donnees.
    Retourne (choix, state).
    """
    data_dir = script_dir / "data"
    sequences_dir = script_dir / "sequences"

    state = check_data_state(data_dir, sequences_dir)

    def status(ok, text):
        return f"    {'[OK]' if ok else '[  ]'} {text}"

    print("\n" + "=" * 60)
    print("  MLP Trainer - Menu Principal")
    print("=" * 60)

    # -- Etat actuel --
    print("\n  Etat actuel :")

    # Scenarios
    if state['n_scenarios'] > 0:
        total_seqs = sum(s['n_sequences'] for s in state['scenarios'])
        scenarios_names = ', '.join(s['name'] for s in state['scenarios'])
        print(status(True, f"Scenarios disponibles: {state['n_scenarios']} ({scenarios_names})"))
        print(f"         Total sequences: {total_seqs}")
    else:
        print(status(False, "Aucun scenario trouve dans sequences/"))

    # Dataset
    if state['has_dataset']:
        print(status(True, f"Dataset agrege: {state['n_samples']} echantillons"))
    else:
        print(status(False, "Dataset non agrege (data/captures.jsonl absent)"))

    # Modele
    if state['has_model'] and state['model_info']:
        info = state['model_info']
        arch = ' -> '.join(map(str, info['hidden_dims'])) if info['hidden_dims'] else 'N/A'
        val_loss = info.get('val_loss', 0)
        print(status(True, f"Modele entraine: {info['input_dim']} -> [{arch}] -> {info['output_dim']}"))
        print(f"         Val loss: {val_loss:.6f}")
    else:
        print(status(False, "Aucun modele entraine"))

    # TFLite
    if state['has_tflite']:
        print(status(True, f"Modele TFLite: {state['tflite_size']:.1f} KB"))
    else:
        print(status(False, "Pas de modele TFLite exporte"))

    # -- Options du menu --
    print(f"\n  Options :")
    print(f"    [1] Agreger les sequences (consolide tous les scenarios -> data/)")
    print(f"    [2] Analyser le dataset (statistiques + graphiques)")
    print(f"    [3] Entrainer un modele")
    print(f"    [Q] Quitter")

    # Validation du choix
    valid_choices = {'1', '2', '3', 'Q'}

    while True:
        choice = input(f"\n  Choix : ").strip().upper()
        if choice in valid_choices:
            return choice, state
        print(f"  Choix invalide. Options disponibles : {', '.join(sorted(valid_choices))}")


def _count_params(input_dim, hidden_dims, output_dim=2):
    """Calcule le nombre de parametres d'un MLP avec les dimensions donnees."""
    total = 0
    prev = input_dim
    for h in hidden_dims:
        total += prev * h + h  # poids + biais
        prev = h
    total += prev * output_dim + output_dim
    return total


def suggest_training_profile(dataset) -> dict:
    """Analyse le dataset et propose un profil d'entrainement adapte.

    Calcule les hidden_dims pour maintenir un ratio params/samples entre 1:5 et 1:10.
    Adapte les epochs, batch_size, lr et weight_decay en consequence.

    Detecte aussi le cas ou le dataset est trop petit pour apprendre une relation
    non-lineaire (architecture minimum requise > budget disponible).
    """
    n_samples = len(dataset)
    raw_dim = dataset.input_dim

    # Detecter les features mortes (std < 1e-6) et construire le masque
    stds = dataset.captures.std(axis=0)
    active_indices = [i for i in range(raw_dim) if stds[i] > 1e-6]
    n_active = len(active_indices)
    n_dead = raw_dim - n_active

    # Appliquer le masque si >0 features mortes
    feature_mask = active_indices if n_dead > 0 else None
    # Le pipeline ajoute 5 delta features (IR_bot_R/L, IR_diff, IR_sum, gyro_z)
    n_deltas = 5
    effective_dim = (n_active if feature_mask else raw_dim) + n_deltas

    # Budget de parametres: viser ratio 1:5 a 1:10
    target_ratio = 7  # milieu de la fourchette
    param_budget = n_samples // target_ratio

    # Chercher les hidden_dims qui respectent le budget (avec effective_dim)
    candidates = [
        [16],
        [32, 16],
        [64, 32],
        [64, 32, 16],
        [128, 64],
        [128, 64, 32],
        [256, 128, 64],
    ]

    best_dims = [32, 16]  # defaut conservateur
    for dims in candidates:
        n_params = _count_params(effective_dim, dims)
        if n_params <= param_budget:
            best_dims = dims

    n_params = _count_params(effective_dim, best_dims)
    actual_ratio = n_samples / n_params if n_params > 0 else 0

    # --- Detection dataset insuffisant ---
    min_viable_dims = [32, 16]
    min_viable_params = _count_params(effective_dim, min_viable_dims)
    min_samples_needed = min_viable_params * target_ratio

    warnings = []
    if len(best_dims) < 2:
        warnings.append(
            f"[WARN] Dataset insuffisant pour l'apprentissage non-lineaire!\n"
            f"           Le budget ({param_budget} params) ne permet qu'une seule couche cachee,\n"
            f"           ce qui est insuffisant pour capter des relations non-lineaires\n"
            f"           (ex: suivi de ligne, reactions aux virages).\n"
            f"           Architecture minimum viable: {effective_dim} -> {' -> '.join(map(str, min_viable_dims))} -> 2\n"
            f"             = {min_viable_params:,} parametres (ratio {target_ratio}:1 -> {min_samples_needed:,} echantillons)\n"
            f"           Echantillons actuels: {n_samples:,}\n"
            f"           Objectif minimum: ~{min_samples_needed:,} echantillons"
        )

    # Adapter les hyperparametres selon la taille du dataset
    if n_samples < 5000:
        epochs, batch_size, lr, wd = 150, 32, 1e-3, 1e-4
    elif n_samples < 20000:
        epochs, batch_size, lr, wd = 100, 64, 1e-3, 1e-4
    else:
        epochs, batch_size, lr, wd = 80, 128, 5e-4, 1e-4

    profile = {
        'name': 'Adaptatif',
        'description': f'Adapte au dataset ({n_samples} samples, {n_active} features actives)',
        'hidden_dims': best_dims,
        'epochs': epochs,
        'batch_size': batch_size,
        'lr': lr,
        'weight_decay': wd,
        'feature_mask': feature_mask,
    }

    return profile, n_params, actual_ratio, n_active, warnings


def choose_training_profile(dataset=None) -> dict:
    """Demande a l'utilisateur le profil d'entrainement."""

    suggested = None
    if dataset is not None:
        suggested, n_params, ratio, n_active, warnings = suggest_training_profile(dataset)

        mask = suggested.get('feature_mask')
        n_deltas = 5  # delta features ajoutees par le pipeline
        base_active = n_active
        effective_dim = (len(mask) if mask else dataset.input_dim) + n_deltas

        print(f"\n  Profil suggere (base sur l'analyse du dataset) :")
        print(f"    Dataset: {len(dataset)} echantillons, {dataset.input_dim} features ({base_active} actives + {n_deltas} deltas)")
        if mask:
            print(f"    Masque: {dataset.input_dim}-dim -> {base_active}-dim actives + {n_deltas} deltas = {effective_dim}-dim")
        print(f"    Architecture: {effective_dim} -> {' -> '.join(map(str, suggested['hidden_dims']))} -> 2")
        print(f"    Parametres: {n_params:,} (ratio samples/params: {ratio:.1f}:1)")
        print(f"    Epochs: {suggested['epochs']}, Batch: {suggested['batch_size']}, LR: {suggested['lr']}")

        if ratio < 2:
            print(f"    [WARN] Ratio faible ({ratio:.1f}:1) - risque de surapprentissage.")
            print(f"           Envisagez de collecter plus d'echantillons.")

        for w in warnings:
            print(f"    {w}")

    print(f"\n  Options :")
    if suggested:
        print(f"    [1] Adaptatif  - profil suggere ci-dessus (recommande)")
    print(f"    [2] Custom     - Configuration personnalisee")

    while True:
        c = input(f"\n  Choix ({('1/' if suggested else '')}2) : ").strip()
        if c == '1' and suggested:
            return suggested
        elif c == '2':
            config = configure_custom_profile()
            # Hériter feature_mask du profil suggéré
            if suggested:
                config['feature_mask'] = suggested.get('feature_mask')
            # Afficher un avertissement si le custom est risque
            if dataset is not None:
                custom_params = _count_params(dataset.input_dim, config['hidden_dims'])
                custom_ratio = len(dataset) / custom_params if custom_params > 0 else 0
                print(f"\n    Parametres: {custom_params:,} (ratio samples/params: {custom_ratio:.1f}:1)")
                if custom_ratio < 2:
                    print(f"    [WARN] Ratio faible - risque de surapprentissage avec ce dataset.")
                elif custom_ratio > 20:
                    print(f"    [INFO] Modele tres petit par rapport aux donnees. Pourrait sous-apprendre.")
            return config
        print(f"  Choix invalide.")


def configure_custom_profile() -> dict:
    """Configure un profil d'entrainement personnalise."""
    print(f"\n  Configuration personnalisee :")

    config = {
        'name': 'Custom',
        'description': 'Configuration personnalisee',
    }

    # Nombre de couches cachees
    while True:
        try:
            n_layers = int(input("    Nombre de couches cachees (1-5, defaut: 2) : ").strip() or "2")
            if 1 <= n_layers <= 5:
                break
            print("    Doit etre entre 1 et 5.")
        except ValueError:
            print("    Valeur invalide.")

    # Dimensions des couches
    hidden_dims = []
    for i in range(n_layers):
        while True:
            try:
                default = 64 // (2 ** i) if i < 3 else 16
                dim = int(input(f"    Dimension couche {i+1} (defaut: {default}) : ").strip() or str(default))
                if 8 <= dim <= 512:
                    hidden_dims.append(dim)
                    break
                print("    Doit etre entre 8 et 512.")
            except ValueError:
                print("    Valeur invalide.")

    config['hidden_dims'] = hidden_dims

    # Epochs
    while True:
        try:
            epochs = int(input("    Nombre d'epochs (10-500, defaut: 100) : ").strip() or "100")
            if 10 <= epochs <= 500:
                config['epochs'] = epochs
                break
            print("    Doit etre entre 10 et 500.")
        except ValueError:
            print("    Valeur invalide.")

    # Batch size
    while True:
        try:
            batch = int(input("    Batch size (8-256, defaut: 32) : ").strip() or "32")
            if 8 <= batch <= 256:
                config['batch_size'] = batch
                break
            print("    Doit etre entre 8 et 256.")
        except ValueError:
            print("    Valeur invalide.")

    # Learning rate
    while True:
        try:
            lr = float(input("    Learning rate (ex: 0.001, defaut: 0.001) : ").strip() or "0.001")
            if 1e-6 <= lr <= 1:
                config['lr'] = lr
                break
            print("    Doit etre entre 1e-6 et 1.")
        except ValueError:
            print("    Valeur invalide.")

    # Weight decay
    while True:
        try:
            wd = float(input("    Weight decay (ex: 0.0001, defaut: 0.0001) : ").strip() or "0.0001")
            if 0 <= wd <= 0.1:
                config['weight_decay'] = wd
                break
            print("    Doit etre entre 0 et 0.1.")
        except ValueError:
            print("    Valeur invalide.")

    # Resume
    print(f"\n    Configuration:")
    print(f"      Hidden dims: {config['hidden_dims']}")
    print(f"      Epochs: {config['epochs']}")
    print(f"      Batch size: {config['batch_size']}")
    print(f"      Learning rate: {config['lr']}")
    print(f"      Weight decay: {config['weight_decay']}")

    return config


# ══════════════════════════════════════════════════════════════
#  Actions du menu
# ══════════════════════════════════════════════════════════════

def run_aggregate_sequences(script_dir: Path):
    """Execute l'agregation des sequences."""
    print("\n" + "=" * 60)
    print("  Agregation des sequences")
    print("=" * 60 + "\n")

    # Import et execution du module aggregate_sequences
    try:
        from aggregate_sequences import aggregate_all_scenarios, discover_scenarios

        sequences_root = script_dir / "sequences"
        output_dir = script_dir / "data"

        if not sequences_root.exists():
            print(f"  ERREUR: Repertoire sequences/ non trouve: {sequences_root}")
            return False

        scenarios = discover_scenarios(sequences_root)
        if not scenarios:
            print("  ERREUR: Aucun scenario trouve!")
            return False

        print(f"  Scenarios trouves: {', '.join(scenarios)}")
        print()

        success = aggregate_all_scenarios(
            sequences_root, output_dir,
            add_scenario_id=False,
            verbose=True
        )

        if success:
            print("\n" + "=" * 60)
            print("  Agregation terminee avec succes!")
            print("=" * 60)
        else:
            print("\n  ERREUR: Agregation echouee")

        return success

    except ImportError as e:
        print(f"  ERREUR: Impossible d'importer aggregate_sequences: {e}")
        return False


def run_analyze_dataset(script_dir: Path):
    """Execute l'analyse du dataset avec generation des graphiques."""
    print("\n" + "=" * 60)
    print("  Analyse du dataset")
    print("=" * 60 + "\n")

    try:
        from analyze_dataset import load_dataset, analyze_dataset, plot_analysis

        data_dir = script_dir / "data"
        output_dir = script_dir / "dataset_analysis"

        if not data_dir.exists():
            print(f"  ERREUR: Repertoire data/ non trouve: {data_dir}")
            print("  -> Executez d'abord l'option [1] Agreger les sequences")
            return False

        print(f"  Chargement du dataset depuis {data_dir}...")
        captures, labels = load_dataset(data_dir)

        if captures is None:
            print("  ERREUR: Impossible de charger le dataset")
            return False

        # Analyse textuelle
        stats = analyze_dataset(captures, labels)

        # Generation des graphiques
        print(f"\n  Generation des graphiques vers {output_dir}...")
        print()
        plot_analysis(captures, labels, output_dir)

        print("\n" + "=" * 60)
        print("  Analyse terminee!")
        print(f"  Graphiques sauvegardes dans: {output_dir}")
        print("=" * 60)

        return True

    except ImportError as e:
        print(f"  ERREUR: Impossible d'importer analyze_dataset: {e}")
        return False


def run_training(script_dir: Path, state: dict):
    """Execute le workflow d'entrainement complet."""
    print("\n" + "=" * 60)
    print("  Entrainement du modele MLP")
    print("=" * 60)

    # Verifier que le dataset existe
    if not state['has_dataset']:
        print("\n  ERREUR: Dataset non disponible!")
        print("  -> Executez d'abord l'option [1] Agreger les sequences")
        return False

    # Chemins
    data_dir = script_dir / "data"
    save_dir = script_dir / "checkpoints"

    # Charger le dataset pour analyse (avant choix du profil)
    print("\n  Chargement du dataset pour analyse...")
    preview_dataset = ZumiControlDataset(str(data_dir))

    # Choisir le profil (adaptatif base sur le dataset)
    config = choose_training_profile(dataset=preview_dataset)

    print(f"\n  Profil selectionne: {config.get('name', 'Custom')}")
    print(f"  Hidden dims: {config.get('hidden_dims', [64, 32])}")
    print(f"  Epochs: {config.get('epochs', 100)}")
    print(f"  Batch size: {config.get('batch_size', 32)}")
    print(f"  Learning rate: {config.get('lr', 1e-3)}")
    print(f"  Weight decay: {config.get('weight_decay', 1e-4)}")

    # Confirmation
    confirm = input("\n  Lancer l'entrainement? (O/N) : ").strip().upper()
    if confirm != 'O':
        print("  Entrainement annule.")
        return False

    # Seed pour reproductibilite
    seed = 42
    torch.manual_seed(seed)

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"\n  Device: {device}")

    # Charger la configuration d'environnement
    print("\n  Chargement de la configuration d'environnement...")
    load_environment_config(script_dir)

    # Chargement des donnees avec dedup + masque + z-score + echantillonnage equilibre
    feature_mask = config.get('feature_mask')
    print("\n  Chargement des donnees (dedup + deltas + z-score + equilibrage)...")
    train_loader, val_loader, dataset = create_data_loaders(
        str(data_dir),
        batch_size=config.get('batch_size', 32),
        seed=seed,
        feature_mask=feature_mask,
        deduplicate=True,
        balanced_sampling=True
    )

    # Creation du modele avec la configuration custom
    hidden_dims = config.get('hidden_dims')
    if hidden_dims:
        model = ZumiMLP(
            input_dim=dataset.input_dim,
            output_dim=dataset.output_dim,
            hidden_dims=hidden_dims
        )
    else:
        model = create_model(
            input_dim=dataset.input_dim,
            output_dim=dataset.output_dim,
            model_size=config.get('model_size', 'medium')
        )

    print(f"\n{model.summary()}\n")

    # Stats de normalisation (calculees par create_data_loaders sur le train set)
    norm_stats = {}
    if hasattr(dataset, 'feature_mean'):
        norm_stats = {
            'feature_mean': dataset.feature_mean.tolist(),
            'feature_std': dataset.feature_std.tolist(),
            'feature_mask': dataset.feature_mask,
            'motor_speed_max': 50.0,
        }

    # Entraînement
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        lr=config.get('lr', 1e-3),
        weight_decay=config.get('weight_decay', 1e-4),
        norm_stats=norm_stats
    )

    history = trainer.train(
        epochs=config.get('epochs', 100),
        save_dir=save_dir
    )

    # === ÉVALUATION DÉTAILLÉE ===
    print(f"\n{'='*60}")
    print("ÉVALUATION DÉTAILLÉE DU MODÈLE")
    print(f"{'='*60}\n")

    # Charger le meilleur modèle sauvegardé
    best_model_path = save_dir / "best_model.pt"
    checkpoint = torch.load(best_model_path, map_location=device, weights_only=False)
    model.load_state_dict(checkpoint['model_state_dict'])

    # Évaluation avec métriques détaillées
    metrics = trainer.evaluate()

    # Affichage des métriques
    print("📊 Métriques d'évaluation:")
    print(f"  MSE:  {metrics['mse']:.6f}")
    print(f"  MAE:  {metrics['mae']:.6f}")
    print(f"  RMSE: {metrics['rmse']:.6f}")
    print(f"  R²:   {metrics['r2']:.6f}")
    print()

    # Interprétation RMSE
    rmse_value = metrics['rmse']
    if rmse_value < 0.1:
        rmse_status = "✅ Excellent"
    elif rmse_value < 0.2:
        rmse_status = "✓ Bon"
    elif rmse_value < 0.3:
        rmse_status = "⚠️ Acceptable"
    else:
        rmse_status = "❌ À améliorer"

    print(f"Interprétation RMSE: {rmse_status}")
    print()

    # Création des visualisations
    print("📈 Génération des visualisations...")
    trainer.visualize_results(metrics, save_dir)
    print()

    # Sauvegarde du rapport avec les métriques
    save_training_report(
        save_dir=save_dir,
        model=model,
        history=history,
        config=config,
        dataset_stats=dataset.get_statistics(),
        metrics=metrics
    )

    # === CONVERSION TFLITE ===
    print(f"\n{'='*60}")
    print("CONVERSION EN TFLITE")
    print(f"{'='*60}\n")

    convert_tflite = input("  Convertir le modele en TFLite? (O/N) : ").strip().upper()
    if convert_tflite == 'O':
        quantize = input("  Appliquer la quantization INT8? (O/N) : ").strip().upper() == 'O'
        run_convert_to_tflite(script_dir, quantize=quantize)

    print(f"\n{'='*60}")
    print("  Entrainement et evaluation termines!")
    print(f"  Resultats sauvegardes dans: {save_dir}")
    print(f"{'='*60}")

    return True


def run_convert_to_tflite(script_dir: Path, quantize: bool = False):
    """Execute la conversion en TFLite."""
    try:
        from convert_to_tflite import (
            load_pytorch_model, export_to_savedmodel,
            convert_savedmodel_to_tflite, verify_tflite_model,
            export_normalization_stats
        )

        model_path = script_dir / "checkpoints" / "best_model.pt"
        output_dir = script_dir / "export"

        if not model_path.exists():
            print(f"  ERREUR: Modele non trouve: {model_path}")
            return False

        output_dir.mkdir(parents=True, exist_ok=True)

        # Chemins de sortie
        savedmodel_path = output_dir / "zumi_mlp_tf"
        tflite_name = "zumi_mlp_quant.tflite" if quantize else "zumi_mlp.tflite"
        tflite_path = output_dir / tflite_name

        print("  Conversion PyTorch -> TFLite...")

        # 1. Charger le modele PyTorch
        model, checkpoint = load_pytorch_model(model_path)
        input_dim = checkpoint['input_dim']
        output_dim = checkpoint['output_dim']
        hidden_dims = checkpoint['hidden_dims']

        # 2. Exporter vers TensorFlow SavedModel
        export_to_savedmodel(model, input_dim, savedmodel_path, hidden_dims, output_dim)

        # 3. Convertir TensorFlow -> TFLite
        convert_savedmodel_to_tflite(savedmodel_path, tflite_path, quantize=quantize, input_dim=input_dim)

        # 4. Exporter les stats de normalisation z-score
        export_normalization_stats(checkpoint, output_dir)

        # 5. Verification
        verify_tflite_model(tflite_path, input_dim)

        print(f"\n  Fichier TFLite cree: {tflite_path}")
        print(f"  Pour deployer sur le robot:")
        print(f"    scp {tflite_path} pi@<ip_robot>:~/robot/models/")

        return True

    except ImportError as e:
        print(f"  ERREUR: Impossible d'importer convert_to_tflite: {e}")
        print("  Assurez-vous que TensorFlow est installe: pip install tensorflow>=2.13.0")
        return False
    except Exception as e:
        print(f"  ERREUR lors de la conversion: {e}")
        return False


# ══════════════════════════════════════════════════════════════
#  Point d'entree
# ══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Entrainement interactif du MLP Zumi")
    parser.add_argument("--headless", action="store_true",
                        help="Mode automatique (sans menu interactif)")
    parser.add_argument("--profile", type=str, default="equilibre",
                        choices=["rapide", "equilibre", "precision"],
                        help="Profil d'entrainement (mode headless)")

    args = parser.parse_args()

    script_dir = Path(__file__).parent

    # Mode headless (automatique)
    if args.headless:
        print("\n  Mode automatique active")
        config = TRAINING_PROFILES.get(args.profile, TRAINING_PROFILES['equilibre'])
        # ... implementation mode headless si necessaire
        return

    # Menu interactif
    while True:
        choice, state = show_main_menu(script_dir)

        if choice == '1':
            run_aggregate_sequences(script_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '2':
            run_analyze_dataset(script_dir)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == '3':
            run_training(script_dir, state)
            input("\n  Appuyez sur Entree pour continuer...")

        elif choice == 'Q':
            print("\n  Au revoir!")
            break


if __name__ == "__main__":
    main()
