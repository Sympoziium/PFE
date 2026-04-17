#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modèle MLP pour le contrôle du robot Zumi.

Architecture configurable pour l'apprentissage par imitation:
- Entrée: vecteur d'état normalisé (fenêtre glissante, typiquement 750 dimensions)
- Sortie: commandes moteur normalisées [left, right] dans [-1, 1]
- Les couches cachées sont configurées dynamiquement par le profil adaptatif
  ou manuellement via le mode custom.
- BatchNorm optionnel entre Linear et GELU pour une convergence plus rapide.
"""

import copy

import torch
import torch.nn as nn


class ZumiMLP(nn.Module):
    """Réseau de neurones MLP pour le contrôle du robot Zumi.

    Architecture:
        Input -> [FC -> BN -> GELU -> Dropout] x N -> FC -> Tanh -> Output

    La couche de sortie utilise Tanh pour garantir des sorties dans [-1, 1],
    ce qui correspond directement aux commandes moteur normalisées.
    BatchNorm est optionnel et peut être fusionné dans les couches Linear
    pour l'export TFLite via fuse_batchnorm().
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int = 2,
        hidden_dims: list = None,
        dropout: float = 0.3,
        use_batchnorm: bool = True
    ):
        """
        Args:
            input_dim: Dimension du vecteur d'entrée (état)
            output_dim: Dimension de sortie (2 = vitesses gauche/droite)
            hidden_dims: Liste des dimensions des couches cachées
            dropout: Taux de dropout pour régularisation
            use_batchnorm: Utiliser BatchNorm entre Linear et GELU
        """
        super().__init__()

        if hidden_dims is None:
            hidden_dims = [64, 32]

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = hidden_dims
        self.use_batchnorm = use_batchnorm

        # Construction des couches
        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            if use_batchnorm:
                layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.Dropout(dropout))
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
        bn_str = " + BN" if self.use_batchnorm else ""
        lines = [
            f"ZumiMLP{bn_str}:",
            f"  Input dim: {self.input_dim}",
            f"  Hidden dims: {self.hidden_dims}",
            f"  Output dim: {self.output_dim}",
            f"  Parameters: {self.count_parameters():,}",
            f"  Architecture: {self.input_dim} -> {' -> '.join(map(str, self.hidden_dims))} -> {self.output_dim}"
        ]
        return "\n".join(lines)

    def fuse_batchnorm(self) -> 'ZumiMLP':
        """Retourne une copie du modèle avec BatchNorm fusionné dans les couches Linear.

        Fusionne chaque paire (Linear, BatchNorm1d) en un seul Linear équivalent.
        Le modèle résultant n'a plus de BatchNorm et produit des sorties identiques
        (à la précision float32 près). Utile pour l'export TFLite où BatchNorm
        n'est pas supporté nativement.

        Formules de fusion:
            W_fused = (gamma / sqrt(var + eps)) * W
            b_fused = gamma * (b - mean) / sqrt(var + eps) + beta

        Returns:
            ZumiMLP: Nouveau modèle sans BatchNorm avec poids fusionnés.
        """
        if not self.use_batchnorm:
            return copy.deepcopy(self)

        # Créer un modèle sans BN
        fused_model = ZumiMLP(
            input_dim=self.input_dim,
            output_dim=self.output_dim,
            hidden_dims=self.hidden_dims,
            use_batchnorm=False
        )

        # Parcourir les couches du modèle source et fusionner
        src_modules = list(self.network.children())
        dst_modules = list(fused_model.network.children())

        src_idx = 0
        dst_idx = 0

        while src_idx < len(src_modules):
            src_layer = src_modules[src_idx]

            if isinstance(src_layer, nn.Linear):
                # Vérifier si la couche suivante est un BatchNorm
                if src_idx + 1 < len(src_modules) and isinstance(src_modules[src_idx + 1], nn.BatchNorm1d):
                    bn = src_modules[src_idx + 1]
                    linear = src_layer

                    # Fusionner BN dans Linear
                    gamma = bn.weight.data           # scale
                    beta = bn.bias.data              # shift
                    mean = bn.running_mean            # moyenne mobile
                    var = bn.running_var               # variance mobile
                    eps = bn.eps

                    inv_std = gamma / torch.sqrt(var + eps)

                    # W_fused = inv_std.unsqueeze(1) * W
                    w_fused = inv_std.unsqueeze(1) * linear.weight.data
                    # b_fused = inv_std * (b - mean) + beta
                    b_fused = inv_std * (linear.bias.data - mean) + beta

                    # Copier dans le modèle destination
                    dst_linear = dst_modules[dst_idx]
                    dst_linear.weight.data.copy_(w_fused)
                    dst_linear.bias.data.copy_(b_fused)

                    src_idx += 2  # skip Linear + BN
                    dst_idx += 1  # avancer dans le dst (Linear seul)
                else:
                    # Linear sans BN (couche de sortie)
                    dst_linear = dst_modules[dst_idx]
                    dst_linear.weight.data.copy_(src_layer.weight.data)
                    dst_linear.bias.data.copy_(src_layer.bias.data)
                    src_idx += 1
                    dst_idx += 1
            else:
                # GELU, Dropout, Tanh — avancer dans les deux
                src_idx += 1
                if dst_idx < len(dst_modules) and type(src_layer) == type(dst_modules[dst_idx]):
                    dst_idx += 1

        fused_model.eval()
        return fused_model


if __name__ == "__main__":
    # Test de l'architecture MLP avec differentes configurations
    print("=== Test ZumiMLP ===\n")

    for hidden_dims in [[64, 32], [128, 64, 32], [384, 192, 96, 48]]:
        model = ZumiMLP(input_dim=650, hidden_dims=hidden_dims, use_batchnorm=True)
        print(model.summary())

        # Faire quelques passes en train mode pour accumuler les running stats BN
        batch = torch.randn(32, 650)
        for _ in range(10):
            _ = model(torch.randn(32, 650))

        # Test forward pass en eval mode
        model.eval()
        with torch.no_grad():
            output = model(batch)
        print(f"  Test output shape: {output.shape}")
        print(f"  Output range: [{output.min().item():.3f}, {output.max().item():.3f}]")

        # Test fusion BatchNorm (eval mode requis pour running stats stables)
        fused = model.fuse_batchnorm()
        with torch.no_grad():
            fused_output = fused(batch)
        diff = (output - fused_output).abs().max().item()
        print(f"  BN fusion max diff: {diff:.8f} (should be < 1e-5)")
        print(f"  Fused params: {fused.count_parameters():,} (no BN)")
        print()
