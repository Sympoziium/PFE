#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dataset PyTorch pour l'entraînement du MLP de contrôle.

Charge les fichiers JSONL générés par le système d'échantillonnage
(captures.jsonl = vecteurs d'état, labels.jsonl = commandes moteur).
"""

import json
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader, random_split, WeightedRandomSampler
from pathlib import Path

# Indices des features dans le vecteur 27-dim pour lesquelles calculer un delta temporel
# delta[t] = state[t] - state[t-1], approxime les dérivées (vitesse de changement)
DELTA_FEATURE_INDICES = [1, 3, 6, 7, 18]  # IR_bot_R, IR_bot_L, IR_diff, IR_sum, gyro_z
DELTA_FEATURE_NAMES = ['IR_bot_R_delta', 'IR_bot_L_delta', 'IR_diff_delta', 'IR_sum_delta', 'gyro_z_delta']


class ZumiControlDataset(Dataset):
    """Dataset pour l'apprentissage par imitation du contrôle Zumi.

    Format des données:
        - captures.jsonl: vecteurs d'état normalisés (dim = 17 + N classes)
        - labels.jsonl: commandes moteur normalisées [left, right] dans [-1, 1]
    """

    def __init__(self, data_dir: str):
        """
        Args:
            data_dir: Répertoire contenant captures.jsonl et labels.jsonl
        """
        self.data_dir = Path(data_dir)
        self.captures = []
        self.labels = []

        self._load_data()

    def _load_data(self):
        """Charge les fichiers JSONL en mémoire."""
        captures_path = self.data_dir / "captures.jsonl"
        labels_path = self.data_dir / "labels.jsonl"

        if not captures_path.exists():
            raise FileNotFoundError(f"Fichier captures.jsonl non trouvé: {captures_path}")
        if not labels_path.exists():
            raise FileNotFoundError(f"Fichier labels.jsonl non trouvé: {labels_path}")

        # Charger les captures (états)
        with open(captures_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.captures.append(json.loads(line))

        # Charger les labels (commandes)
        with open(labels_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    self.labels.append(json.loads(line))

        # Validation
        if len(self.captures) != len(self.labels):
            raise ValueError(
                f"Nombre d'échantillons incohérent: "
                f"{len(self.captures)} captures vs {len(self.labels)} labels"
            )

        # Convertir en tenseurs numpy pour efficacité
        self.captures = np.array(self.captures, dtype=np.float32)
        self.labels = np.array(self.labels, dtype=np.float32)

        print(f"[Dataset] Chargé {len(self)} échantillons")
        print(f"[Dataset] Dimension entrée: {self.input_dim}, Dimension sortie: {self.output_dim}")

    @property
    def input_dim(self) -> int:
        """Dimension du vecteur d'entrée."""
        return self.captures.shape[1] if len(self.captures) > 0 else 0

    @property
    def output_dim(self) -> int:
        """Dimension du vecteur de sortie."""
        return self.labels.shape[1] if len(self.labels) > 0 else 0

    def __len__(self) -> int:
        return len(self.captures)

    def __getitem__(self, idx: int):
        """Retourne un tuple (état, commande) en tenseurs PyTorch."""
        state = torch.from_numpy(self.captures[idx])
        command = torch.from_numpy(self.labels[idx])
        return state, command

    def deduplicate(self, threshold: float = 1e-4):
        """Retire les echantillons consecutifs quasi-identiques.

        Ces doublons proviennent de moments ou le robot est immobile ou
        le sampling est trop rapide. Ils biaisent le modele vers 'ne rien faire'.

        Args:
            threshold: Distance L2 minimale entre deux echantillons consecutifs.
        """
        if len(self.captures) < 2:
            return

        diffs = np.linalg.norm(self.captures[1:] - self.captures[:-1], axis=1)
        keep = np.concatenate([[True], diffs >= threshold])
        n_removed = int(np.sum(~keep))
        self.captures = self.captures[keep]
        self.labels = self.labels[keep]
        print(f"[Dataset] Deduplication: {n_removed} doublons retires ({len(self)} restants)")

    def compute_deltas(self, delta_indices: list = None):
        """Calcule les features temporelles delta[t] = state[t] - state[t-1].

        Les deltas approximent les derivees temporelles (vitesse de changement)
        et sont appeles AVANT le shuffle pour que les echantillons consecutifs
        soient coherents. Chaque delta est ensuite attache a son echantillon.

        Args:
            delta_indices: Indices des features source dans le vecteur original.
                          Par defaut DELTA_FEATURE_INDICES.
        """
        if delta_indices is None:
            delta_indices = DELTA_FEATURE_INDICES

        if len(self.captures) < 2:
            return

        # Calculer les deltas pour les features selectionnees
        selected = self.captures[:, delta_indices]
        deltas = np.zeros_like(selected)
        deltas[1:] = selected[1:] - selected[:-1]

        # Detecter les frontieres de sequence (transition entre sessions d'echantillonnage)
        # On utilise uniquement les features IR (indices 0-3 dans delta_indices) pour la detection
        # car gyro_z peut varier enormement au sein d'une meme session.
        # Seuil: un saut > 150 en L2 sur les IR seulement indique un changement de session.
        ir_delta_cols = [j for j, idx in enumerate(delta_indices) if idx <= 7]  # IR features (indices 0-7)
        if ir_delta_cols:
            ir_jumps = np.linalg.norm(deltas[:, ir_delta_cols], axis=1)
            boundary_mask = ir_jumps > 150.0
        else:
            boundary_mask = np.zeros(len(deltas), dtype=bool)
        boundary_mask[0] = True  # premier echantillon = pas de precedent
        n_boundaries = int(np.sum(boundary_mask))
        deltas[boundary_mask] = 0.0

        # Ajouter les deltas comme nouvelles colonnes
        self.captures = np.hstack([self.captures, deltas.astype(np.float32)])

        n_deltas = len(delta_indices)
        print(f"[Dataset] Deltas temporels: {n_deltas} features ajoutees "
              f"({self.captures.shape[1] - n_deltas}-dim -> {self.captures.shape[1]}-dim)"
              + (f", {n_boundaries} frontieres de sequence detectees" if n_boundaries > 0 else ""))

    def rescale_labels(self, old_max: float, new_max: float):
        """Re-encode les labels pour un nouveau MOTOR_SPEED_MAX.

        Les labels existants ont ete normalises par old_max (ex: 100).
        On les convertit pour new_max (ex: 50) pour mieux utiliser la plage [-1, 1].

        Args:
            old_max: Ancien MOTOR_SPEED_MAX utilise lors de l'echantillonnage.
            new_max: Nouveau MOTOR_SPEED_MAX.
        """
        if old_max == new_max:
            return

        scale = old_max / new_max
        rescaled = self.labels * scale
        n_clipped = int(np.sum(np.abs(rescaled) > 1.0))
        self.labels = np.clip(rescaled, -1.0, 1.0)
        print(f"[Dataset] Labels rescales: MAX {old_max} -> {new_max} "
              f"(facteur {scale:.1f}x, plage effective [{self.labels.min():.3f}, {self.labels.max():.3f}])")
        if n_clipped > 0:
            print(f"[Dataset] {n_clipped} valeurs clippees a [-1, 1] "
                  f"(vitesses > {new_max} dans les donnees originales)")

    def compute_sample_weights(self) -> np.ndarray:
        """Calcule les poids par echantillon pour equilibrer les categories d'actions.

        Utilise l'inverse de la frequence de chaque categorie pour que les
        actions rares (virages, arrets) soient vues aussi souvent que 'tout droit'.

        Returns:
            np.ndarray: Poids par echantillon (shape: [n_samples])
        """
        left = self.labels[:, 0]
        right = self.labels[:, 1]
        speed_avg = (left + right) / 2.0
        steering = left - right

        # Seuils en vitesse absolue (independants de MOTOR_SPEED_MAX)
        # On utilise les labels normalises, seuils relatifs
        stop_thresh = 0.02     # vitesse ~1 sur 50
        steer_thresh = 0.06    # differentiel ~3 sur 50

        categories = np.zeros(len(self.labels), dtype=np.int64)
        is_stop = (np.abs(left) < stop_thresh) & (np.abs(right) < stop_thresh)
        is_reverse = (speed_avg < -stop_thresh) & ~is_stop
        is_turn_left = (steering < -steer_thresh) & ~is_stop & ~is_reverse
        is_turn_right = (steering > steer_thresh) & ~is_stop & ~is_reverse
        is_forward = ~is_stop & ~is_reverse & ~is_turn_left & ~is_turn_right

        categories[is_stop] = 0
        categories[is_forward] = 1
        categories[is_turn_left] = 2
        categories[is_turn_right] = 3
        categories[is_reverse] = 4

        class_counts = np.bincount(categories, minlength=5).astype(np.float64)
        class_counts[class_counts == 0] = 1.0  # eviter div par zero
        class_weights = 1.0 / class_counts
        sample_weights = class_weights[categories]

        cat_names = ["Arret", "Tout droit", "Tourne G", "Tourne D", "Recule"]
        print("[Dataset] Poids par categorie (echantillonnage equilibre):")
        for i, name in enumerate(cat_names):
            count = int(class_counts[i])
            weight = class_weights[i]
            print(f"  {name:15s}: {count:5d} samples, poids {weight:.4f}")

        return sample_weights

    def apply_feature_mask(self, mask: list):
        """Retire les features mortes en ne gardant que les indices du masque.

        Args:
            mask: Liste d'indices de features a conserver (ex: [0,1,2,3,4,5,6,7,16,17,...])
        """
        original_dim = self.captures.shape[1]
        self.captures = self.captures[:, mask]
        print(f"[Dataset] Masque applique: {original_dim}-dim -> {self.captures.shape[1]}-dim "
              f"({original_dim - len(mask)} features mortes retirees)")

    def normalize(self, mean: np.ndarray, std: np.ndarray):
        """Applique la normalisation z-score aux captures.

        Args:
            mean: Moyenne par feature (shape: [input_dim])
            std: Ecart-type par feature (shape: [input_dim])
        """
        safe_std = std.copy()
        safe_std[safe_std < 1e-6] = 1.0  # eviter division par zero pour features mortes
        self.captures = (self.captures - mean) / safe_std

    def get_statistics(self) -> dict:
        """Calcule les statistiques du dataset pour analyse."""
        stats = {
            "n_samples": len(self),
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "state_mean": self.captures.mean(axis=0).tolist(),
            "state_std": self.captures.std(axis=0).tolist(),
            "label_mean": self.labels.mean(axis=0).tolist(),
            "label_std": self.labels.std(axis=0).tolist(),
            "label_min": self.labels.min(axis=0).tolist(),
            "label_max": self.labels.max(axis=0).tolist(),
        }
        return stats


def create_data_loaders(
    data_dir: str,
    batch_size: int = 32,
    train_ratio: float = 0.8,
    shuffle: bool = True,
    seed: int = 42,
    feature_mask: list = None,
    deduplicate: bool = True,
    label_rescale: tuple = None,
    balanced_sampling: bool = True
) -> tuple:
    """Crée les DataLoaders pour l'entraînement et la validation.

    Pipeline complet:
      1. Chargement des donnees
      2. Deduplication des echantillons consecutifs quasi-identiques
      3. Calcul des deltas temporels (avant shuffle, sur echantillons consecutifs)
      4. Rescaling des labels (migration MOTOR_SPEED_MAX)
      5. Calcul des poids d'echantillonnage equilibre
      6. Application du masque de features mortes
      7. Split train/validation
      8. Normalisation z-score (stats calculees sur train uniquement)
      9. Creation des DataLoaders (avec WeightedRandomSampler si equilibre)

    Args:
        data_dir: Répertoire des données
        batch_size: Taille des mini-batches
        train_ratio: Proportion des données pour l'entraînement (0.8 = 80%)
        shuffle: Mélanger les données d'entraînement (ignore si balanced_sampling=True)
        seed: Graine aléatoire pour reproductibilité
        feature_mask: Liste d'indices de features a conserver (None = toutes)
        deduplicate: Retirer les doublons consecutifs (defaut: True)
        label_rescale: Tuple (old_max, new_max) pour rescaler les labels (None = pas de rescaling)
        balanced_sampling: Utiliser WeightedRandomSampler pour equilibrer les categories (defaut: True)

    Returns:
        tuple: (train_loader, val_loader, dataset)
    """
    dataset = ZumiControlDataset(data_dir)

    # 1. Deduplication (avant tout traitement)
    if deduplicate:
        dataset.deduplicate()

    # 2. Deltas temporels (avant shuffle, sur echantillons consecutifs)
    dataset.compute_deltas()

    # 3. Rescaling des labels (migration MOTOR_SPEED_MAX)
    if label_rescale is not None:
        old_max, new_max = label_rescale
        dataset.rescale_labels(old_max, new_max)

    # 4. Calculer les poids d'echantillonnage (avant masque, base sur les labels)
    sample_weights = None
    if balanced_sampling:
        sample_weights = dataset.compute_sample_weights()

    # 5. Appliquer le masque de features (retire les features mortes)
    #    Le masque est calcule sur les features originales (27-dim).
    #    Les delta features (ajoutees apres) sont toujours actives, on les inclut.
    if feature_mask is not None:
        n_deltas = len(DELTA_FEATURE_INDICES)
        original_dim = dataset.captures.shape[1] - n_deltas
        delta_indices = list(range(original_dim, original_dim + n_deltas))
        extended_mask = feature_mask + delta_indices
        dataset.apply_feature_mask(extended_mask)
        dataset.feature_mask = extended_mask  # masque etendu (inclut les deltas)
    else:
        dataset.feature_mask = None

    # 6. Split train/validation
    n_train = int(len(dataset) * train_ratio)
    n_val = len(dataset) - n_train

    generator = torch.Generator().manual_seed(seed)
    train_dataset, val_dataset = random_split(
        dataset, [n_train, n_val], generator=generator
    )

    # 7. Calculer mean/std sur le train set uniquement (apres masque)
    train_indices = train_dataset.indices
    train_captures = dataset.captures[train_indices]
    feature_mean = train_captures.mean(axis=0)
    feature_std = train_captures.std(axis=0)

    n_dead = np.sum(feature_std < 1e-6)
    n_active = len(feature_std) - n_dead
    print(f"[Dataset] Z-score: {n_active} features actives, {n_dead} features mortes (std < 1e-6)")

    # Normaliser tout le dataset avec les stats du train set
    dataset.normalize(feature_mean, feature_std)

    # Stocker les stats pour export ultérieur
    dataset.feature_mean = feature_mean
    dataset.feature_std = feature_std

    # 8. Creer les DataLoaders
    if balanced_sampling and sample_weights is not None:
        # WeightedRandomSampler pour le train set (equilibre les categories)
        train_weights = torch.from_numpy(sample_weights[train_indices]).double()
        sampler = WeightedRandomSampler(
            weights=train_weights,
            num_samples=len(train_weights),
            replacement=True
        )
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            sampler=sampler,    # sampler remplace shuffle
            num_workers=0,
            pin_memory=True
        )
        print(f"[Dataset] Echantillonnage equilibre active (WeightedRandomSampler)")
    else:
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=0,
            pin_memory=True
        )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=True
    )

    print(f"[Dataset] Train: {n_train} samples, Val: {n_val} samples")

    return train_loader, val_loader, dataset


if __name__ == "__main__":
    # Test de chargement
    import sys

    data_dir = Path(__file__).parent / "data"
    if not data_dir.exists():
        print(f"Répertoire de données non trouvé: {data_dir}")
        sys.exit(1)

    dataset = ZumiControlDataset(str(data_dir))
    stats = dataset.get_statistics()

    print("\n=== Statistiques du Dataset ===")
    print(f"Nombre d'échantillons: {stats['n_samples']}")
    print(f"Dimension entrée: {stats['input_dim']}")
    print(f"Dimension sortie: {stats['output_dim']}")
    print(f"\nLabel (commandes moteur):")
    print(f"  Min: {stats['label_min']}")
    print(f"  Max: {stats['label_max']}")
    print(f"  Mean: {[f'{m:.3f}' for m in stats['label_mean']]}")
    print(f"  Std: {[f'{s:.3f}' for s in stats['label_std']]}")

    # Test DataLoaders
    train_loader, val_loader, _ = create_data_loaders(str(data_dir), batch_size=16)

    print(f"\nTest batch:")
    for states, commands in train_loader:
        print(f"  States shape: {states.shape}")
        print(f"  Commands shape: {commands.shape}")
        break
