#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modèle MLP pour le contrôle du robot Zumi.

Architecture configurable pour l'apprentissage par imitation:
- Entrée: vecteur d'état normalisé (fenêtre glissante, typiquement 680 dimensions)
- Sortie: commandes moteur normalisées [left, right] dans [-1, 1]
- Les couches cachées sont configurées dynamiquement par le profil adaptatif
  ou manuellement via le mode custom.
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


if __name__ == "__main__":
    # Test de l'architecture MLP avec differentes configurations
    print("=== Test ZumiMLP ===\n")

    for hidden_dims in [[64, 32], [128, 64, 32], [256, 128, 64, 32]]:
        model = ZumiMLP(input_dim=680, hidden_dims=hidden_dims)
        print(model.summary())

        # Test forward pass
        batch = torch.randn(4, 680)
        output = model(batch)
        print(f"  Test output shape: {output.shape}")
        print(f"  Output range: [{output.min().item():.3f}, {output.max().item():.3f}]")
        print()
