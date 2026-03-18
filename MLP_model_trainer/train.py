#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script d'entraînement du MLP pour le contrôle du robot Zumi.

Exécute automatiquement validate_env.py au démarrage pour optimiser les paramètres.

Usage:
    python train.py                          # Entraînement avec paramètres optimisés
    python train.py --epochs 200 --lr 0.001  # Paramètres personnalisés (override config)
    python train.py --model-size small       # Modèle compact pour Pi Zero
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from torch.optim.lr_scheduler import ReduceLROnPlateau

from dataset import create_data_loaders
from model import create_model


def load_environment_config(script_dir: Path) -> dict:
    """Charge la configuration d'environnement générée par validate_env.py.

    Si le fichier n'existe pas, le génère automatiquement.
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
        weight_decay: float = 1e-4
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.device = device

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
                torch.save({
                    'epoch': epoch,
                    'model_state_dict': self.model.state_dict(),
                    'optimizer_state_dict': self.optimizer.state_dict(),
                    'val_loss': val_loss,
                    'input_dim': self.model.input_dim,
                    'output_dim': self.model.output_dim,
                    'hidden_dims': self.model.hidden_dims,
                }, best_model_path)
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
    args: argparse.Namespace,
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
            "learning_rate": args.lr,
            "batch_size": args.batch_size,
            "weight_decay": args.weight_decay,
            "model_size": args.model_size
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

    print(f"Rapport sauvegardé: {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Entraînement du MLP Zumi")
    parser.add_argument("--data-dir", type=str, default="data",
                        help="Répertoire des données")
    parser.add_argument("--save-dir", type=str, default="checkpoints",
                        help="Répertoire de sauvegarde")
    parser.add_argument("--epochs", type=int, default=None,
                        help="Nombre d'époques (auto si None)")
    parser.add_argument("--batch-size", type=int, default=None,
                        help="Taille des mini-batches (auto si None)")
    parser.add_argument("--lr", type=float, default=None,
                        help="Learning rate initial (auto si None)")
    parser.add_argument("--weight-decay", type=float, default=1e-4,
                        help="Weight decay (L2 regularization)")
    parser.add_argument("--model-size", type=str, default=None,
                        choices=["small", "medium", "large"],
                        help="Taille du modèle (auto si None)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Graine aléatoire")
    parser.add_argument("--no-cuda", action="store_true",
                        help="Désactiver CUDA")

    args = parser.parse_args()

    # Seed pour reproductibilité
    torch.manual_seed(args.seed)

    # Chemins
    script_dir = Path(__file__).parent

    # === CHARGER LA CONFIGURATION D'ENVIRONNEMENT ===
    print("\n" + "=" * 70)
    print("CHARGEMENT DE LA CONFIGURATION D'ENVIRONNEMENT")
    print("=" * 70)
    config = load_environment_config(script_dir)
    print()

    # Utiliser les recommandations si les paramètres ne sont pas spécifiés
    if config and config.get("recommendations"):
        recs = config["recommendations"]

        if args.epochs is None:
            args.epochs = recs.get("num_epochs", 100)
        if args.batch_size is None:
            args.batch_size = recs.get("batch_size", 32)
        if args.lr is None:
            args.lr = recs.get("learning_rate", 1e-3)
        if args.model_size is None:
            args.model_size = recs.get("model_size", "medium")

        print("💡 Paramètres optimisés appliqués:")
        print(f"  Epochs: {args.epochs}")
        print(f"  Batch Size: {args.batch_size}")
        print(f"  Learning Rate: {args.lr}")
        print(f"  Model Size: {args.model_size}")
        print()
    else:
        # Valeurs par défaut si pas de config
        if args.epochs is None:
            args.epochs = 100
        if args.batch_size is None:
            args.batch_size = 32
        if args.lr is None:
            args.lr = 1e-3
        if args.model_size is None:
            args.model_size = "medium"

    # Device
    device = torch.device("cpu")
    if not args.no_cuda and torch.cuda.is_available():
        device = torch.device("cuda")
    print(f"Using device: {device}")

    # Chemins
    data_dir = script_dir / args.data_dir
    save_dir = script_dir / args.save_dir

    # Chargement des données
    train_loader, val_loader, dataset = create_data_loaders(
        str(data_dir),
        batch_size=args.batch_size,
        seed=args.seed
    )

    # Création du modèle
    model = create_model(
        input_dim=dataset.input_dim,
        output_dim=dataset.output_dim,
        model_size=args.model_size
    )
    print(f"\n{model.summary()}\n")

    # Entraînement
    trainer = Trainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        lr=args.lr,
        weight_decay=args.weight_decay
    )

    history = trainer.train(
        epochs=args.epochs,
        save_dir=save_dir
    )

    # === ÉVALUATION DÉTAILLÉE ===
    print(f"\n{'='*60}")
    print("ÉVALUATION DÉTAILLÉE DU MODÈLE")
    print(f"{'='*60}\n")

    # Charger le meilleur modèle sauvegardé
    best_model_path = save_dir / "best_model.pt"
    checkpoint = torch.load(best_model_path, map_location=device)
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
        args=args,
        dataset_stats=dataset.get_statistics(),
        metrics=metrics
    )

    print(f"{'='*60}")
    print("✅ Entraînement et évaluation terminés!")
    print(f"Résultats sauvegardés dans: {save_dir}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
