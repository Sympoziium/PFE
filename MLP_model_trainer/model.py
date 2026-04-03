#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modèle MLP pour le contrôle du robot Zumi.

Architecture simple mais efficace pour l'apprentissage par imitation:
- Entrée: vecteur d'état normalisé (17 + N dimensions)
- Sortie: commandes moteur normalisées [left, right] dans [-1, 1]
"""

import torch
import torch.nn as nn


class ZumiMLP(nn.Module):
    """Réseau de neurones MLP pour le contrôle du robot Zumi.

    Architecture:
        Input -> FC -> ReLU -> Dropout -> FC -> ReLU -> Dropout -> FC -> Tanh -> Output

    La couche de sortie utilise Tanh pour garantir des sorties dans [-1, 1],
    ce qui correspond directement aux commandes moteur normalisées.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int = 2,
        hidden_dims: list = None,
        dropout: float = 0.1
    ):
        """
        Args:
            input_dim: Dimension du vecteur d'entrée (état)
            output_dim: Dimension de sortie (2 = vitesses gauche/droite)
            hidden_dims: Liste des dimensions des couches cachées
            dropout: Taux de dropout pour régularisation
        """
        super().__init__()

        if hidden_dims is None:
            hidden_dims = [64, 32]

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims

        # Construction des couches
        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout)
            ])
            prev_dim = hidden_dim

        # Couche de sortie avec Tanh pour borner à [-1, 1]
        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.Tanh())

        self.network = nn.Sequential(*layers)

        # Initialisation des poids
        self._init_weights()

    def _init_weights(self):
        """Initialisation Xavier pour une meilleure convergence."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Tensor de forme (batch_size, input_dim)

        Returns:
            Tensor de forme (batch_size, output_dim) dans [-1, 1]
        """
        return self.network(x)

    def count_parameters(self) -> int:
        """Compte le nombre de paramètres entraînables."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def summary(self) -> str:
        """Retourne un résumé de l'architecture."""
        lines = [
            f"ZumiMLP:",
            f"  Input dim: {self.input_dim}",
            f"  Hidden dims: {self.hidden_dims}",
            f"  Output dim: {self.output_dim}",
            f"  Parameters: {self.count_parameters():,}",
            f"  Architecture: {self.input_dim} -> {' -> '.join(map(str, self.hidden_dims))} -> {self.output_dim}"
        ]
        return "\n".join(lines)


class ZumiMLPLarge(ZumiMLP):
    """Version plus large du MLP pour des tâches plus complexes."""

    def __init__(self, input_dim: int, output_dim: int = 2, dropout: float = 0.2):
        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=[128, 64, 32],
            dropout=dropout
        )


class ZumiMLPSmall(ZumiMLP):
    """Version compacte du MLP optimisée pour le déploiement sur Pi Zero."""

    def __init__(self, input_dim: int, output_dim: int = 2, dropout: float = 0.05):
        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=[32, 16],
            dropout=dropout
        )


class ZumiMLPWindow(ZumiMLP):
    """Version large du MLP pour entree en fenetre glissante (~680 dims).

    Dimensionnee pour traiter des vecteurs d'etat concatenes sur plusieurs pas
    temporels (ex: 34 features x 20 pas = 680 dims). Le reseau est plus large
    que le MLP standard pour exploiter la richesse du contexte temporel.
    """

    def __init__(self, input_dim: int, output_dim: int = 2, dropout: float = 0.15):
        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dims=[256, 128, 64],
            dropout=dropout
        )


def create_model(
    input_dim: int,
    output_dim: int = 2,
    model_size: str = "medium"
) -> ZumiMLP:
    """Factory function pour créer le modèle approprié.

    Args:
        input_dim: Dimension d'entrée
        output_dim: Dimension de sortie
        model_size: "small", "medium", "large" ou "window"

    Returns:
        Instance de ZumiMLP
    """
    if model_size == "small":
        return ZumiMLPSmall(input_dim, output_dim)
    elif model_size == "large":
        return ZumiMLPLarge(input_dim, output_dim)
    elif model_size == "window":
        return ZumiMLPWindow(input_dim, output_dim)
    else:  # medium (default)
        return ZumiMLP(input_dim, output_dim)


if __name__ == "__main__":
    # Test des différentes architectures
    input_dim = 21  # 6 IR + 1 flag + 4 classes + 4 bbox + 6 IMU

    print("=== Test des architectures MLP ===\n")

    for size in ["small", "medium", "large"]:
        model = create_model(input_dim, model_size=size)
        print(f"--- {size.upper()} ---")
        print(model.summary())

        # Test forward pass
        batch = torch.randn(4, input_dim)
        output = model(batch)
        print(f"  Test output shape: {output.shape}")
        print(f"  Output range: [{output.min().item():.3f}, {output.max().item():.3f}]")
        print()
